from datetime import datetime
from typing import Optional
import zoneinfo

DEFAULT_TZ_NAME = "Europe/Prague"
PRAGUE_TZ = zoneinfo.ZoneInfo(DEFAULT_TZ_NAME)


def get_zoneinfo(tz_name: Optional[str] = None) -> zoneinfo.ZoneInfo:
    """Resolves a valid IANA ZoneInfo, falling back to Europe/Prague on invalid input."""
    if not tz_name:
        return PRAGUE_TZ
    try:
        return zoneinfo.ZoneInfo(str(tz_name).strip())
    except Exception:
        return PRAGUE_TZ


def to_tenant_dt(
    dt: Optional[datetime], tz_name: Optional[str] = None
) -> Optional[datetime]:
    """Converts a datetime to the tenant's configured IANA timezone."""
    if dt is None:
        return None
    tz = get_zoneinfo(tz_name)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def format_tenant_dt(
    dt: Optional[datetime],
    fmt: str = "%d.%m.%Y %H:%M",
    tz_name: Optional[str] = None,
) -> str:
    """Formats a datetime in the tenant's configured IANA timezone."""
    if dt is None:
        return ""
    local_dt = to_tenant_dt(dt, tz_name=tz_name)
    return local_dt.strftime(fmt) if local_dt else ""


def to_prague_dt(dt: datetime | None) -> datetime | None:
    """Backward-compatible helper converting datetime to Europe/Prague."""
    return to_tenant_dt(dt, tz_name=DEFAULT_TZ_NAME)


def format_prague_dt(dt: datetime | None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Backward-compatible helper formatting datetime in Europe/Prague."""
    return format_tenant_dt(dt, fmt=fmt, tz_name=DEFAULT_TZ_NAME)
