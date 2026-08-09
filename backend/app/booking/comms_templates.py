"""The four Hebrew lifecycle SMS bodies, plus the segment budget that keeps them
affordable and the mask that keeps the manage token out of the evidence trail.

Pure: nothing here imports from `app/db`, opens a session or reaches a sender, so
every rule below is unit-testable with no I/O. Wording comes verbatim from
`.planning/design/screens/manage-booking/copy.md` (APPROVED — Interview Q5);
**counsel signs the bodies off before a real provider goes live**, which is a
pre-provider gate and not a pre-merge one (Amendment 40 posture).

Deliberately NOT env-tunable, per the house rule that `Settings` carries
deployment identity and never product policy.
"""

import datetime

from app.notifications.validation import MASK_CHAR
from app.storefront.validation import BOUTIQUE_TIMEZONE

# --- budget -----------------------------------------------------------------

# A Hebrew body is UCS-2 on the wire: 70 characters in a single message, 67 once
# the provider has to concatenate (6 of the 70 go to the UDH). "Characters" means
# UTF-16 code units, so an astral character costs two.
UCS2_SINGLE_LIMIT = 70
UCS2_CONCAT_LIMIT = 67

# Three segments is the ceiling every body is designed against. It is a cost
# ceiling, not a correctness one — a fourth segment sends fine and bills again.
CONFIRMATION_MAX_SEGMENTS = 3
REMINDER_MAX_SEGMENTS = 3
OWNER_CANCEL_MAX_SEGMENTS = 3
OWNER_RESCHEDULE_MAX_SEGMENTS = 3
PAYMENT_RECEIVED_NO_SLOT_MAX_SEGMENTS = 3
# F23's offer, at parity with the reminder: prefix 101 UCS-2 units at a 25-char
# truncated name and the longest weekday, link 97 at the documented 30-char slug
# budget.
WAITLIST_OFFER_MAX_SEGMENTS = 3

# tenants.name is unbounded TEXT, but the arithmetic above assumes ~25 characters
# of it. Truncating here is the only way production matches the tested fixture
# (Interview pre-decided #8, discharging design finding F-M3).
BOUTIQUE_NAME_MAX_CHARS = 25

# The slug length the budget assumes. `is_valid_slug` permits a 63-character DNS
# label, which pushes the confirmation body to a fourth segment — a documented
# ceiling, not a guarantee. Capping slug length belongs to F6's provisioning
# surface, and refusing to boot on a legitimate slug would be worse than one
# extra segment. Pinned by a test so an invoice is never how this is discovered.
MANAGE_LINK_SLUG_BUDGET_CHARS = 30

# What replaces the raw token in `log_body` (D2) — the same glyph the OTP mask and
# the UI use for a concealed value.
MASKED_TOKEN = MASK_CHAR * 3

# Sunday-first is the Israeli week, but datetime.weekday() is Monday-first, so
# this tuple is indexed by weekday() directly rather than reordered at the call
# site. Hand-rolled and not `locale`-dependent: every body must read the same on
# the CI runner, on a laptop and in Israel.
_WEEKDAY_WORDS = ("שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון")


def ucs2_segments(body: str) -> int:
    """How many SMS segments `body` costs as UCS-2."""
    units = sum(2 if ord(char) > 0xFFFF else 1 for char in body)
    if units <= UCS2_SINGLE_LIMIT:
        return 1
    return -(-units // UCS2_CONCAT_LIMIT)  # ceil, without importing math


def truncate_boutique_name(name: str) -> str:
    # rstrip after the slice: a cut landing mid-word often leaves a trailing
    # space, and every body puts a colon or a comma immediately after the name.
    return name[:BOUTIQUE_NAME_MAX_CHARS].rstrip()


# --- the link ---------------------------------------------------------------


def manage_link(*, slug: str, base_domain: str, token: str) -> str:
    """`/b/{token}` on the tenant's own storefront host.

    The short path is deliberate (D7): the alternative spends ~14 extra UCS-2
    characters per SMS forever. Always https, dev `base_domain` included — a real
    SMS may not carry a cleartext link, and the fake sender sends nothing anyway.
    """
    return f"https://{slug}.{base_domain}/b/{token}"


def mask_manage_link(body: str, token: str) -> str:
    """What `message_log` stores. `bookings` keeps only the token's sha256, so
    persisting the raw token in the forever-table beside its own hash would
    defeat the hashed storage completely — identical reasoning, and identical
    mechanism, to `mask_otp_body`."""
    return body.replace(token, MASKED_TOKEN)


# --- zoned rendering --------------------------------------------------------


def jerusalem_weekday(instant: datetime.datetime) -> str:
    """The bare day word, so «ליום {weekday}» reads correctly for שבת too."""
    return _WEEKDAY_WORDS[instant.astimezone(BOUTIQUE_TIMEZONE).weekday()]


def jerusalem_date(instant: datetime.datetime) -> str:
    local = instant.astimezone(BOUTIQUE_TIMEZONE)
    return f"{local.day}.{local.month}.{local.year}"


def jerusalem_time(instant: datetime.datetime) -> str:
    local = instant.astimezone(BOUTIQUE_TIMEZONE)
    return f"{local.hour:02d}:{local.minute:02d}"


def _when(instant: datetime.datetime) -> tuple[str, str, str]:
    return jerusalem_weekday(instant), jerusalem_date(instant), jerusalem_time(instant)


# --- the fifth body ---------------------------------------------------------

# F19 MD2, verbatim from the spec's decision block. A CONSTANT and not a
# function because it takes nothing: the four bodies above are parameterised by
# facts the copy deck approved them to state, and prefixing this one with the
# boutique name would be inventing copy MD2 did not approve.
#
# What it is allowed to say is the whole point, and MD2 fixed it: it promises no
# refund (MD1 keeps the deposit against a new appointment, and D16 writes no
# refund_due row), it names no new time (race row #15 is the bride who already
# rebooked herself, for whom "we will arrange a new time" is false), and it
# claims nothing has already been done (it is sent from the branch where the
# rebind did NOT happen). "We will get back to you shortly" is true in both
# races, and the specific remedy is the owner's to say on the phone.
PAYMENT_RECEIVED_NO_SLOT_BODY = (
    "התשלום שלך התקבל. המועד שבחרת כבר נתפס, והפיקדון שמור עבורך — נחזור אליך בהקדם."
)


# --- the four bodies --------------------------------------------------------


def confirmation_sms_body(
    *, boutique_name: str, starts_at: datetime.datetime, manage_url: str
) -> str:
    """Sent immediately after a booking commits.

    **No location line.** The design gate struck it: one body cannot honestly
    carry both unbounded tenant free-text and the manage link inside three
    segments, and the manage page's ContactPanel carries maps/waze anyway — so
    the link she gets leads to the location.
    """
    weekday, date, time = _when(starts_at)
    return (
        f"{truncate_boutique_name(boutique_name)}: "
        f"התור נקבע ליום {weekday}, {date} בשעה {time}. "
        f"לצפייה, אישור הגעה או ביטול: {manage_url}"
    )


def reminder_sms_body(*, boutique_name: str, starts_at: datetime.datetime, manage_url: str) -> str:
    """One body for all three D3 bands.

    It carries no «מחר»: Interview Q4 rules that a booking made under 24 hours
    out gets its reminder IMMEDIATELY, so "tomorrow" would be false for the
    2-24h band on a same-day booking. The weekday and the date carry the timing
    instead, which is also what makes a reminder that fires late still honest —
    the body renders from `starts_at`, never from "in 24 hours".
    """
    weekday, date, time = _when(starts_at)
    return (
        f"{truncate_boutique_name(boutique_name)}: "
        f"תזכורת — התור שלך ביום {weekday}, {date} בשעה {time}. "
        f"לאישור הגעה או ביטול: {manage_url}"
    )


def offer_link(*, slug: str, base_domain: str, token: str) -> str:
    """`/w/{token}` — `manage_link`'s sibling, one letter apart on purpose.

    Same short path for the same reason (D7): the alternative spends ~14 extra
    UCS-2 characters per SMS forever. `mask_manage_link` masks this one too — it
    replaces the TOKEN, not the path, so one function covers both link shapes.
    """
    return f"https://{slug}.{base_domain}/w/{token}"


def waitlist_offer_sms_body(
    *,
    boutique_name: str,
    slot_starts_at: datetime.datetime,
    deadline: datetime.datetime,
    sent_at: datetime.datetime,
    offer_url: str,
) -> str:
    """F23's offer — the fifth lifecycle body.

    **The deadline is ABSOLUTE, never «בעוד שעתיים».** The reminder's own rule:
    a body renders from an instant, never from an offset, because an SMS read
    forty minutes late makes a relative claim false. The two-hour window is a
    SETTING; the clock time is a FACT.

    **F-O1 — the weekday is appended when the deadline falls on another day.**
    At the shipped defaults the deadline cannot cross midnight (the cascade stops
    issuing at 21:00 and the window is two hours, so 22:59 is the latest), which
    is what lets it render as a bare `HH:MM`. That guarantee is a function of
    `waitlist_offer_window_seconds`: raise it past ~3h and a 20:30 offer expires
    TOMORROW while the body still reads as today. One comparison of Jerusalem
    calendar dates removes the whole class of support call, and it costs nothing
    on the default path because the branch is never taken there.

    No send-promise, no «נשלח רק אלייך», no «נותרו רק» and NO EXCLAMATION MARK.
    The cascade offers sequentially (#13), but the bride is owed no statement
    about other brides, and urgency is the one register this product does not
    use.
    """
    weekday, date, time = _when(slot_starts_at)
    # Against the SEND day, not the slot's: "until 00:30" is ambiguous to
    # somebody reading it at 22:45 tonight, and the slot may be weeks away.
    same_day = (
        deadline.astimezone(BOUTIQUE_TIMEZONE).date()
        == sent_at.astimezone(BOUTIQUE_TIMEZONE).date()
    )
    until = (
        jerusalem_time(deadline)
        if same_day
        else f"יום {jerusalem_weekday(deadline)} {jerusalem_time(deadline)}"
    )
    return (
        f"{truncate_boutique_name(boutique_name)}: "
        f"התפנה תור ביום {weekday}, {date} בשעה {time}. "
        f"שמור עבורך עד {until}, לאישור: {offer_url}"
    )


def owner_cancel_sms_body(
    *, boutique_name: str, starts_at: datetime.datetime, boutique_phone: str | None
) -> str:
    """F15's seam. States the cancellation and points at the phone — and states
    NO refund or forfeit outcome, because E4 #19 is what will be able to compute
    one. The clause is dropped entirely when the boutique published no phone: a
    freshly provisioned tenant has every profile field null, and «לשאלות:»
    followed by nothing is worse than a shorter sentence."""
    date = jerusalem_date(starts_at)
    body = f"{truncate_boutique_name(boutique_name)}: התור שלך בתאריך {date} בוטל על ידי הבוטיק."
    if boutique_phone is None:
        return body
    return f"{body} לשאלות ולתיאום מחדש: {boutique_phone}"


def owner_reschedule_sms_body(
    *, boutique_name: str, starts_at: datetime.datetime, manage_url: str
) -> str:
    """F15's other seam. `starts_at` is the NEW time, and the link is the same
    manage link — the page renders the moved appointment's facts."""
    weekday, date, time = _when(starts_at)
    return (
        f"{truncate_boutique_name(boutique_name)}: "
        f"התור שלך הועבר ליום {weekday}, {date} בשעה {time}. "
        f"לצפייה ולאישור: {manage_url}"
    )
