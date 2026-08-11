from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from hermes.utils import parse_date_value


class LabelItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label_id: int
    label_name: str
    created: datetime
    group_id: int
    group_name: str

    @field_validator("created", mode="before")
    @classmethod
    def parse_date(cls, value: str) -> datetime:
        return parse_date_value(value)


class CargoMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    holder: str | None = None  # only in non-operational
    description: str
    is_verified: bool | None = None  # only in operational
    file_labels: list[LabelItem] | None = []  # only in operational

    path_id: str
    path: str
    path_list: list[str] = []

    reality_id: str | None = None  # only in operational
    reality_type: str | None = None  # only in non-operational

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

    @field_validator("created", "last_modified", "ver_last_modified", mode="before")
    @classmethod
    def parse_mandatory_date(cls, value: str) -> datetime:
        return parse_date_value(value)

    @field_validator("delete_date", mode="before")
    @classmethod
    def parse_optional_date(cls, value: str | None) -> datetime | None:
        if value is None:
            return None
        return parse_date_value(value)

    @model_validator(mode="after")
    def set_path_list(self) -> CargoMessage:
        self.path_list = [part.strip() for part in self.path_id.split("/") if part.strip()]
        return self


class CargoEnrichedMessage(CargoMessage):
    text_content: str
    type: str
