from pydantic import BaseModel, PositiveFloat, PositiveInt


class TritonConfig(BaseModel, frozen=True):
    url: str
    model_name: str
    model_version: str = ""
    input_name: str = "TEXT"
    output_name: str = "EMBEDDING"
    embedding_dim: PositiveInt = 1024
    timeout: PositiveFloat = 30.0
    batch_size: PositiveInt = 32

    @property
    def embedding_version(self) -> str:
        return f"{self.model_name}:{self.model_version or 'latest'}"
