"""F26 — invites at rest and the single-use claim, as `boutique_app`.

⚠ db-marked: no Docker locally, so this whole file runs on CI only.

Everything here runs under the NON-OWNER application role, which is the point:
the migration REVOKEs DELETE on `platform_invites`, and a repository that
silently needed it would fail here rather than in production.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.service import AuthService
from app.auth.tokens import generate_session_token, hash_token
from app.core.config import Settings
from app.db.repositories.platform_invites import PlatformInvitesRepository
from app.main import create_app
from app.models.constants import StaffRole
from app.models.platform_invite import PlatformInvite
from app.platform.service import ProvisioningService, RedeemResult

pytestmark = pytest.mark.db


def _engine(app_role_url: str) -> AsyncEngine:
    return create_async_engine(app_role_url, poolclass=NullPool)


def _factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


def _slug() -> str:
    return f"shop-{uuid.uuid4().hex[:8]}"


def _now() -> datetime:
    return datetime.now(UTC)


async def _insert(
    factory: async_sessionmaker,
    *,
    code: str,
    slug: str,
    expires_at: datetime | None = None,
    created_by: str = "op@modryn.example",
) -> uuid.UUID:
    repo = PlatformInvitesRepository()
    async with factory() as session, session.begin():
        row = await repo.insert(
            session,
            code_hash=hash_token(code),
            slug=slug,
            name="Bella Bridal",
            owner_email="Owner@Bella.example",
            created_by=created_by,
            expires_at=expires_at or (_now() + timedelta(days=14)),
        )
        return row.id


def test_an_invite_round_trips_and_stores_only_the_hash(app_role_url: str) -> None:
    """⚠ THE HIGHEST-VALUE ASSERTION IN THIS FILE. Not "code_hash looks right" —
    the raw code must appear in NO column of the row, because a `code` column
    added later "for support" would turn a database leak into a set of live
    boutique-creation credentials, and a targeted assertion would not notice."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    repo = PlatformInvitesRepository()
    try:
        code = generate_session_token()
        slug = _slug()
        invite_id = asyncio.run(_insert(factory, code=code, slug=slug))

        async def read() -> tuple[PlatformInvite | None, dict[str, object]]:
            async with factory() as session:
                found = await repo.by_code_hash(session, hash_token(code))
                row = (
                    (
                        await session.execute(
                            text("SELECT * FROM platform_invites WHERE id = :id"),
                            {"id": invite_id},
                        )
                    )
                    .mappings()
                    .one()
                )
                return found, dict(row)

        found, raw = asyncio.run(read())
        assert found is not None
        assert found.id == invite_id
        assert found.code_hash == hash_token(code)
        assert found.slug == slug
        # Lowercased at insert, like `platform_operators`' addresses.
        assert found.owner_email == "owner@bella.example"
        assert found.redeemed_at is None

        # Over EVERY column value, not just the ones this test names.
        assert code not in {str(value) for value in raw.values()}
        assert "code" not in raw
    finally:
        asyncio.run(engine.dispose())


def test_the_lookup_misses_a_revoked_invite(app_role_url: str) -> None:
    """Revoke is a soft delete, and a soft-deleted invite must read as ABSENT —
    that is what collapses "revoked" into the same `invalid_invite` an unknown
    code gets (D5)."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    repo = PlatformInvitesRepository()
    try:
        code = generate_session_token()
        invite_id = asyncio.run(_insert(factory, code=code, slug=_slug()))

        async def revoke_and_read() -> object:
            async with factory() as session, session.begin():
                assert await repo.soft_delete(session, invite_id) is True
            async with factory() as session:
                return await repo.by_code_hash(session, hash_token(code))

        assert asyncio.run(revoke_and_read()) is None
    finally:
        asyncio.run(engine.dispose())


def test_claim_succeeds_once_and_never_again(app_role_url: str) -> None:
    """The single-use predicate as behaviour, sequentially. The concurrent proof
    lives beside `redeem_invite`; this one pins that the conditional UPDATE
    matches zero rows the second time rather than overwriting the first
    redemption's tenant id."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    repo = PlatformInvitesRepository()
    try:
        code = generate_session_token()
        asyncio.run(_insert(factory, code=code, slug=_slug()))
        first_tenant = uuid.uuid4()
        second_tenant = uuid.uuid4()

        async def claim(tenant_id: uuid.UUID) -> object:
            async with factory() as session, session.begin():
                return await repo.claim(
                    session, code_hash=hash_token(code), tenant_id=tenant_id, now=_now()
                )

        assert asyncio.run(claim(first_tenant)) is not None
        assert asyncio.run(claim(second_tenant)) is None

        async def read_tenant() -> object:
            async with factory() as session:
                found = await repo.by_code_hash(session, hash_token(code))
                assert found is not None
                return found.redeemed_tenant_id

        assert asyncio.run(read_tenant()) == first_tenant
    finally:
        asyncio.run(engine.dispose())


def test_claim_refuses_an_expired_or_revoked_invite(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    repo = PlatformInvitesRepository()
    try:
        expired_code = generate_session_token()
        asyncio.run(
            _insert(
                factory,
                code=expired_code,
                slug=_slug(),
                expires_at=_now() - timedelta(seconds=1),
            )
        )
        revoked_code = generate_session_token()
        revoked_id = asyncio.run(_insert(factory, code=revoked_code, slug=_slug()))

        async def revoke() -> None:
            async with factory() as session, session.begin():
                await repo.soft_delete(session, revoked_id)

        asyncio.run(revoke())

        async def claim(code: str) -> object:
            async with factory() as session, session.begin():
                return await repo.claim(
                    session, code_hash=hash_token(code), tenant_id=uuid.uuid4(), now=_now()
                )

        assert asyncio.run(claim(expired_code)) is None
        assert asyncio.run(claim(revoked_code)) is None
        assert asyncio.run(claim(generate_session_token())) is None
    finally:
        asyncio.run(engine.dispose())


# --- B2: create / list / revoke, through ProvisioningService ------------------
#
# Audit rows are read through the SUPERUSER url, never the app role:
# `platform_audit_log` is INSERT-only for the role under test and genuinely
# cannot be SELECTed by it (`test_provisioning.py`'s technique).


def _audit(owner_url: str, operator: str) -> list[tuple[str, dict]]:
    async def read() -> list[tuple[str, dict]]:
        engine = create_async_engine(owner_url)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            "SELECT action, details FROM platform_audit_log "
                            "WHERE operator = :operator ORDER BY created_at"
                        ),
                        {"operator": operator},
                    )
                ).all()
                return [(str(r[0]), dict(r[1])) for r in rows]
        finally:
            await engine.dispose()

    return asyncio.run(read())


def _operator() -> str:
    return f"op-{uuid.uuid4().hex[:10]}@modryn.example"


def test_create_invite_returns_a_code_that_verifies_against_the_stored_hash(
    app_role_url: str, migrated_db: str
) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = ProvisioningService(factory)
    repo = PlatformInvitesRepository()
    try:
        operator = _operator()
        slug = _slug()
        created = asyncio.run(
            service.create_invite(
                slug=slug, name="Bella Bridal", owner_email="Owner@Bella.example", operator=operator
            )
        )
        assert created.ok, created.message
        assert created.code is not None
        assert created.invite is not None
        assert created.invite.slug == slug
        assert created.invite.owner_email == "owner@bella.example"
        assert created.invite.redeemed_at is None

        async def stored() -> PlatformInvite | None:
            async with factory() as session:
                return await repo.by_code_hash(session, hash_token(created.code or ""))

        found = asyncio.run(stored())
        assert found is not None and found.id == created.invite.id
        assert found.created_by == operator

        rows = _audit(migrated_db, operator)
        assert [action for action, _ in rows] == ["invite_created"]
        assert rows[0][1] == {"slug": slug, "owner_email": "owner@bella.example"}
    finally:
        asyncio.run(engine.dispose())


def test_a_duplicate_or_reserved_slug_is_refused_and_its_failure_audit_commits(
    app_role_url: str, migrated_db: str
) -> None:
    """The F5 lesson on this path: a refusal reported by an exception rolls back
    the row that reports it, so `_fail_invite` writes OUTSIDE the transaction and
    the row survives."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = ProvisioningService(factory)
    try:
        operator = _operator()
        slug = _slug()
        provisioned = asyncio.run(
            service.provision(
                slug=slug,
                name="Bella Bridal",
                owner_email="owner@bella.example",
                owner_password="bella-owner-first-pw",
                operator="someone-else@modryn.example",
            )
        )
        assert provisioned.ok

        taken = asyncio.run(
            service.create_invite(slug=slug, name="X", owner_email="o@x.example", operator=operator)
        )
        assert taken.ok is False
        assert taken.message == "slug_taken"
        assert taken.code is None

        reserved = asyncio.run(
            service.create_invite(
                slug="admin", name="X", owner_email="o@x.example", operator=operator
            )
        )
        assert reserved.ok is False
        assert reserved.message == "invalid_or_reserved_slug"
        assert reserved.code is None

        rows = _audit(migrated_db, operator)
        assert [action for action, _ in rows] == [
            "invite_create_failed",
            "invite_create_failed",
        ]
        assert [details["reason"] for _, details in rows] == [
            "slug_taken",
            "invalid_or_reserved_slug",
        ]
    finally:
        asyncio.run(engine.dispose())


def test_revoke_soft_deletes_audits_and_refuses_a_second_time(
    app_role_url: str, migrated_db: str
) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = ProvisioningService(factory)
    try:
        operator = _operator()
        created = asyncio.run(
            service.create_invite(
                slug=_slug(), name="Bella", owner_email="o@bella.example", operator=operator
            )
        )
        assert created.ok and created.invite is not None
        invite_id = created.invite.id

        listed = asyncio.run(service.list_invites())
        assert invite_id in {row.id for row in listed}

        revoked = asyncio.run(service.revoke_invite(invite_id=invite_id, operator=operator))
        assert revoked.ok and revoked.message == "invite_revoked"

        again = asyncio.run(service.revoke_invite(invite_id=invite_id, operator=operator))
        assert again.ok is False
        assert again.message == "invite_not_found"

        # The row leaves the list, and the preview stops resolving.
        listed_after = asyncio.run(service.list_invites())
        assert invite_id not in {row.id for row in listed_after}
        assert asyncio.run(service.preview_invite(code=created.code or "")) is None

        actions = [action for action, _ in _audit(migrated_db, operator)]
        # Exactly one revoke row: a failed revoke is a no-op with nothing to
        # record, and there is no INVITE_REVOKE_FAILED member to record it with.
        assert actions == ["invite_created", "invite_revoked"]
    finally:
        asyncio.run(engine.dispose())


def test_no_audit_row_ever_carries_the_raw_code_or_its_hash(
    app_role_url: str, migrated_db: str
) -> None:
    """⚠ R-C's tripwire, over EVERY row this feature writes for one operator.

    `platform_audit_log` is append-only by DB grant and nothing prunes it, so a
    code written here would be a live boutique-creation credential stored
    forever in a table the app can neither read back nor delete from."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = ProvisioningService(factory)
    try:
        operator = _operator()
        created = asyncio.run(
            service.create_invite(
                slug=_slug(), name="Bella", owner_email="o@bella.example", operator=operator
            )
        )
        assert created.ok and created.code is not None and created.invite is not None
        code = created.code
        # A refusal path too, so the assertion covers `_fail_invite`'s details.
        asyncio.run(
            service.create_invite(
                slug="admin", name="X", owner_email="o@x.example", operator=operator
            )
        )
        asyncio.run(service.revoke_invite(invite_id=created.invite.id, operator=operator))

        rendered = repr(_audit(migrated_db, operator))
        assert code not in rendered
        assert hash_token(code) not in rendered
    finally:
        asyncio.run(engine.dispose())


# --- B3: redemption, and the race that is this feature's proof ---------------

REDEEM_PASSWORD = "bella-owner-first-pw"
AUTH_SETTINGS = Settings(app_env="dev", session_ttl_seconds=3600)


def _tenants_named(owner_url: str, slug: str) -> int:
    async def read() -> int:
        engine = create_async_engine(owner_url)
        try:
            async with engine.connect() as conn:
                found = await conn.execute(
                    text("SELECT count(*) FROM tenants WHERE slug = :slug"), {"slug": slug}
                )
                return int(found.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(read())


def _staff_rows(owner_url: str, slug: str) -> int:
    async def read() -> int:
        engine = create_async_engine(owner_url)
        try:
            async with engine.connect() as conn:
                found = await conn.execute(
                    text(
                        "SELECT count(*) FROM staff_users s JOIN tenants t ON t.id = s.tenant_id "
                        "WHERE t.slug = :slug"
                    ),
                    {"slug": slug},
                )
                return int(found.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(read())


def test_redeeming_creates_the_tenant_the_operator_authorised_and_the_owner_logs_in(
    app_role_url: str, migrated_db: str
) -> None:
    """⚠ THE PARITY PROOF (spec D4). `TENANT_PROVISIONED` beside `INVITE_REDEEMED`
    is the mechanical evidence that redemption used `_create_tenant` rather than
    a second writer that would drift — and BOTH rows are attributed to the
    invite's issuer, because the redeemer authenticates as nobody."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = ProvisioningService(factory)
    auth = AuthService(factory, AUTH_SETTINGS)
    try:
        operator = _operator()
        slug = _slug()
        created = asyncio.run(
            service.create_invite(
                slug=slug,
                name="Bella Bridal",
                owner_email="owner@bella.example",
                operator=operator,
            )
        )
        assert created.ok and created.code is not None

        # The read the join screen does first: three facts, no code, no hash.
        preview = asyncio.run(service.preview_invite(code=created.code))
        assert preview is not None
        assert (preview.slug, preview.name, preview.owner_email) == (
            slug,
            "Bella Bridal",
            "owner@bella.example",
        )

        result = asyncio.run(
            service.redeem_invite(code=created.code, owner_password=REDEEM_PASSWORD)
        )
        assert result.ok, result.message
        assert result.slug == slug
        assert result.tenant_id is not None

        staff, _ = asyncio.run(auth.login(result.tenant_id, "owner@bella.example", REDEEM_PASSWORD))
        assert staff.email == "owner@bella.example"
        assert staff.role == StaffRole.OWNER.value

        actions = [action for action, _ in _audit(migrated_db, operator)]
        assert actions == ["invite_created", "tenant_provisioned", "invite_redeemed"]

        # Spent: the same link answers the one refusal for all four states.
        again = asyncio.run(
            service.redeem_invite(code=created.code, owner_password=REDEEM_PASSWORD)
        )
        assert again.ok is False and again.message == "invalid_invite"
        assert asyncio.run(service.preview_invite(code=created.code)) is None
    finally:
        asyncio.run(engine.dispose())


def test_two_concurrent_redemptions_produce_exactly_one_boutique(
    app_role_url: str, migrated_db: str
) -> None:
    """⚠ THE FEATURE'S PROOF, and it is deliberately concurrent rather than
    sequential — a sequential double redeem is the test above and proves
    something else entirely.

    Two `redeem_invite` coroutines on ONE code against real Postgres. The loser
    blocks on the claim's row lock, re-evaluates `redeemed_at IS NULL` against
    the winner's committed version, matches zero rows and rolls its WHOLE
    transaction back — so it must leave no Tenant, no StaffUser and no
    TENANT_PROVISIONED row of its own."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = ProvisioningService(factory)
    try:
        operator = _operator()
        slug = _slug()
        created = asyncio.run(
            service.create_invite(
                slug=slug, name="Bella Bridal", owner_email="owner@bella.example", operator=operator
            )
        )
        assert created.ok and created.code is not None
        code = created.code

        async def both() -> list[RedeemResult]:
            return list(
                await asyncio.gather(
                    service.redeem_invite(code=code, owner_password=REDEEM_PASSWORD),
                    service.redeem_invite(code=code, owner_password=REDEEM_PASSWORD),
                )
            )

        results = asyncio.run(both())
        winners = [r for r in results if r.ok]
        losers = [r for r in results if not r.ok]
        assert len(winners) == 1, results
        assert len(losers) == 1, results
        assert losers[0].message in ("invalid_invite", "slug_taken"), losers[0].message

        assert _tenants_named(migrated_db, slug) == 1
        assert _staff_rows(migrated_db, slug) == 1
        actions = [action for action, _ in _audit(migrated_db, operator)]
        assert actions.count("tenant_provisioned") == 1
        assert actions.count("invite_redeemed") == 1
    finally:
        asyncio.run(engine.dispose())


def test_an_expired_or_revoked_invite_answers_the_one_refusal(
    app_role_url: str, migrated_db: str
) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = ProvisioningService(factory)
    try:
        expired_code = generate_session_token()
        asyncio.run(
            _insert(
                factory,
                code=expired_code,
                slug=_slug(),
                expires_at=_now() - timedelta(seconds=1),
            )
        )
        operator = _operator()
        created = asyncio.run(
            service.create_invite(
                slug=_slug(), name="Bella", owner_email="o@bella.example", operator=operator
            )
        )
        assert created.ok and created.invite is not None and created.code is not None
        asyncio.run(service.revoke_invite(invite_id=created.invite.id, operator=operator))

        for code in (expired_code, created.code, generate_session_token()):
            result = asyncio.run(service.redeem_invite(code=code, owner_password=REDEEM_PASSWORD))
            assert result.ok is False
            assert result.message == "invalid_invite"
            assert asyncio.run(service.preview_invite(code=code)) is None
    finally:
        asyncio.run(engine.dispose())


def test_a_failed_redemption_names_the_issuer_of_a_real_invite(
    app_role_url: str, migrated_db: str
) -> None:
    """⚠ THE REFUSAL IS ONE CODE; THE AUDIT ROW IS NOT.

    Operator issues an invite for a slug, spots a typo, revokes it — and the
    link leaks. The replay must leave a book entry that answers "which
    authorisation was being replayed and who issued it", which `anonymous:join`
    with no slug cannot. Expired and revoked both have their issuer in the row
    the read already returned. Only an UNKNOWN code has no issuer, and it is the
    only one that stays anonymous.

    The wire answer is `invalid_invite` in all three cases — asserted here so
    the attribution cannot be mistaken for a widened disclosure (D5).
    """
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = ProvisioningService(factory)
    try:
        operator = _operator()
        expired_slug = _slug()
        expired_code = generate_session_token()
        asyncio.run(
            _insert(
                factory,
                code=expired_code,
                slug=expired_slug,
                expires_at=_now() - timedelta(seconds=1),
                created_by=operator,
            )
        )
        revoked_slug = _slug()
        created = asyncio.run(
            service.create_invite(
                slug=revoked_slug, name="Bella", owner_email="o@bella.example", operator=operator
            )
        )
        assert created.ok and created.invite is not None and created.code is not None
        asyncio.run(service.revoke_invite(invite_id=created.invite.id, operator=operator))

        for code in (expired_code, created.code):
            result = asyncio.run(service.redeem_invite(code=code, owner_password=REDEEM_PASSWORD))
            assert result.ok is False and result.message == "invalid_invite"

        failures = [
            details
            for action, details in _audit(migrated_db, operator)
            if action == "invite_redeem_failed"
        ]
        assert len(failures) == 2
        assert {details["slug"] for details in failures} == {expired_slug, revoked_slug}
        # Still the prefix, never the code and never the whole hash.
        assert {details["code_hash_prefix"] for details in failures} == {
            hash_token(expired_code)[:8],
            hash_token(created.code)[:8],
        }
        assert expired_code not in repr(failures) and created.code not in repr(failures)

        unknown = generate_session_token()
        result = asyncio.run(service.redeem_invite(code=unknown, owner_password=REDEEM_PASSWORD))
        assert result.ok is False and result.message == "invalid_invite"
        anonymous = [
            details
            for action, details in _audit(migrated_db, "anonymous:join")
            if action == "invite_redeem_failed"
            and details["code_hash_prefix"] == hash_token(unknown)[:8]
        ]
        assert len(anonymous) == 1
        assert "slug" not in anonymous[0]
    finally:
        asyncio.run(engine.dispose())


def test_a_slug_taken_between_issue_and_redemption_leaves_the_invite_unspent(
    app_role_url: str, migrated_db: str
) -> None:
    """The claim is the FIRST statement, so it rolls back with everything else:
    a reissue for a free address can still use this invite. That is only true
    because there is one transaction — a claim committed separately would burn
    the invite on somebody else's slug."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = ProvisioningService(factory)
    try:
        operator = _operator()
        slug = _slug()
        created = asyncio.run(
            service.create_invite(
                slug=slug, name="Bella Bridal", owner_email="owner@bella.example", operator=operator
            )
        )
        assert created.ok and created.code is not None

        # Somebody else takes the address after the invite was issued.
        stolen = asyncio.run(
            service.provision(
                slug=slug,
                name="Someone Else",
                owner_email="other@x.example",
                owner_password="another-owner-pw",
                operator="someone-else@modryn.example",
            )
        )
        assert stolen.ok

        result = asyncio.run(
            service.redeem_invite(code=created.code, owner_password=REDEEM_PASSWORD)
        )
        assert result.ok is False
        assert result.message == "slug_taken"

        # UNSPENT — the claim rolled back with the failed insert.
        still_open = asyncio.run(service.preview_invite(code=created.code))
        assert still_open is not None
        assert still_open.redeemed_at is None
        assert _tenants_named(migrated_db, slug) == 1
    finally:
        asyncio.run(engine.dispose())


def test_a_weak_password_is_refused_without_spending_the_invite(
    app_role_url: str, migrated_db: str
) -> None:
    """Each refusal keeps its own code — the join screen puts them in the
    password field's error slot rather than the form alert — and neither spends
    the invite, because `_password_problem` runs BEFORE the transaction."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = ProvisioningService(factory)
    try:
        operator = _operator()
        created = asyncio.run(
            service.create_invite(
                slug=_slug(), name="Bella", owner_email="o@bella.example", operator=operator
            )
        )
        assert created.ok and created.code is not None

        blank = asyncio.run(service.redeem_invite(code=created.code, owner_password="   "))
        assert blank.ok is False and blank.message == "empty_password"
        short = asyncio.run(service.redeem_invite(code=created.code, owner_password="abc"))
        assert short.ok is False and short.message == "password_too_short"

        still_open = asyncio.run(service.preview_invite(code=created.code))
        assert still_open is not None and still_open.redeemed_at is None

        rows = _audit(migrated_db, operator)
        assert [action for action, _ in rows] == [
            "invite_created",
            "invite_redeem_failed",
            "invite_redeem_failed",
        ]
        # The hash PREFIX only — never the code, never the whole hash.
        for _, details in rows[1:]:
            assert details["code_hash_prefix"] == hash_token(created.code)[:8]
        assert created.code not in repr(rows)
        assert hash_token(created.code) not in repr(rows)
    finally:
        asyncio.run(engine.dispose())


# --- C2: the anonymous surface over HTTP -------------------------------------


def _console_app(factory: async_sessionmaker, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(app_env="dev"))
    monkeypatch.setattr("app.main.get_session_factory", lambda: factory)

    async def _resolver(slug: str) -> None:
        return None

    return create_app(resolver=_resolver)


def test_the_join_routes_preview_and_redeem_an_invite_anonymously(
    app_role_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No cookie, no session, no operator — the whole point of the feature. The
    success response names the manage URL F17's gateway screen lives behind; F26
    adds no payment code and only links there (D7)."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = ProvisioningService(factory)
    try:
        slug = _slug()
        created = asyncio.run(
            service.create_invite(
                slug=slug,
                name="Bella Bridal",
                owner_email="owner@bella.example",
                operator=_operator(),
            )
        )
        assert created.ok and created.code is not None

        app = _console_app(factory, monkeypatch)
        with TestClient(app, base_url="http://admin.localtest.me") as client:
            preview = client.post("/platform/join/invite", json={"code": created.code})
            assert preview.status_code == 200, preview.text
            assert preview.json() == {
                "slug": slug,
                "name": "Bella Bridal",
                "owner_email": "owner@bella.example",
            }

            redeemed = client.post(
                "/platform/join/redeem",
                json={"code": created.code, "owner_password": REDEEM_PASSWORD},
            )
            assert redeemed.status_code == 200, redeemed.text
            assert redeemed.json() == {
                "slug": slug,
                "manage_url": f"https://{slug}.localtest.me/manage",
            }

            # Spent. Same body for redeemed as for unknown (D5).
            spent = client.post("/platform/join/invite", json={"code": created.code})
            assert spent.status_code == 404
            assert spent.json()["error"]["code"] == "invalid_invite"
    finally:
        asyncio.run(engine.dispose())


def test_repeated_bad_codes_are_throttled_after_the_budget(
    app_role_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The budget exists because every refusal here writes an INSERT-only
    `platform_audit_log` row nothing prunes. Keyed on the code's hash, so the
    same bad code is what gets throttled — and the global arm is what a caller
    rotating codes eventually hits."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    try:
        app = _console_app(factory, monkeypatch)
        bad = generate_session_token()
        with TestClient(app, base_url="http://admin.localtest.me") as client:
            budget = Settings(app_env="dev").invite_redeem_max_attempts
            for _ in range(budget):
                refused = client.post(
                    "/platform/join/redeem",
                    json={"code": bad, "owner_password": REDEEM_PASSWORD},
                )
                assert refused.status_code == 404
                assert refused.json()["error"]["code"] == "invalid_invite"
            blocked = client.post(
                "/platform/join/redeem", json={"code": bad, "owner_password": REDEEM_PASSWORD}
            )
            assert blocked.status_code == 429
            assert blocked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
            # The SAME budget, so a caller who exhausted redeem cannot keep
            # hammering preview with the code it already spent it on.
            assert client.post("/platform/join/invite", json={"code": bad}).status_code == 429
    finally:
        asyncio.run(engine.dispose())
