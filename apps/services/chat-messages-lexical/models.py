from __future__ import annotations

from datetime import datetime

from hermes.utils import parse_date_value
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatMessageFile(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str | None = None
    name: str | None = None
    type: str | None = None


class ChatMessageUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str | None = None
    username: str | None = None
    name: str | None = None


class ChatMessageChannel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str | None = None
    name: str | None = None


class ChatMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(alias="id_")
    room_id: str | None = Field(default=None, alias="rid")
    msg: str | None = None
    # `from` is a keyword, so the alias carries the source key.
    sender: str | None = Field(default=None, alias="from")

    created_at: datetime | None = Field(default=None, alias="ts")
    updated_at: datetime | None = Field(default=None, alias="updatedAt_")

    file: ChatMessageFile | None = None
    description: str | None = None

    user: ChatMessageUser | None = Field(default=None, alias="u")
    mentions: list[ChatMessageUser] = []
    channels: list[ChatMessageChannel] = []

    t: bool | None = None
    url_strings: list[str] = Field(default=[], alias="urlStrings")

    room_type: str | None = None
    room_name: str | None = None
    users_count: int | None = Field(default=None, alias="usersCount")

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v: object) -> str:
        return str(v)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_optional_date(cls, value: str | None) -> datetime | None:
        return parse_date_value(value) if value else None

    @field_validator("mentions", "channels", "url_strings", mode="before")
    @classmethod
    def default_list(cls, value: list | None) -> list:
        return value or []


class ChatEnrichedMessage(ChatMessage):
    midur_ids: list[str] | None = None
