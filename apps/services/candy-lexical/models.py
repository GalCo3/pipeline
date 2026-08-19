from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hermes.utils import parse_date_value


class CandyReportsMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    creating_user_name: str = Field(alias="creatingUserName")
    actual_user_name: str | None = Field(default=None, alias="actualUserName")
    description: str
    type: str
    date: datetime
    actual_date: datetime | None = Field(default=None, alias="actualDate")
    is_deleted: bool = Field(alias="isDeleted")
    updating_user: str | None = Field(default=None, alias="updatingUser")
    last_deletion_date: datetime | None = Field(default=None, alias="lastDeletionDate")
    event_id: int | None = Field(default=None, alias="eventId")
    delete_author: str | None = Field(default=None, alias="deleteAuthor")
    cell_id: str = Field(alias="cellId")
    reality_id: str = Field(alias="realityId")
    cell_hierarchy: str = Field(alias="cellHierarchy")
    creation_date: datetime = Field(alias="creationDate")
    last_update_time_to_transfer: datetime = Field(alias="lastUpdateTimeToTransfer")
    frame: str | None = None
    mclol: str | None = None
    cell: str | None = None
    mirage_action: str | None = Field(default=None, alias="mirageAction")
    military_district_id: int = Field(alias="militaryDistrictId")
    military_district_name: str = Field(alias="militaryDistrictName")

    @model_validator(mode="before")
    @classmethod
    def transform(cls, data: dict) -> dict:
        if not data:
            return {}
        data["id"] = str(data["id"])
        event_id = data.get("eventId")
        data["eventId"] = int(event_id) if event_id is not None else None
        data["cellId"] = str(data["cellId"])
        data["realityId"] = str(data["realityId"])
        cell_hierarchy: str = data["cellHierarchy"]
        if cell_hierarchy:
            hierarchy = cell_hierarchy.split("/")
            data["frame"] = hierarchy[0]
            data["mclol"] = hierarchy[1]
            data["cell"] = hierarchy[2]
        return data

    @field_validator("date", "creation_date", "last_update_time_to_transfer", mode="before")
    @classmethod
    def parse_mandatory_date(cls, value: str | int) -> datetime:
        return parse_date_value(value)

    @field_validator("actual_date", "last_deletion_date", mode="before")
    @classmethod
    def parse_optional_date(cls, value: str | int | None) -> datetime | None:
        if value is None or value == "null":
            return None

        return parse_date_value(value)
