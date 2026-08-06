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
PLATFORM_SESSION_COOKIE = "boutique_platform_session"


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
    _set(response, PLATFORM_SESSION_COOKIE, token, secure=secure, max_age=max_age)


def clear_platform_session_cookie(response: Response, *, secure: bool) -> None:
    _clear(response, PLATFORM_SESSION_COOKIE, secure=secure)
