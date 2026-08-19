from datetime import UTC, datetime

from dateutil import parser


def to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.replace(microsecond=0)


def parse_date_value(value: str | int) -> datetime:
    if isinstance(value, int):
        return to_utc_naive(datetime.fromtimestamp(value / 1000, tz=UTC))
    val_clean = value.strip()
    try:
        return to_utc_naive(datetime.fromisoformat(val_clean))
    except ValueError:
        return to_utc_naive(parser.parse(val_clean))
