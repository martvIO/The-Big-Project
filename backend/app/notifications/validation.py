"""OTP and phone constants + pure helpers. Deliberately not env-tunable (the
F8/F10 rule: `Settings` carries deployment identity, never product policy) —
except the send rate-limit windows, which follow the login/presign precedent
and live in `Settings` for incident tuning.
"""

import re
import secrets

from app.errors import DomainValidationError

OTP_CODE_LENGTH = 6
# Epic requirement: ≤ 5 minutes.
OTP_TTL_SECONDS = 300
# 5 guesses against 10^6 codes ≈ 0.0005% per code; the row-tracked counter is
# the real brute-force control, not the hash.
OTP_MAX_VERIFY_ATTEMPTS = 5
# Long enough to finish the booking form, short enough that an abandoned token
# dies before the slot picker goes stale.
VERIFICATION_TOKEN_TTL_SECONDS = 600

# After normalization: +972 5X XXXXXXX — Israeli mobiles only, deliberately.
# The pilot is Israeli, the SMS route is Israeli, and a wrong-country send is
# pure cost. Same derivation family as waPhone in apps/storefront/src/lib/contact.ts.
_NORMALIZED_MOBILE = re.compile(r"^\+9725\d{8}$")
_ALLOWED_CHARSET = re.compile(r"^\+?[0-9 ()\-]+$")

MASK_CHAR = "●"  # ● — same glyph the UI uses for concealed values


def normalize_israeli_mobile(raw: str) -> str:
    """Accept the ways a human types an Israeli mobile; return E.164 or raise.

    At most one leading '+', then digits/space/()/-; '05X…' gains 972, '9725X…'
    gains '+'. Anything else — landlines, foreign numbers, junk — is a domain
    400, because storing an unreachable phone strands the customer behind an
    SMS link that can never arrive.
    """
    candidate = raw.strip()
    if not candidate or not _ALLOWED_CHARSET.fullmatch(candidate):
        raise DomainValidationError("Enter a valid Israeli mobile number.")
    digits = re.sub(r"\D", "", candidate)
    if digits.startswith("05"):
        digits = "972" + digits[1:]
    normalized = "+" + digits
    if not _NORMALIZED_MOBILE.fullmatch(normalized):
        raise DomainValidationError("Enter a valid Israeli mobile number.")
    return normalized


def generate_otp_code() -> str:
    return f"{secrets.randbelow(10**OTP_CODE_LENGTH):0{OTP_CODE_LENGTH}d}"


def otp_sms_body(code: str) -> str:
    # Transactional-only wording; the template set gets a counsel read before
    # the real provider goes live (spec: Amendment 40 note).
    return f"קוד האימות שלך: {code}"


def mask_otp_body(body: str, code: str) -> str:
    """What message_log stores for kind='otp'. The log lives forever, the code
    is worthless in five minutes, and the Spam-Law evidence value is "an OTP
    was sent to this phone at this time" — never the digits."""
    return body.replace(code, MASK_CHAR * OTP_CODE_LENGTH)
