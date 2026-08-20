from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Mock LLM Server")


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
def mock_all():
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a generic response from the LLM service.",
                },
                "finish_reason": "stop",
            }
        ],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
