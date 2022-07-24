from datetime import datetime
from dateutil.parser import isoparse
from dateutil.tz import UTC


def to_utc(datetime_str: str) -> datetime:
    return isoparse(datetime_str).astimezone(UTC)


def to_utc_at_day_start(datetime_str: str) -> datetime:
    return isoparse(datetime_str).astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def to_utc_iso_format_at_day_start(datetime_str: str) -> str:
    return to_utc_at_day_start(datetime_str).isoformat()


def to_utc_iso_format_day_interval(datetime_str: str) -> dict:
    start = to_utc_at_day_start(datetime_str)
    end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
    return {
        'start': start.isoformat(),
        'end': end.isoformat()
    }


def now_as_utc_iso_format_datetime() -> str:
    return datetime.utcnow().isoformat()
