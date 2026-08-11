from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from hermes.utils import parse_date_value


class CandyReportsMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    creatingUserName: str
    actualUserName: str | None = None
    description: str
    type: str
    date: datetime
    actualDate: datetime | None = None
    isDeleted: bool
    updatingUser: str | None = None
    lastDeletionDate: datetime | None = None
    eventId: str
    deleteAuthor: str | None = None
    cellId: str
    realityId: str
    cellHierarchy: str
    creationDate: datetime
    lastUpdateTimeToTransfer: datetime
    frame: str | None = None
    mclol: str | None = None
    cell: str | None = None
    mirageAction: str | None = None
    militaryDistrictId: int

    @model_validator(mode="before")
    @classmethod
    def transform(cls, data: dict) -> dict:
        if not data:
            return {}
        data["id"] = str(data["id"])
        data["eventId"] = str(data["eventId"])
        data["cellId"] = str(data["cellId"])
        data["realityId"] = str(data["realityId"])
        cell_hierarchy: str = data["cellHierarchy"]
        if cell_hierarchy:
            hierarchy = cell_hierarchy.split("/")
            data["frame"] = hierarchy[0]
            data["mclol"] = hierarchy[1]
            data["cell"] = hierarchy[2]
        return data

    @field_validator("date", "creationDate", "lastUpdateTimeToTransfer", mode="before")
    @classmethod
    def parse_mandatory_date(cls, value: str | int) -> datetime:
        return parse_date_value(value)

    @field_validator("actualDate", "lastDeletionDate", mode="before")
    @classmethod
    def parse_optional_date(cls, value: str | int | None) -> datetime | None:
        if value is None:
            return None
        return parse_date_value(value)
