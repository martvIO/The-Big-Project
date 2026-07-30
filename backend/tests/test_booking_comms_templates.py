"""F16's pure template layer: the four Hebrew lifecycle bodies, the UCS-2
segment budget, the boutique-name truncation and the token mask.

Nothing here touches a database or a sender. Every assertion is about a rule the
copy deck or the spec fixed, and the two that matter most are mechanical: a body
that quietly grows to a fourth segment costs the boutique real money on every
send, and a body that leaks the raw manage token into `log_body` defeats the
hashed storage on `bookings`.
"""

import datetime

import pytest

from app.booking.comms_templates import (
    BOUTIQUE_NAME_MAX_CHARS,
    CONFIRMATION_MAX_SEGMENTS,
    MANAGE_LINK_SLUG_BUDGET_CHARS,
    MASKED_TOKEN,
    OWNER_CANCEL_MAX_SEGMENTS,
    OWNER_RESCHEDULE_MAX_SEGMENTS,
    REMINDER_MAX_SEGMENTS,
    UCS2_CONCAT_LIMIT,
    UCS2_SINGLE_LIMIT,
    confirmation_sms_body,
    jerusalem_date,
    jerusalem_time,
    jerusalem_weekday,
    manage_link,
    mask_manage_link,
    owner_cancel_sms_body,
    owner_reschedule_sms_body,
    reminder_sms_body,
    truncate_boutique_name,
    ucs2_segments,
)

# The documented worst case, from the spec's Named-constants row: a 30-char slug,
# a 43-char token (generate_session_token's length), the real production domain,
# a boutique name at the 25-char bound and a two-digit day in a two-digit month.
WORST_SLUG = "a" * MANAGE_LINK_SLUG_BUDGET_CHARS
WORST_TOKEN = "T" * 43
WORST_DOMAIN = "modryn.co.il"
WORST_NAME = "ב" * BOUTIQUE_NAME_MAX_CHARS
# Wednesday 31.12.2026, 22:45 Jerusalem — the longest weekday words are 5 chars
# and the longest date is 10.
WORST_INSTANT = datetime.datetime(2026, 12, 31, 20, 45, tzinfo=datetime.UTC)

WORST_LINK = manage_link(slug=WORST_SLUG, base_domain=WORST_DOMAIN, token=WORST_TOKEN)


def _worst_confirmation() -> str:
    return confirmation_sms_body(
        boutique_name=WORST_NAME, starts_at=WORST_INSTANT, manage_url=WORST_LINK
    )


def _worst_reminder() -> str:
    return reminder_sms_body(
        boutique_name=WORST_NAME, starts_at=WORST_INSTANT, manage_url=WORST_LINK
    )


# --- the link ---------------------------------------------------------------


def test_manage_link_is_the_short_https_path_the_spec_pinned() -> None:
    # /b/{token}, not /manage-booking/{token}: D7 spends the shorter path
    # deliberately, because every character rides inside a UCS-2 Hebrew SMS.
    assert manage_link(slug="bella", base_domain="modryn.co.il", token="abc") == (
        "https://bella.modryn.co.il/b/abc"
    )


def test_manage_link_is_never_http() -> None:
    """A real SMS may not carry a cleartext link, dev base_domain included."""
    assert manage_link(slug="bella", base_domain="localtest.me", token="abc").startswith("https://")


# --- boutique name truncation (pre-decided #8 / design finding F-M3) --------


def test_a_long_boutique_name_is_truncated_to_the_budget() -> None:
    name = "הבוטיק של ורד — שמלות כלה בעבודת יד ותפירה אישית"
    truncated = truncate_boutique_name(name)
    assert len(truncated) <= BOUTIQUE_NAME_MAX_CHARS
    assert name.startswith(truncated)


def test_truncation_does_not_leave_a_dangling_space() -> None:
    # 25 characters landing mid-word would otherwise render "בוטיק ורד ה :" —
    # the colon that follows in every body must sit against a word.
    assert truncate_boutique_name("א" * 24 + " " + "ב" * 10) == "א" * 24


def test_a_short_name_is_untouched() -> None:
    assert truncate_boutique_name("בלה כלות") == "בלה כלות"


# --- zoned rendering -------------------------------------------------------


def test_instants_render_in_the_boutiques_zone_not_utc() -> None:
    """23:30 UTC on 3 August is 02:30 on 4 August in Jerusalem — a UTC render
    would put a bride's appointment on the wrong day and the wrong weekday."""
    instant = datetime.datetime(2026, 8, 3, 23, 30, tzinfo=datetime.UTC)
    assert jerusalem_date(instant) == "4.8.2026"
    assert jerusalem_time(instant) == "02:30"
    assert jerusalem_weekday(instant) == "שלישי"


def test_saturday_reads_as_a_day_word_too() -> None:
    # "ליום שבת" — the templates prefix «ליום», so the Saturday word must work
    # in that frame without a special case at the call site.
    saturday = datetime.datetime(2026, 8, 8, 9, 0, tzinfo=datetime.UTC)
    assert jerusalem_weekday(saturday) == "שבת"


# --- the segment budget ----------------------------------------------------


def test_segment_counting_uses_utf16_code_units() -> None:
    assert ucs2_segments("") == 1
    assert ucs2_segments("א" * UCS2_SINGLE_LIMIT) == 1
    assert ucs2_segments("א" * (UCS2_SINGLE_LIMIT + 1)) == 2
    assert ucs2_segments("א" * (UCS2_CONCAT_LIMIT * 2)) == 2
    assert ucs2_segments("א" * (UCS2_CONCAT_LIMIT * 2 + 1)) == 3


def test_an_astral_character_costs_two_units() -> None:
    """UCS-2 is UTF-16: a surrogate pair is two units, not one. Nothing in the
    approved copy uses one, and this is what keeps that true if anything ever
    tries to."""
    assert ucs2_segments("😀" * 35) == 1
    assert ucs2_segments("😀" * 36) == 2


def test_the_confirmation_clears_its_budget_at_the_worst_case() -> None:
    body = _worst_confirmation()
    assert ucs2_segments(body) <= CONFIRMATION_MAX_SEGMENTS, body


def test_the_reminder_clears_its_budget_at_the_worst_case() -> None:
    body = _worst_reminder()
    assert ucs2_segments(body) <= REMINDER_MAX_SEGMENTS, body


def test_the_owner_bodies_clear_their_budgets_at_the_worst_case() -> None:
    cancel = owner_cancel_sms_body(
        boutique_name=WORST_NAME, starts_at=WORST_INSTANT, boutique_phone="+972501234567"
    )
    reschedule = owner_reschedule_sms_body(
        boutique_name=WORST_NAME, starts_at=WORST_INSTANT, manage_url=WORST_LINK
    )
    assert ucs2_segments(cancel) <= OWNER_CANCEL_MAX_SEGMENTS, cancel
    assert ucs2_segments(reschedule) <= OWNER_RESCHEDULE_MAX_SEGMENTS, reschedule


def test_the_slug_budget_is_a_documented_ceiling_not_a_guarantee() -> None:
    """is_valid_slug permits a 63-character DNS label, which pushes the body past
    three segments. Recorded rather than fixed (a boot guard on a legitimate slug
    would be worse than one extra segment) — this test is what keeps the ceiling
    from being discovered by an invoice."""
    long_link = manage_link(slug="a" * 63, base_domain=WORST_DOMAIN, token=WORST_TOKEN)
    over = confirmation_sms_body(
        boutique_name=WORST_NAME, starts_at=WORST_INSTANT, manage_url=long_link
    )
    assert ucs2_segments(over) == CONFIRMATION_MAX_SEGMENTS + 1
    assert MANAGE_LINK_SLUG_BUDGET_CHARS == 30


# --- body content ---------------------------------------------------------


@pytest.mark.parametrize("body", [_worst_confirmation(), _worst_reminder()])
def test_the_link_survives_the_body_intact(body: str) -> None:
    """A template that wrapped, trimmed or percent-escaped the URL would produce
    a link that looks right in a test and 404s on a phone."""
    assert WORST_LINK in body


def test_the_confirmation_carries_no_location_line() -> None:
    """The design gate dropped it: one body cannot honestly carry both unbounded
    tenant free-text and the manage link inside three segments. The manage page's
    ContactPanel carries maps/waze instead."""
    body = confirmation_sms_body(
        boutique_name="בלה", starts_at=WORST_INSTANT, manage_url="https://x.test/b/t"
    )
    assert "waze" not in body.lower()
    assert body.count("https://") == 1


def test_the_reminder_never_says_tomorrow_in_any_band() -> None:
    """Interview Q4: under 24h notice the reminder sends IMMEDIATELY, so «מחר»
    is false for the 2-24h band on a same-day booking. One date-led body serves
    every band, and the weekday plus the date carry the timing instead."""
    body = reminder_sms_body(
        boutique_name="בלה", starts_at=WORST_INSTANT, manage_url="https://x.test/b/t"
    )
    assert "מחר" not in body
    assert jerusalem_weekday(WORST_INSTANT) in body
    assert jerusalem_date(WORST_INSTANT) in body
    assert jerusalem_time(WORST_INSTANT) in body


def test_no_body_carries_a_money_word_before_e4() -> None:
    """Amendment 40 posture plus the E4 seam: owner-cancel states the
    cancellation and points at the phone, and states no refund or forfeit until
    E4 #19 exists to compute one."""
    bodies = [
        _worst_confirmation(),
        _worst_reminder(),
        owner_cancel_sms_body(
            boutique_name="בלה", starts_at=WORST_INSTANT, boutique_phone="+972501234567"
        ),
        owner_reschedule_sms_body(
            boutique_name="בלה", starts_at=WORST_INSTANT, manage_url="https://x.test/b/t"
        ),
    ]
    for body in bodies:
        for word in ("₪", "החזר", "מקדמה", "חיוב", "תשלום"):
            assert word not in body, f"{word!r} reached {body!r}"


def test_owner_cancel_drops_its_contact_clause_when_no_phone_is_published() -> None:
    """A freshly provisioned tenant has every profile field null, and «לשאלות:»
    followed by nothing is worse than a shorter sentence."""
    body = owner_cancel_sms_body(boutique_name="בלה", starts_at=WORST_INSTANT, boutique_phone=None)
    assert "לשאלות" not in body
    assert body.endswith("בוטל על ידי הבוטיק.")


# --- the mask (D2) -------------------------------------------------------


def test_the_masked_body_keeps_the_prose_and_drops_the_token() -> None:
    """message_log lives forever and bookings stores only the token's sha256 —
    storing the raw token in the evidence row beside its own hash would defeat
    the hashed storage entirely. Same mechanism and same glyph as OTP masking."""
    body = _worst_confirmation()
    masked = mask_manage_link(body, WORST_TOKEN)
    assert WORST_TOKEN not in masked
    assert MASKED_TOKEN in masked
    # Everything except the token is retained: the Spam-Law evidence value is
    # "this body went to this phone at this time".
    assert masked.startswith(WORST_NAME)
    assert f"/b/{MASKED_TOKEN}" in masked


def test_masking_a_body_that_never_held_the_token_is_a_no_op() -> None:
    body = owner_cancel_sms_body(
        boutique_name="בלה", starts_at=WORST_INSTANT, boutique_phone="+972501234567"
    )
    assert mask_manage_link(body, WORST_TOKEN) == body
