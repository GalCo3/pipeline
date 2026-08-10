from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from hermes.utils import parse_date_value


class ChatUserMessage(BaseModel):
    # Source payload mixes camelCase and snake_case, so every non-matching key
    # is aliased.
    id: str
    created_at: datetime = Field(alias="createdAt")
    name: str | None = None
    email_address: str | None = None
    username: str | None = None
    updated_at: datetime = Field(alias="updatedAt_")
    roles: list[str] = []
    hatzava_chail: str | None = None
    hatzava_pikud: str | None = None
    hatzava_yechida: str | None = None
    clean_name: str | None = Field(default=None, alias="cleanName")
    classification_level: int | None = None
    classification_color: str | None = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v: object) -> str:
        return str(v)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_mandatory_date(cls, value: str) -> datetime:
        return parse_date_value(value)

    @field_validator("roles", mode="before")
    @classmethod
    def default_roles(cls, value: list[str] | None) -> list[str]:
        return value or []
