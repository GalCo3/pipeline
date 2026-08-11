from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hermes.utils import parse_date_value


class ChatBaseModel(BaseModel):
    # Enrichment re-validates an already-dumped message, where the source
    # aliases are gone, so every model has to accept its field names too.
    model_config = ConfigDict(populate_by_name=True)


class ChatMessageFile(ChatBaseModel):
    id: str | None = Field(default=None, alias="id_")
    name: str | None = None
    type: str | None = None


class ChatMessageUser(ChatBaseModel):
    id: str | None = Field(default=None, alias="id_")
    username: str | None = None
    name: str | None = None


class ChatMessageChannel(ChatBaseModel):
    id: str | None = Field(default=None, alias="id_")
    name: str | None = None


class ChatMessage(ChatBaseModel):
    id: str = Field(alias="id_")
    room_id: str | None = Field(default=None, alias="rid")
    msg: str | None = None
    # `from` is a keyword, so the source key is carried by the alias.
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
