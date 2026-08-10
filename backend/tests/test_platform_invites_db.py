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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.tokens import generate_session_token, hash_token
from app.db.repositories.platform_invites import PlatformInvitesRepository
from app.models.platform_invite import PlatformInvite

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
) -> uuid.UUID:
    repo = PlatformInvitesRepository()
    async with factory() as session, session.begin():
        row = await repo.insert(
            session,
            code_hash=hash_token(code),
            slug=slug,
            name="Bella Bridal",
            owner_email="Owner@Bella.example",
            created_by="op@modryn.example",
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
