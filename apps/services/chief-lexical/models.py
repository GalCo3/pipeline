from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

from hermes.utils import parse_date_value


class ChiefCommandContent(BaseModel):
    id: str | int
    name: str
    full_name: str
    order: int
    user_id: str | int
    create_date: datetime | str
    last_update_date: datetime | str
    note: str | None = None
    text: str | None = None

    @field_validator("create_date", "last_update_date", mode="before")
    @classmethod
    def parse_date(cls, value: str | datetime | None) -> datetime | str | None:
        if isinstance(value, str):
            try:
                return parse_date_value(value)
            except Exception:
                return value
        return value


class ChiefMessage(BaseModel):
    id: str
    type: str
    template_id: str
    reference_id: str
    name: str
    create_date: datetime
    last_update_date: datetime
    stage: str
    description: str
    mifkada: str
    version: int
    classification: str
    validity_start_date: datetime
    content_last_update_date: datetime
    validity_end_date: datetime | None = None
    reality_id: int
    michlol_id: str
    attachments_description: str
    doc_num: int
    distribution_date: datetime
    metro_last_update_date: datetime
    last_distribution_date: datetime
    type_display_name: str
    is_deleted: bool
    mailing_list: list[str]
    directories: list[str]
    operational_directory: str | None = None

    @field_validator(
        "create_date",
        "last_update_date",
        "validity_start_date",
        "content_last_update_date",
        "distribution_date",
        "metro_last_update_date",
        "last_distribution_date",
        mode="before",
    )
    @classmethod
    def parse_mandatory_date(cls, value: str) -> datetime:
        return parse_date_value(value)

    @field_validator("validity_end_date", mode="before")
    @classmethod
    def parse_optional_date(cls, value: str | None) -> datetime | None:
        if value is None:
            return None
        return parse_date_value(value)


class ChiefEnrichedMessage(ChiefMessage):
    command_content: list[ChiefCommandContent]
    cleaned_text: str
