from pydantic import BaseModel, Field


class BaseLLMConfig(BaseModel):
    base_url: str = Field(
        ..., description="Base URL of the LLM service (e.g. https://models.ai-services.idf.cts)"
    )
    token: str = Field(..., description="Bearer token for authentication")
    model_name: str = Field(default="openai/gpt-oss-120b", description="Model identifier to use")
    endpoint: str = Field(default="v1/chat/completions", description="Endpoint path")
    timeout: int = Field(default=30, description="Timeout in seconds for the HTTP request")
    max_retries: int = Field(default=3, description="Maximum number of retries for failed requests")
    verify_ssl: bool = Field(
        default=False, description="Whether to verify SSL certificates (default False)"
    )
