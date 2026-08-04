"""Named bounds for the privacy surface.

Deliberately NOT `Settings` fields: F8's rule is that `Settings` carries
deployment identity and never product policy, and the size of a legal document
is product policy. (The retention *periods* are the exception the plan argues
separately — they are an operator's policy dial, not a document's shape.)
"""

from app.errors import DomainValidationError

# The cap on ONE stored override — `notice_text` or `dpa_text` — measured in
# UTF-8 BYTES, because that is what Postgres stores and Hebrew is two bytes a
# character. A character cap would silently halve the allowance for the only
# language these documents are written in.
#
# 8 KB is chosen against the platform defaults it must hold: the longest is the
# collection notice at 3 746 bytes, so a boutique's own lawyer can roughly double
# it before hitting the wall. `test_privacy_text.py` asserts every default fits,
# which is what keeps the editor from prefilling text it would then refuse to
# save back.
MAX_PRIVACY_TEXT_BYTES = 8 * 1024

# The two placeholders a SCRUB writes in place of a person. They live here rather
# than in `retention.py` because the erase ENDPOINT (F20 C4) writes exactly the
# same pair, and `notifications/service.py` reads the prefix to refuse a send —
# three modules, one spelling, no import cycle through the retention registry.
#
# ASCII and one LTR run: an RTL console renders it with no bidi care at all, and
# the alternative (exposing `erased_at` on every owner row plus new manage copy)
# is two schema changes and a frontend change to say what one literal says.
ERASED_NAME = "[erased]"
# PER-ROW, never a constant: `idx_customers_tenant_phone_unique` is UNIQUE on
# (tenant_id, phone), so the placeholder is `erased:{id}`. A constant would make
# the SECOND row in a 500-row scrub chunk raise, roll the whole chunk back, and
# repeat that failure on every tick for every tenant past the clock, permanently.
# It is also un-sendable: `normalize_israeli_mobile` rejects it outright.
ERASED_PHONE_PREFIX = "erased:"

# The cap on the erase route's `reason`, in UTF-8 bytes, two orders of magnitude
# below the document caps because this field is prose about a DECISION, not a
# document. It lands in `audit_log`, which is exempt from every retention class
# forever (D19) — so anything typed here is permanent, and a field that invites
# a paragraph invites a paragraph about a named person.
MAX_ERASE_REASON_BYTES = 500

# The cap on a raw phone as TYPED, in characters, before
# `normalize_israeli_mobile` regexes it. A trust-boundary bound and not a format
# rule — the format rule is that function's, and it runs a `fullmatch` plus a
# `re.sub` over whatever arrives. 32 holds every shape a human types
# (`+972 50-123-4567`, `050 123 4567`) with room to spare, and stops a
# body-limit-sized string reaching the regex at all.
MAX_PHONE_INPUT_CHARS = 32

# The three subject budgets. Per-tenant, one instance each — never one limiter
# with three keys, which would give all three routes ONE shared ceiling
# (`.memory/patterns/limiter-max-is-per-instance`).
#
# NOT `Settings` fields, and the spec's own constants table is the authority:
# it enumerates every `Settings` key F20 adds — the retention clocks, which are
# an operator's policy dial with a counsel review behind them — and these are
# not among them. A ceiling nobody tunes per deployment is product policy, which
# F8's rule keeps out of `Settings`.
#
# None of these is a defence in the OTP sense: an authenticated owner can
# already read every booking in her console. They are runaway brakes on a route
# that assembles a whole person into one document and on one that destroys data
# irreversibly. Sized so a real morning of subject requests — even a busy one
# after a data-protection notice — cannot reach them.
SUBJECT_EXPORT_MAX_PER_WINDOW = 60
SUBJECT_EXPORT_WINDOW_SECONDS = 3600
SUBJECT_ERASE_MAX_PER_WINDOW = 30
SUBJECT_ERASE_WINDOW_SECONDS = 3600
MARKETING_WITHDRAW_MAX_PER_WINDOW = 120
MARKETING_WITHDRAW_WINDOW_SECONDS = 3600


class PrivacyThrottledError(Exception):
    """One of the three subject budgets is spent; main.py maps it to the shared
    TOO_MANY_ATTEMPTS 429.

    Its own class for the reason `StorefrontThrottledError`, `OtpThrottledError`
    and `CheckinThrottledError` each give in turn: unrelated budgets, unrelated
    keys, unrelated operational meanings. Reparenting every throttle error onto
    one base stays F21's behaviour-neutral cleanup.
    """


def validate_privacy_text(value: str, *, field: str) -> None:
    """The 8 KB cap on ONE stored override.

    BYTES, not characters, and the difference is not pedantic: these documents
    are written in Hebrew, which is two bytes a character in UTF-8, so a
    character cap would silently halve the allowance for the only language they
    exist in — and `len()` on the Python string is the character count.

    `field` is named in the message because the console edits two textareas on
    one form and submits both together (D16), so "too long" with no field is
    unactionable.
    """
    if len(value.encode("utf-8")) > MAX_PRIVACY_TEXT_BYTES:
        raise DomainValidationError(f"{field} is longer than {MAX_PRIVACY_TEXT_BYTES} bytes.")


def validate_erase_reason(value: str) -> None:
    """The 500-byte cap. Same byte-not-character argument as above; the operator
    writes this in Hebrew too."""
    if len(value.encode("utf-8")) > MAX_ERASE_REASON_BYTES:
        raise DomainValidationError(f"reason is longer than {MAX_ERASE_REASON_BYTES} bytes.")
