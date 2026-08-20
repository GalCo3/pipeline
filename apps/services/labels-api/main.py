from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path

from constants import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, MAX_CONTENT_LENGTH
from fastapi import FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from models import RecommendationRequest, RecommendationResponse
from settings import get_settings
from utils import (
    build_system_prompt,
    build_user_message,
    parse_llm_json_response,
)

from hermes.connections import BaseLLMHandler, BaseS3Handler
from hermes.observability import (
    MessageStatus,
    TelemetryCounter,
    get_logger,
    init_observability,
)
from hermes.observability.fastapi import add_fastapi_observability
from hermes.utils import CargoFileNotFoundError, extract_cargo_files_text

STATIC_DIR = Path(__file__).parent / "static"

init_observability(service_name="labels-api")
logger = get_logger(__name__)

requests_processed = TelemetryCounter("labels_api_requests_total", allowed_labels=["status"])


class AppState:
    s3_client: BaseS3Handler | None = None
    llm_client: BaseLLMHandler | None = None

    def get_s3_client(self) -> BaseS3Handler:
        if self.s3_client is None:
            raise RuntimeError("S3 client is not initialized.")
        return self.s3_client

    def get_llm_client(self) -> BaseLLMHandler:
        if self.llm_client is None:
            raise RuntimeError("LLM client is not initialized.")
        return self.llm_client


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    state.s3_client = BaseS3Handler(settings.cargo_config)
    state.llm_client = BaseLLMHandler(settings.llm_config)
    yield
    if state.llm_client:
        state.llm_client.close()


app = FastAPI(title="Labels API", lifespan=lifespan, docs_url=None)
add_fastapi_observability(app, enable_access_logs=False)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    if (STATIC_DIR / "swagger-ui-bundle.js").exists():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="/static/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger-ui.css",
        )
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    )


@app.post("/recommend", response_model=RecommendationResponse)
async def recommend_label(request: RecommendationRequest):
    try:
        logger.info("Processing recommendation request", doc_name=request.name)

        # 1. Extract text from S3
        extraction_result = extract_cargo_files_text(
            state.get_s3_client(), request.s3_key, request.s3_bucket
        )

        if not extraction_result or not extraction_result.text.strip():
            logger.warning("Document extraction failed or empty", doc_name=request.name)
            requests_processed.inc(labels={"status": MessageStatus.SKIPPED})
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Document could not be extracted or is empty",
            )

        # 2. Build Prompt
        system_prompt = build_system_prompt()
        user_message = build_user_message(
            name=request.name,
            labels=request.available_labels,
            content=extraction_result.text[:MAX_CONTENT_LENGTH],
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # 3. Call LLM
        llm_response = state.get_llm_client().chat_completion(
            messages=messages,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
        )

        if not llm_response.is_success:
            logger.error("LLM Request Failed", error=str(llm_response.error))
            requests_processed.inc(labels={"status": MessageStatus.ERROR})
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Failed to get recommendation from LLM",
            )

        # Parse LLM response (OpenAI format)
        try:
            response_data = llm_response.response
            raw_text = response_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            logger.error(
                "Unexpected LLM response format", error=str(e), response=llm_response.response
            )
            requests_processed.inc(labels={"status": MessageStatus.ERROR})
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Invalid response structure from LLM",
            ) from e

        # Extract label from JSON or fallback
        suggested_label = parse_llm_json_response(raw_text, request.available_labels)
        if not suggested_label:
            logger.warning("Could not parse JSON or missing recommended_label", raw_text=raw_text)
            requests_processed.inc(labels={"status": MessageStatus.ERROR})
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Failed to parse valid recommendation label from LLM response",
            )

        # 4. Validate Label against allowed set
        if suggested_label not in request.available_labels:
            logger.warning(
                "LLM returned a label not in candidate list",
                label=suggested_label,
                available=request.available_labels,
            )
            requests_processed.inc(labels={"status": MessageStatus.ERROR})
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=f"LLM returned invalid label: {suggested_label}",
            )

        logger.info(
            f"Successfully recommended label '{suggested_label}' for document '{request.name}'",
            doc_name=request.name,
            label=suggested_label,
        )
        requests_processed.inc(labels={"status": MessageStatus.SUCCESS})
        return RecommendationResponse(label=suggested_label)

    except HTTPException:
        raise
    except CargoFileNotFoundError as e:
        logger.warning("Cargo file not found in S3 for recommendation", error=str(e))
        requests_processed.inc(labels={"status": MessageStatus.NOT_FOUND})
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Cargo file not found") from e
    except Exception as e:
        logger.error("Failed to process recommendation request", exc_info=True)
        requests_processed.inc(labels={"status": MessageStatus.ERROR})
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Internal server error"
        ) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080, access_log=False, reload=False)
