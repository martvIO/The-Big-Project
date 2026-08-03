from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.customers.validation import phone_search_term
from app.models.customer import Customer


def _search_where(tenant_id: UUID, q: str | None) -> list[ColumnElement[bool]]:
    """The predicate the page and the total share, so the two can never drift.

    Two things here are the difference between a working search box and a broken
    one, and neither is obvious from the call site:

    **The phone leg runs on `phone_search_term(term)`, never on the term.**
    `customers.phone` only ever holds strict E.164 — `normalize_israeli_mobile`
    rewrites a typed `05X…` to `972` + the rest before either writer stores it —
    so the leading `0` a human reads off a card has been destroyed before
    storage. `'+972501234567' ILIKE '%0501234567%'` is false, and so is `%050%`:
    the stored string contains no `0`,`5`,`0` run at all. Both of the natural
    desk actions would answer "no results" for a customer who demonstrably
    exists. The name leg deliberately stays on the RAW term — a name is not
    digits — and a term with no digits at all skips the phone leg entirely.

    **`autoescape=True` on both legs.** Without it the term is interpolated
    straight into a LIKE pattern, so a typed `_` or `%` returns the whole
    tenant. Hand-rolling `f"%{term}%"` ships exactly that bug.
    """
    criteria: list[ColumnElement[bool]] = [
        Customer.tenant_id == tenant_id,
        Customer.deleted_at.is_(None),
    ]
    term = (q or "").strip()
    if not term:
        return criteria
    legs = [Customer.name.icontains(term, autoescape=True)]
    phone_term = phone_search_term(term)
    if phone_term is not None:
        legs.append(Customer.phone.icontains(phone_term, autoescape=True))
    criteria.append(or_(*legs))
    return criteria


class CustomersRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see StaffUsersRepository)."""

    async def by_phone(
        self, session: AsyncSession, tenant_id: UUID, *, phone: str
    ) -> Customer | None:
        stmt = select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.phone == phone,
            Customer.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, customer_id: UUID
    ) -> Customer | None:
        stmt = select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.id == customer_id,
            Customer.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_ids(
        self, session: AsyncSession, tenant_id: UUID, customer_ids: Sequence[UUID]
    ) -> list[Customer]:
        """The owner day list's name column, in one statement rather than one
        per row. An empty input short-circuits: `IN ()` is a syntax error in
        Postgres and SQLAlchemy's empty-IN rewrite is a needless round trip."""
        if not customer_ids:
            return []
        stmt = select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.id.in_(customer_ids),
            Customer.deleted_at.is_(None),
        )
        return list((await session.execute(stmt)).scalars())

    async def set_phone(
        self, session: AsyncSession, tenant_id: UUID, customer_id: UUID, *, phone: str
    ) -> Customer | None:
        """The owner's phone correction (D8), as one UPDATE.

        `upsert` is NOT the writer for this: it keys on phone, so calling it
        with the corrected number would create a SECOND customer and leave the
        booking pointing at the first. `None` means no live row by that id.

        When the corrected number already belongs to another live customer of
        this tenant, `idx_customers_tenant_phone_unique` refuses and this
        raises. The service never reaches that — it pre-checks and re-points
        `bookings.customer_id` at the existing row instead, because the number
        identifies a person and that person already has a record."""
        stmt = (
            update(Customer)
            .where(
                Customer.tenant_id == tenant_id,
                Customer.id == customer_id,
                Customer.deleted_at.is_(None),
            )
            .values(phone=phone)
            .returning(Customer.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, customer_id)

    async def search(
        self, session: AsyncSession, tenant_id: UUID, *, q: str | None, offset: int, limit: int
    ) -> list[Customer]:
        """The console's customer list (D2). A blank or whitespace-only `q` is
        not a filter — it drops the predicate rather than searching for the
        empty string, because "she cleared the box" means "show me everyone".

        `ORDER BY name, id`: the `id` tiebreak is what makes OFFSET paging
        stable. Two customers named «מיכל לוי» under one boutique is not
        hypothetical, and with `ORDER BY name` alone Postgres may return them in
        either order across plans — so page 1 and page 2 can show the same row
        and hide the other.

        No index, deliberately: a btree cannot serve an unanchored `%term%` at
        all, and the only thing that helps is a `pg_trgm` GIN pair whose upgrade
        path is recorded in 0017's comment.
        """
        stmt = (
            select(Customer)
            .where(*_search_where(tenant_id, q))
            .order_by(Customer.name, Customer.id)
            .offset(offset)
            .limit(limit)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def count_search(self, session: AsyncSession, tenant_id: UUID, *, q: str | None) -> int:
        stmt = select(func.count()).select_from(Customer).where(*_search_where(tenant_id, q))
        return (await session.execute(stmt)).scalar_one()

    async def set_notes_and_tags(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> Customer | None:
        """The CRM write, as one UPDATE — `set_phone`'s shape above.

        `None` means NOT SUPPLIED, never "clear it": `""` and `[]` are values the
        owner can write and they clear the field. The console's notes box and
        its tag chips are two independent controls, so a tags-only patch must
        leave notes alone. Supplying neither is a legal no-op that still answers
        the live row, so the service's diff can decide not to write without
        needing a second read path. `None` means no live row by that id.
        """
        values: dict[str, Any] = {}
        if notes is not None:
            values["notes"] = notes
        if tags is not None:
            values["tags"] = tags
        if not values:
            return await self.by_id(session, tenant_id, customer_id)
        stmt = (
            update(Customer)
            .where(
                Customer.tenant_id == tenant_id,
                Customer.id == customer_id,
                Customer.deleted_at.is_(None),
            )
            .values(**values)
            .returning(Customer.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, customer_id)

    async def upsert(
        self, session: AsyncSession, tenant_id: UUID, *, phone: str, name: str
    ) -> Customer:
        """Attach-or-insert by (tenant, phone). Safe to call without its own
        lock because every caller already holds the per-tenant advisory lock for
        the slot claim; the partial unique index is the backstop either way.

        A returning customer's `name` is UPDATED rather than ignored: she typed
        it on this booking, so it is the most recent thing she calls herself.
        """
        existing = await self.by_phone(session, tenant_id, phone=phone)
        if existing is not None:
            existing.name = name
            await session.flush()
            await session.refresh(existing)
            return existing
        row = Customer(tenant_id=tenant_id, phone=phone, name=name)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row
