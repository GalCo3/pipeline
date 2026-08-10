from datetime import datetime

from dateutil import parser


def parse_date_value(value: str) -> datetime:
    val_clean = value.strip()
    try:
        return datetime.fromisoformat(val_clean)
    except ValueError:
        return parser.parse(val_clean)
