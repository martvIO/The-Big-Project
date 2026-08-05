"""The one derivation of a request's real client address.

⚠ IT RETURNS `None` ON EVERY DEPLOYMENT WE CURRENTLY HAVE, AND THAT IS THE POINT
OF READING IT HERE RATHER THAN INFERRING IT. `trust_forwarded_for` ships `False`
(`core/config.py:37`), so every caller below gets `None` and every per-IP budget
in this codebase is INERT until that setting flips. `TRUST_FORWARDED_FOR=true` is
only correct on a deployment that terminates exactly one trusted proxy which
appends `X-Forwarded-For` — that is a host fact, not a code change, and F21
deliberately does not flip it. Enablement is the parked `F62` entry's, alongside
the distributed (Redis) limiter that makes any of these budgets survive a second
worker process.

Extracted from `auth/router.py` by F21 (Task 9) rather than copied. Two call
sites disagreeing about how the real client address is derived is precisely the
bug class the comment below warns about: one of them would eventually start
trusting `request.client.host` unconditionally, and the budget keyed on it would
collapse to a single global bucket that reads as working.
"""

from fastapi import Request


def client_ip(request: Request, trust_forwarded_for: bool) -> str | None:
    # Per-IP limiting is only meaningful with the REAL client IP. Without a trusted
    # proxy that appends XFF, request.client.host is the proxy → a global bucket, so
    # we skip the per-IP key entirely (None). With one trusted proxy hop, the last
    # XFF entry is the client the proxy saw.
    if not trust_forwarded_for:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else None
