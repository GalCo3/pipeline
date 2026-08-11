from datetime import datetime, timezone

from dateutil import parser


def parse_date_value(value: str | int) -> datetime:
    if isinstance(value, int):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    val_clean = value.strip()
    try:
        return datetime.fromisoformat(val_clean)
    except ValueError:
        return parser.parse(val_clean)
