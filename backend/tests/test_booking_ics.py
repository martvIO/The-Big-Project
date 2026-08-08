"""F24 D5's `.ics` builder — pure, stdlib, no database and no HTTP.

Four things here are the whole reason this is its own module.

**UTC instants and no VTIMEZONE.** Israel switches between IST (+02:00) and IDT
(+03:00), and a VTIMEZONE block hand-written against one of them is wrong for
half the year. An absolute `…Z` instant is DST-proof and every calendar client
renders it in the reader's local wall clock — so the summer and winter cases
below are not two spellings of one assertion, they are the assertion.

**DTEND is arithmetic, not a field.** A booking has no end time (F12): the
duration lives on `appointment_types.duration_minutes`, read regardless of the
type's `deleted_at`, because an archived type still says how long the fitting
she booked runs.

**Folding is octets, not characters.** RFC 5545 folds at 75 OCTETS, and Hebrew
is two octets per letter — a character-counted fold produces lines a strict
parser rejects, and a naive byte slice can cut a UTF-8 sequence in half and
produce mojibake in her calendar.

**No capability in the file.** `.ics` files get forwarded and synced into shared
calendars; a manage token inside one hands control of the booking to whoever the
invite reached.
"""

import datetime
import uuid

from app.booking.ics import ICS_MAX_OCTETS, build_ics
from app.models.booking import Booking
from app.models.constants import BookingStatus

SLUG = "bella"
BASE_DOMAIN = "modryn.co.il"
NOW = datetime.datetime(2026, 7, 28, 9, 30, tzinfo=datetime.UTC)
BOOKING_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")
MANAGE_TOKEN = "mt-supersecret-capability-value"


def _booking(
    starts_at: datetime.datetime,
    *,
    type_name: str = "מדידה ראשונה",
    status: str = BookingStatus.CONFIRMED.value,
) -> Booking:
    booking = Booking()
    booking.id = BOOKING_ID
    booking.starts_at = starts_at
    booking.status = status
    booking.appointment_type_name = type_name
    # A row that genuinely carries a live link, so the no-token assertion has
    # something to find rather than proving an absence twice.
    booking.manage_token_hash = MANAGE_TOKEN
    return booking


def _build(booking: Booking, **overrides: object) -> str:
    kwargs: dict[str, object] = {
        "duration_minutes": 60,
        "boutique_name": "בלה כלות",
        "address": "רחוב דיזנגוף 99, תל אביב",
        "slug": SLUG,
        "base_domain": BASE_DOMAIN,
        "now": NOW,
    }
    kwargs.update(overrides)
    return build_ics(booking, **kwargs)  # type: ignore[arg-type]


def _unfold(text: str) -> list[str]:
    """RFC 5545 unfolding: a CRLF followed by a single space continues the
    previous line. Assertions about VALUES run on unfolded content; assertions
    about the WIRE run on the raw text."""
    return text.replace("\r\n ", "").split("\r\n")


def _value(text: str, prop: str) -> str | None:
    for line in _unfold(text):
        if line.startswith(f"{prop}:"):
            return line[len(prop) + 1 :]
    return None


# --- the instants -----------------------------------------------------------


def test_a_summer_idt_booking_is_the_right_utc_instant() -> None:
    """10:00 Jerusalem in August is 07:00Z — the +03:00 IDT offset. A builder
    that emitted local wall-clock digits with a Z suffix would put her fitting
    three hours early in every calendar on earth."""
    text = _build(_booking(datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC)))
    assert _value(text, "DTSTART") == "20260802T070000Z"
    assert _value(text, "DTEND") == "20260802T080000Z"


def test_a_winter_ist_booking_is_the_right_utc_instant() -> None:
    """10:00 Jerusalem in January is 08:00Z — +02:00. Same builder, no branch:
    the input is already an instant, which is exactly why no VTIMEZONE block is
    needed or wanted."""
    text = _build(_booking(datetime.datetime(2027, 1, 12, 8, 0, tzinfo=datetime.UTC)))
    assert _value(text, "DTSTART") == "20270112T080000Z"
    assert _value(text, "DTEND") == "20270112T090000Z"


def test_dtend_is_starts_at_plus_the_types_duration() -> None:
    text = _build(
        _booking(datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC)), duration_minutes=90
    )
    assert _value(text, "DTEND") == "20260802T083000Z"


def test_dtstamp_is_the_supplied_now_in_utc() -> None:
    text = _build(_booking(datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC)))
    assert _value(text, "DTSTAMP") == "20260728T093000Z"


def test_a_non_utc_input_instant_is_converted_and_not_relabelled() -> None:
    """Every timestamp in this codebase is an `Instant`, but a caller handing in
    a +03:00-tagged datetime must still produce the same UTC digits — the
    conversion is real, not a suffix."""
    tagged = datetime.datetime(
        2026, 8, 2, 10, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=3))
    )
    assert _value(_build(_booking(tagged)), "DTSTART") == "20260802T070000Z"


# --- the wire format --------------------------------------------------------


def test_every_line_ends_with_crlf_and_the_file_does_too() -> None:
    text = _build(_booking(datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC)))
    assert text.endswith("\r\n")
    assert "\n" not in text.replace("\r\n", "")
    assert text.startswith("BEGIN:VCALENDAR\r\n")
    assert "BEGIN:VEVENT\r\n" in text
    assert text.rstrip("\r\n").endswith("END:VCALENDAR")


def test_no_line_exceeds_seventy_five_octets_even_in_hebrew() -> None:
    """Hebrew is two octets per letter, so a character-counted fold passes a
    naive test and ships lines a strict parser rejects."""
    long_name = "מדידה ראשונה עם התאמות אישיות לשמלת הכלה ולתכשיטים הנלווים אליה"
    text = _build(
        _booking(datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC), type_name=long_name),
        boutique_name="בוטיק בלה כלות של רחוב דיזנגוף בתל אביב",
    )
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= ICS_MAX_OCTETS, line


def test_folding_survives_a_round_trip_through_unfolding() -> None:
    """The fold must never cut a UTF-8 sequence: unfolding has to give back the
    exact Hebrew that went in."""
    long_name = "מדידה ראשונה עם התאמות אישיות לשמלת הכלה ולתכשיטים הנלווים אליה"
    text = _build(
        _booking(datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC), type_name=long_name)
    )
    summary = _value(text, "SUMMARY")
    assert summary is not None
    assert long_name in summary
    assert "בלה כלות" in summary


def test_text_values_escape_the_separators_ics_reserves() -> None:
    """An address with a comma is ordinary in Israel and a raw comma inside a
    TEXT value splits it into two values — the boutique's street number becomes
    a second location."""
    text = _build(
        _booking(datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC)),
        address="Dizengoff 99, Tel Aviv; floor 2",
        boutique_name="Bella, Bridal",
    )
    assert _value(text, "LOCATION") == "Dizengoff 99\\, Tel Aviv\\; floor 2"
    summary = _value(text, "SUMMARY")
    assert summary is not None and "Bella\\, Bridal" in summary


# --- the contents -----------------------------------------------------------


def test_the_uid_is_the_booking_under_the_tenant_host() -> None:
    """Stable across downloads, so re-adding updates the same calendar entry
    instead of duplicating it, and namespaced by tenant host so two boutiques
    cannot collide in one calendar."""
    text = _build(_booking(datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC)))
    assert _value(text, "UID") == f"{BOOKING_ID}@{SLUG}.{BASE_DOMAIN}"


def test_the_summary_names_the_appointment_and_the_boutique() -> None:
    text = _build(_booking(datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC)))
    assert _value(text, "SUMMARY") == "מדידה ראשונה — בלה כלות"


def test_status_is_confirmed_and_there_is_exactly_one_vevent() -> None:
    text = _build(_booking(datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC)))
    assert _value(text, "STATUS") == "CONFIRMED"
    assert text.count("BEGIN:VEVENT") == 1
    assert text.count("END:VEVENT") == 1


def test_location_is_omitted_entirely_when_the_boutique_has_no_address() -> None:
    """An empty LOCATION is worse than none: calendar clients render the blank
    field and some map it to «unknown location»."""
    text = _build(_booking(datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC)), address=None)
    assert _value(text, "LOCATION") is None
    assert "LOCATION" not in text


def test_the_file_carries_no_manage_token_anywhere() -> None:
    """The D5 rule, asserted on a booking whose row genuinely holds one: `.ics`
    files are forwarded and synced into shared calendars, and a capability
    inside one hands control of the appointment to whoever the invite reached."""
    booking = _booking(datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC))
    text = _build(booking)
    assert MANAGE_TOKEN not in text
    assert "token" not in text.lower()
    assert "/b/" not in text
