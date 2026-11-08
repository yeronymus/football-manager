"""
Pure-domain RFC 5545 iCalendar (.ics) generator and stateless HMAC calendar token signer.
Enables employees and players to subscribe their Google Calendar, Apple Calendar, or
Microsoft Outlook to live match schedules (ACTIVE = CONFIRMED, RESERVE = TENTATIVE)
with automatic 2-hour reminders (VALARM).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from typing import Optional, Sequence


@dataclass(frozen=True)
class CalendarMatchEvent:
    game_id: int
    sequence_number: int
    title: str
    location: str
    start_utc: datetime
    duration_hours: float = 2.0
    is_reserve: bool = False
    price: int = 0
    currency: str = "CZK"
    is_free_corporate: bool = False


def generate_calendar_token(user_id: int, secret: str) -> str:
    """
    Generates a stateless, URL-safe token `<user_id>.<16-hex-hmac>` for a user's iCal feed.
    """
    msg = f"ical:{int(user_id)}".encode("utf-8")
    key = (secret or "default-calendar-secret").encode("utf-8")
    sig = hmac.new(key, msg, hashlib.sha256).hexdigest()[:20]
    return f"{int(user_id)}.{sig}"


def verify_calendar_token(token: str, secret: str) -> Optional[int]:
    """
    Verifies a `<user_id>.<sig>` calendar token in constant time and returns `user_id` if valid.
    """
    if not token or "." not in token:
        return None
    parts = token.split(".", 1)
    try:
        uid = int(parts[0])
    except ValueError:
        return None
    expected = generate_calendar_token(uid, secret)
    if hmac.compare_digest(token, expected):
        return uid
    return None


def _escape_ics_text(value: str) -> str:
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _format_ics_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        utc_dt = dt.replace(tzinfo=timezone.utc)
    else:
        utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y%m%dT%H%M%SZ")


def build_icalendar_feed(
    events: Sequence[CalendarMatchEvent],
    calendar_name: str = "Sports Platform Schedule",
) -> str:
    """
    Builds a standards-compliant RFC 5545 VCALENDAR (.ics) string with CRLF line endings.
    """
    now_str = _format_ics_utc(datetime.now(timezone.utc))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Sports Manager Enterprise Platform//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_ics_text(calendar_name)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]

    for ev in events:
        start_dt = (
            ev.start_utc.replace(tzinfo=timezone.utc)
            if ev.start_utc.tzinfo is None
            else ev.start_utc.astimezone(timezone.utc)
        )
        end_dt = start_dt + timedelta(hours=float(ev.duration_hours or 2.0))
        status_badge = "[RESERVE] " if ev.is_reserve else ""
        summary = f"{status_badge}{ev.title} #{ev.sequence_number}"
        ics_status = "TENTATIVE" if ev.is_reserve else "CONFIRMED"

        if ev.is_free_corporate:
            fee_line = "Fee: Covered by Organization (Free Corporate)"
        elif ev.price > 0:
            fee_line = f"Fee: {ev.price} {ev.currency}"
        else:
            fee_line = "Fee: Free"

        roster_line = "Status: Reserve List (Waiting for slot)" if ev.is_reserve else "Status: Main Squad (Confirmed)"
        description = f"{roster_line}\nLocation: {ev.location}\n{fee_line}"

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:match-{ev.game_id}@sports-manager.enterprise",
                f"DTSTAMP:{now_str}",
                f"DTSTART:{_format_ics_utc(start_dt)}",
                f"DTEND:{_format_ics_utc(end_dt)}",
                f"SUMMARY:{_escape_ics_text(summary)}",
                f"LOCATION:{_escape_ics_text(ev.location)}",
                f"DESCRIPTION:{_escape_ics_text(description)}",
                f"STATUS:{ics_status}",
                "BEGIN:VALARM",
                "TRIGGER:-PT2H",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Upcoming match in 2 hours: {_escape_ics_text(summary)}",
                "END:VALARM",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
