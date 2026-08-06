from starlette.responses import Response

SESSION_COOKIE = "boutique_session"
# F24's customer session, and a DIFFERENT NAME on purpose (spec D2). The
# storefront and the console live on the same tenant host, so both cookies ride
# every request to it: one shared name would let an owner signing into the
# console clobber her own customer session, and a bride's login clobber the
# console's. Two names, two dependencies, two lookup tables.
CUSTOMER_SESSION_COOKIE = "boutique_customer_session"

# F25 D3. Its OWN name beside the staff one rather than a shared cookie with a
# wider Domain: host-only scoping to admin.{base} already isolates it from every
# tenant host, but a distinct name means a leaked or misconfigured Domain
# attribute STILL cannot be resolved by the staff or customer lookups. Two
# independent reasons a stolen cookie fails, and neither is trusted alone.
_PLATFORM_SESSION_COOKIE = "boutique_platform_session"


def platform_session_cookie_name(secure: bool) -> str:
    """⚠ `__Host-` IS THE BROWSER-ENFORCED HALF OF D3, and the name alone was
    never the whole answer.

    A distinct name stops the platform cookie being READ by the staff or customer
    lookups. It does nothing about the cookie being PLANTED: script execution on
    any `*.modryn.co.il` host (a storefront XSS, a third-party embed, any deploy
    that Domain-scopes a cookie) can set `boutique_platform_session` for the
    parent domain, and admin. then receives two cookies of that name.
    `request.cookies.get` reads exactly one, browser's choice — either the
    operator's real session looks dead and cannot be cleared (logout deletes only
    the host cookie), or she works inside a session the attacker picked.

    The prefix makes that impossible rather than merely unhelpful: browsers refuse
    a `__Host-` cookie unless it is Secure, path=/ and Domain-less — exactly the
    attributes `_set` already emits — and refuse it from any host but the one
    setting it.

    CONDITIONAL ON `secure`, because the prefix REQUIRES Secure and dev serves
    *.localtest.me over plain http. An unconditional prefix would be a cookie the
    dev browser silently drops, which reads as "login does nothing".
    """
    return f"__Host-{_PLATFORM_SESSION_COOKIE}" if secure else _PLATFORM_SESSION_COOKIE


def _set(response: Response, name: str, token: str, *, secure: bool, max_age: int) -> None:
    # No Domain attribute → host-only cookie: a session minted at boutique A is
    # never sent to boutique B's subdomain. HttpOnly blocks JS theft; SameSite=Lax
    # blocks cross-site CSRF on the login/session cookie.
    #
    # ONE place for the attributes, shared by all three populations: three copies
    # of five security-relevant flags is how one of them quietly loses HttpOnly.
    response.set_cookie(
        name,
        token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def _clear(response: Response, name: str, *, secure: bool) -> None:
    response.delete_cookie(name, httponly=True, secure=secure, samesite="lax", path="/")


def set_session_cookie(response: Response, token: str, *, secure: bool, max_age: int) -> None:
    _set(response, SESSION_COOKIE, token, secure=secure, max_age=max_age)


def clear_session_cookie(response: Response, *, secure: bool) -> None:
    _clear(response, SESSION_COOKIE, secure=secure)


def set_customer_session_cookie(
    response: Response, token: str, *, secure: bool, max_age: int
) -> None:
    _set(response, CUSTOMER_SESSION_COOKIE, token, secure=secure, max_age=max_age)


def clear_customer_session_cookie(response: Response, *, secure: bool) -> None:
    _clear(response, CUSTOMER_SESSION_COOKIE, secure=secure)


def set_platform_session_cookie(
    response: Response, token: str, *, secure: bool, max_age: int
) -> None:
    _set(response, platform_session_cookie_name(secure), token, secure=secure, max_age=max_age)


def clear_platform_session_cookie(response: Response, *, secure: bool) -> None:
    _clear(response, platform_session_cookie_name(secure), secure=secure)
