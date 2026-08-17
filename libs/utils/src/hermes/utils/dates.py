from datetime import UTC, datetime

from dateutil import parser


def parse_date_value(value: str | int) -> datetime:
    if isinstance(value, int):
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    val_clean = value.strip()
    try:
        return datetime.fromisoformat(val_clean)
    except ValueError:
        return parser.parse(val_clean)
