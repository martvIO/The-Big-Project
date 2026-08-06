"""The `.ics` builder (F24 D5). Pure, stdlib, no dependency.

**Stdlib and not `icalendar`.** One VEVENT with six properties is forty lines of
string assembly; a dependency here buys a parser this product never reads back,
plus a supply-chain surface on the one artefact customers forward to other
people.

**UTC instants, no VTIMEZONE.** `DTSTART`/`DTEND` are absolute `…Z` values.
Israel moves between IST (+02:00) and IDT (+03:00), and a hand-written VTIMEZONE
is wrong for half the year; an instant is DST-proof and every client renders it
in the reader's own wall clock.

**No capability anywhere in the file.** `.ics` attachments are forwarded and
synced into shared calendars. A manage token inside one hands control of the
appointment to whoever the invite reached — so this module never touches
`manage_token_hash`, never builds a `/b/{token}` URL, and takes no token
argument it could accidentally render.
"""

import datetime

from app.models.booking import Booking

CRLF = "\r\n"
# RFC 5545 §3.1: content lines are folded at 75 OCTETS, not characters. Hebrew
# is two octets per letter, so a character-counted fold produces lines a strict
# parser rejects on exactly the boutiques this product is for.
ICS_MAX_OCTETS = 75
PRODID = "-//MODRYN//Boutique//HE"


def _escape(value: str) -> str:
    """RFC 5545 §3.3.11 TEXT escaping. The comma is the one that matters in
    practice: «רחוב דיזנגוף 99, תל אביב» is an ordinary Israeli address, and a
    raw comma inside a TEXT value splits it into two values.

    Backslash FIRST, or the escapes escape each other.
    """
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def _fold(line: str) -> str:
    """Fold to 75 octets per line, splitting only between CHARACTERS.

    A byte-slice fold is the tempting version and it cuts UTF-8 sequences in
    half, which reaches her calendar as mojibake rather than as an error. The
    continuation line's leading space counts toward its own 75, hence the
    reduced budget after the first segment.
    """
    segments: list[str] = []
    current: list[str] = []
    used = 0
    budget = ICS_MAX_OCTETS
    for char in line:
        size = len(char.encode("utf-8"))
        if used + size > budget:
            segments.append("".join(current))
            current = []
            used = 0
            budget = ICS_MAX_OCTETS - 1
        current.append(char)
        used += size
    segments.append("".join(current))
    return (CRLF + " ").join(segments)


def _instant(value: datetime.datetime) -> str:
    return value.astimezone(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")


def build_ics(
    booking: Booking,
    *,
    duration_minutes: int,
    boutique_name: str,
    address: str | None,
    slug: str,
    base_domain: str,
    now: datetime.datetime,
) -> str:
    """One VEVENT for one booking.

    `duration_minutes` is passed in rather than read here because it lives on
    `appointment_types` and must be read REGARDLESS of that row's `deleted_at`:
    an archived type still says how long the fitting she booked runs, and a
    fallback constant would quietly mis-state somebody's afternoon.

    `now` is an argument so DTSTAMP is deterministic under a frozen clock.
    """
    ends_at = booking.starts_at + datetime.timedelta(minutes=duration_minutes)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        # Stable across downloads, so re-adding UPDATES the entry instead of
        # duplicating it, and namespaced by tenant host so two boutiques cannot
        # collide inside one person's calendar.
        f"UID:{booking.id}@{slug}.{base_domain}",
        f"DTSTAMP:{_instant(now)}",
        f"DTSTART:{_instant(booking.starts_at)}",
        f"DTEND:{_instant(ends_at)}",
        f"SUMMARY:{_escape(f'{booking.appointment_type_name} — {boutique_name}')}",
    ]
    if address:
        # OMITTED and never empty when there is no address: clients render a
        # blank LOCATION, and some map it to «unknown location».
        lines.append(f"LOCATION:{_escape(address)}")
    lines += ["STATUS:CONFIRMED", "END:VEVENT", "END:VCALENDAR"]
    return CRLF.join(_fold(line) for line in lines) + CRLF
