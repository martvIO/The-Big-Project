# Pattern: A DB write followed by `raise` in the same transaction is rolled back

`tenant_session()` / `tenant_connection()` open the transaction with
`async with session_factory() as session, session.begin():`. If you `add()`+`flush()`
a row and then `raise` while still inside that block, `session.begin().__aexit__`
rolls the whole transaction back on the way out — the write is silently discarded.

**Rule:** failure-path writes that MUST persist (audit rows, `login_failed`,
future booking/payment failure records) cannot share a transaction with the
exception that reports the failure. Compute the outcome, let the `tenant_session`
block exit normally so it commits, then raise *outside* the `async with`. And test
it: assert the row exists after the failure, not just that the exception raised.

**Origin (2026-07-21, Feature 5 review):** both the quality and adversarial-security
reviewers independently reproduced this — `login()` wrote `LOGIN_FAILED` then raised
inside `tenant_session`, so zero failed-login audit rows ever committed. A superset
audit assertion (`>= {"login","logout"}`) masked it; a `count("login_failed") == N`
assertion catches it.
