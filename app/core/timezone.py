import zoneinfo
from datetime import datetime

PRAGUE_TZ = zoneinfo.ZoneInfo("Europe/Prague")

def to_prague_dt(dt: datetime | None) -> datetime | None:
    """
    Ensures datetime is in Europe/Prague timezone.
    If naive, assumes Europe/Prague timezone.
    If aware (e.g. UTC from PostgreSQL TIMESTAMPTZ), converts to Europe/Prague timezone.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=PRAGUE_TZ)
    return dt.astimezone(PRAGUE_TZ)

def format_prague_dt(dt: datetime | None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """
    Formats a datetime object to string in Europe/Prague timezone.
    Guarantees that database UTC timestamps render the exact Prague local time.
    """
    if dt is None:
        return ""
    prague_dt = to_prague_dt(dt)
    return prague_dt.strftime(fmt)
