"""The manage link's credential: minted once per booking, stored as sha256 only,
compared in constant time.

Reuses the `otp_codes` mint-hash-compare primitives rather than inventing a
second token scheme — `generate_session_token()` is 32 random bytes (43 urlsafe
characters), comfortably past the epic's >=128-bit floor, and the budget
arithmetic in `comms_templates.py` is written against exactly that length.
"""

import hmac

from app.auth.tokens import generate_session_token, hash_token


def mint_manage_token() -> str:
    return generate_session_token()


def manage_token_hash(raw: str) -> str:
    return hash_token(raw)


def manage_token_matches(raw: str, stored_hash: str | None) -> bool:
    """The final gate after the indexed lookup, and it is deliberately redundant.

    `BookingsRepository.by_manage_token_hash` selects on an equality against this
    same hash, so a returned row has already matched. That is the point: if the
    predicate is ever widened — a prefix match, a `LIKE`, a join that loses its
    tenant clause — this comparison is what stops the widened query from handing
    back a booking whose token the caller does not hold. `compare_digest` because
    both sides are attacker-influenced hex and a length-dependent `==` on a
    credential check is a habit worth not having.
    """
    if stored_hash is None:
        return False
    return hmac.compare_digest(manage_token_hash(raw), stored_hash)
