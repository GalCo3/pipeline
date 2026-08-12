from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hermes.utils import parse_date_value


class ChatRoomMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str | None = None

    room_type: str | None = None
    classification_level: int | None = Field(default=None, alias="classificationLevel")
    classification_color: str | None = Field(default=None, alias="classificationColor")

    created_at: datetime | None = Field(default=None, alias="ts")
    updated_at: datetime | None = Field(default=None, alias="_updatedAt")

    description: str | None = None
    topic: str | None = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v: object) -> str:
        return str(v)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_optional_date(cls, value: str | None) -> datetime | None:
        return parse_date_value(value) if value else None
