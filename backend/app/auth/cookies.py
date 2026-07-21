from starlette.responses import Response

SESSION_COOKIE = "boutique_session"


def set_session_cookie(response: Response, token: str, *, secure: bool, max_age: int) -> None:
    # No Domain attribute → host-only cookie: a session minted at boutique A is
    # never sent to boutique B's subdomain. HttpOnly blocks JS theft; SameSite=Lax
    # blocks cross-site CSRF on the login/session cookie.
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, *, secure: bool) -> None:
    response.delete_cookie(SESSION_COOKIE, httponly=True, secure=secure, samesite="lax", path="/")
