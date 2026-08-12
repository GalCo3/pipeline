from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hermes.utils import parse_date_value


class ChatMessageFile(BaseModel):
    # Enrichment re-validates an already-dumped message, where the source
    # aliases are gone, so every model has to accept its field names too.
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str | None = Field(default=None, alias="_id")
    name: str | None = None
    type: str | None = None


class ChatMessageUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str | None = Field(default=None, alias="_id")
    username: str | None = None
    name: str | None = None
    cleanName: str | None = None


class ChatMessageChannel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str | None = Field(default=None, alias="_id")
    name: str | None = None


class ChatMessageTriangle(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str | None = None
    name: str | None = None
    clearance: int | None = None


class ChatMessageClassification(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    triangles: dict[str, ChatMessageTriangle] = Field(default_factory=dict)

    @field_validator("triangles", mode="before")
    @classmethod
    def default_triangles(cls, value: dict | None) -> dict:
        return value or {}


class ChatMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(alias="_id")
    room_id: str | None = Field(default=None, alias="rid")
    msg: str | None = None
    # `from` is a keyword, so the source key is carried by the alias.
    sender: str | None = Field(default=None, alias="from")

    created_at: datetime | None = Field(default=None, alias="ts")
    updated_at: datetime | None = Field(default=None, alias="_updatedAt")

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

    classification: ChatMessageClassification | None = None

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
