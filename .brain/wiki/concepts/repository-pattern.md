---
tags: [backend, db, python, architecture, orm]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Repository Pattern

**What it is.** One stateless class per table under
[[backend/app/db/repositories/__init__.py]]'s package, each method taking the caller's
`AsyncSession` and `tenant_id` as ordinary arguments and returning ORM entities. The repository
owns *statements*; the service owns *transactions*.

## The house signature

```python
async def by_id(self, session: AsyncSession, tenant_id: UUID, x_id: UUID) -> Row | None
```

`session` first, `tenant_id` second, keyword-only after that. Repositories are constructed once in
a service's `__init__` with **no arguments** — they hold no session, no factory and no state, which
is what lets one service call several of them inside a single `tenant_session` and get one
transaction. [[backend/app/booking/service.py]] instantiates nine of them this way.

**The one exception is [[backend/app/db/repositories/tenants.py]]**, which takes the session factory
and opens its own transactions: `tenants` is platform-scoped, has no `tenant_id` and no RLS, so it
cannot be called from inside a tenant-bound session. Its docstring also records that it requires
`expire_on_commit=False`, since it returns entities after commit.

## Two invariants every repository holds

1. **A redundant `tenant_id` predicate.** [[Row Level Security]] already makes cross-tenant reads
   impossible; the explicit `Table.tenant_id == tenant_id` is defense-in-depth, and every
   repository docstring says so, pointing at
   [[backend/app/db/repositories/staff_users.py]] as the house precedent.
2. **`deleted_at.is_(None)`** on every read — see [[Soft Delete]].

## No error translation, no business rules

A repository raises nothing of its own. `flush()` lets `IntegrityError` reach the service, which
maps it to the domain error — [[backend/app/db/repositories/bookings.py#insert]] refuses to
pre-check the seat index and says why (the index is the truth, a pre-check is a TOCTOU). Likewise
`reschedule` returns `None` rather than raising, and its docstring spells out that `None` is not
silence: it means a concurrent cancel or no-show landed, and the caller must roll back rather than
commit an audit row for a move that did not happen.

Concurrency requirements are documented *on the repository method that needs them* rather than
assumed: `BookingsRepository.insert` states that any caller picking a seat from `active_seats_at`
must first hold the per-tenant [[Advisory Lock]], and
[[backend/app/db/repositories/customers.py#upsert]] states the converse — it needs no lock of its
own because every caller already holds one.

## Gotchas

- **Do not add a re-export barrel** to [[backend/app/db/repositories/__init__.py]]. It is zero
  bytes deliberately: importing one repository must not drag every model onto the declarative base,
  because Alembic autogenerate and the forced-RLS metadata scan both depend on which models are
  registered at a given moment.
- Repositories that mutate must not set `updated_at` — the DB trigger owns it.
- A repository may not open a `tenant_session`. Owning the transaction is the service's job, and
  that is what makes "token burn, terms check, lock, insert, audit — all or nothing" expressible at
  all.
- This is **not** the Exposed/Kotlin repository convention described under `.claude/rules/database/`;
  none of that stack exists here. See [[Documented Stack Vs Actual Stack]].

## Related

- [[Advisory Lock]] · [[Soft Delete]] · [[Row Level Security]] · [[Tenant Context]] · [[SQLAlchemy]]
