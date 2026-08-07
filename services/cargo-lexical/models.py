from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, field_validator, model_validator

DATETIME_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S"


class LabelItem(BaseModel):
    label_id: int
    label_name: str
    created: datetime
    group_id: int
    group_name: str

    @field_validator("created", mode="before")
    @classmethod
    def parse_date(cls, value: str | datetime) -> datetime:
        # Already a datetime when a dumped model is re-validated, e.g.
        # CargoEnrichedMessage(**cargo_message.model_dump()).
        return datetime.strptime(value, DATETIME_FORMAT) if isinstance(value, str) else value


class CargoMessage(BaseModel):
    id: str
    name: str
    holder: str
    description: str
    is_verified: bool | None  # only in operational
    file_labels: list[LabelItem] | None = []  # only in operational

    path_id: str
    path: str
    path_list: list[str] = []

    reality_id: str | None  # only in operational
    reality_type: str | None  # only in non-operational

    s3_key: str
    s3_bucket: str

    created: datetime
    last_modified: datetime
    ver_last_modified: datetime
    delete_date: datetime | None = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v: object) -> str:
        return str(v)

    @field_validator("created", "last_modified", "ver_last_modified", "delete_date", mode="before")
    @classmethod
    def parse_date(cls, value: str | datetime | None) -> datetime | None:
        return datetime.strptime(value, DATETIME_FORMAT) if isinstance(value, str) else value

    @model_validator(mode="after")
    def set_path_list(self) -> CargoMessage:
        self.path_list = [part.strip() for part in self.path_id.split("/")]
        return self


class CargoEnrichedMessage(CargoMessage):
    text_content: str
    type: str
