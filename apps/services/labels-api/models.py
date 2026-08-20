from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    s3_key: str = Field(..., description="Key of the document in S3")
    s3_bucket: str = Field(..., description="Bucket where the document is stored")
    name: str = Field(..., description="Name of the document")
    available_labels: list[str] = Field(..., min_length=1, description="List of possible labels")


class RecommendationResponse(BaseModel):
    label: str | None = Field(
        default=None, description="The recommended label, or null if none fit / error"
    )
    error: str | None = Field(default=None, description="Error message if any")
