from __future__ import annotations

from datetime import datetime

from dateutil import parser
from pydantic import BaseModel, field_validator, model_validator


def parse_date_value(value: str) -> datetime:
    val_clean = value.strip()
    try:
        return datetime.fromisoformat(val_clean)
    except ValueError:
        return parser.parse(val_clean)


class CandyReportsMessage(BaseModel):
    id: str
    creatingusername: str
    actualusername: str | None = None
    description: str
    type: str
    date: datetime
    actualdate: datetime | None = None
    isdeleted: bool
    updatinguser: str | None = None
    lastdeletiondate: datetime | None = None
    eventid: str
    deleteauthor: str | None = None
    cellid: str
    realityid: str
    cellhierarchy: str
    creationdate: datetime
    lastupdatetimetotransfer: datetime
    frame: str | None = None
    mclol: str | None = None
    cell: str | None = None
    mirageaction: str | None = None
    militarydistrictid: int

    @model_validator(mode="before")
    @classmethod
    def transform(cls, data: dict) -> dict:
        if not data:
            return {}
        data["id"] = str(data["id"])
        data["eventid"] = str(data["eventid"])
        data["cellid"] = str(data["cellid"])
        data["realityid"] = str(data["realityid"])
        cell_hierarchy: str = data.get("cellhierarchy")
        if cell_hierarchy:
            hierarchy = cell_hierarchy.split("/")
            data["frame"] = hierarchy[0]
            data["mclol"] = hierarchy[1]
            data["cell"] = hierarchy[2]
        return data

    @field_validator(
        "date",
        "creationdate",
        "lastupdatetimetotransfer",
        mode="before",
    )
    @classmethod
    def parse_mandatory_date(cls, value: str) -> datetime:
        return parse_date_value(value)

    @field_validator(
        "actualdate",
        "lastdeletiondate",
        mode="before",
    )
    @classmethod
    def parse_optional_date(cls, value: str | None) -> datetime | None:
        if value is None:
            return None
        return parse_date_value(value)
