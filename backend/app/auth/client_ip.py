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

⚠ AND THIS FILE DID THAT ITSELF, ON ITS LAST LINE, until the 2026-08-05 review.
With `trust_forwarded_for` on and no `X-Forwarded-For` present it fell back to
`request.client.host` — the socket peer, which on the deployment this setting
describes is the proxy. That is precisely "a single global bucket that reads as
working", in the file whose stated purpose is to prevent it, reachable on any
request that skips the proxy. The fallback is now `None`.

`None` and not the peer address, deliberately: the premise of
`TRUST_FORWARDED_FOR=true` is that exactly one trusted proxy appends the header,
so a request arriving without it is one that BYPASSED the proxy, and its peer
address is not a fact this module can vouch for. Callers already treat `None` as
"skip the per-IP budget" (`notifications/service.py`'s `ip_key`), so the failure
mode is one budget not metering rather than every customer sharing one.
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
    if not forwarded:
        return None
    return forwarded.split(",")[-1].strip()
