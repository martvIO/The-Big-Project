"""Owner-only staff administration: the only surface in the product that can
create a shift_manager.

**Not methods on AuthService.** That class verifies credentials and issues
sessions; folding administration into it would put the login path's fake into
every CRUD test. Two files in an existing package, not a new app/staff/ package
for one router.

**Two invariants hold under CONCURRENCY, not just under a single request** — an
owner may not deactivate or demote herself, and a tenant always has at least one
live owner. The second one is why this module opens with an advisory lock.

No unique index can express it: an index expresses *at most one* of something,
and this invariant is *at least one*. A single guarded statement does not work
either, and that is the trap worth writing down:

    UPDATE staff_users SET role = 'shift_manager' WHERE id = :id
      AND (SELECT count(*) FROM staff_users
           WHERE tenant_id = :t AND role = 'owner' AND deleted_at IS NULL) > 1

Under READ COMMITTED — Postgres's default and this repo's — two concurrent
statements each evaluate that subquery against a snapshot that does not contain
the other's uncommitted write. Both see 2, both pass, both commit, and the tenant
ends with ZERO owners with no error raised anywhere.

So PATCH-carrying-a-role and DELETE both run the same protocol inside one
tenant_session: take the lock BEFORE any read, then read the target, then the
guards, then the write, then the audit rows. A read taken outside the lock is a
stale read — the guard would be evaluated against a count another transaction has
already invalidated.

**create takes no lock**, and that absence is a ruling rather than an omission:
an insert can only RAISE the live-owner count, and a raise never invalidates a
decision another transaction already made under the lock.
"""

import uuid
from typing import NoReturn

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.passwords import hash_password, verify_password
from app.auth.service import StaffContext
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.sessions import SessionsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError, DomainValidationError
from app.models.constants import AuditAction, StaffRole
from app.models.staff_user import StaffUser

# hashtext() keys an xact-scoped lock that releases with the transaction. The
# prefix is a SQL literal and the tenant id is bound — never interpolated.
#
# NAMESPACED deliberately: the bare hashtext(:tenant_id) key is the booking-claim
# lock (booking/service.py, booking/owner.py), and reusing it would serialize
# every staff edit against every public booking create for this tenant — correct
# but pointlessly wide. catalog/service.py's 'dress-media:' / 'dress-variants:'
# keys are the in-repo precedent for prefixing.
#
# ponytail: one lock per tenant's staff table; nothing in a boutique needs finer.
_STAFF_LOCK = text("SELECT pg_advisory_xact_lock(hashtext('staff:' || :tenant_id))")

_CURRENT_PASSWORD_REQUIRED = (
    "current_password is required and must match to change your own password"
)


class DuplicateEmailError(Exception):
    """A live staff row already holds this address for this tenant. Raised by the
    pre-check AND by the IntegrityError backstop behind the partial unique index —
    the pre-check races, and a 500 on a duplicate email is not an answer."""


class LastOwnerRequiredError(Exception):
    """Demoting or deactivating this row would leave the tenant with no live
    owner. The body names no count: a count is not the owner's problem to solve."""


class StaffSelfManageError(Exception):
    """The acting staffer targeted her own role, or her own account for
    deactivation. Renaming herself and changing her own password stay legal."""


class StaffNotFoundError(DomainNotFoundError):
    """Unknown, soft-deleted, or another tenant's staff id — one indistinguishable
    miss. RLS and the repository's redundant tenant predicate are what make the
    foreign case identical to the missing one, by design. Subclasses the
    app/errors.py base, so it needs no handler of its own."""


def _refuse_current_password() -> NoReturn:
    raise DomainValidationError(_CURRENT_PASSWORD_REQUIRED)


class StaffService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._staff = StaffUsersRepository()
        self._sessions = SessionsRepository()
        self._audit = AuditLogRepository()

    async def list_staff(self, tenant_id: uuid.UUID) -> list[StaffUser]:
        """No lock and no pagination (spec D6): a boutique's staff table is
        single-digit, and paging controls nobody can reach are the un-lazy thing."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            return await self._staff.list_live(session, tenant_id)

    async def create(
        self,
        tenant_id: uuid.UUID,
        *,
        email: str,
        display_name: str,
        role: str,
        password: str,
        actor: StaffContext,
    ) -> StaffUser:
        # Lowercased HERE, before anything else (spec D5). login lowercases before
        # its lookup and by_email matches exactly, so a row written as
        # Dana@Bella.example is an account that can never sign in — a silent,
        # total failure with no error anywhere. ProvisioningService already knows
        # this; so does this.
        address = email.lower()
        # Outside the session: argon2 is deliberately expensive, and there is no
        # reason to hold a pooled connection across it.
        password_hash = hash_password(password)
        try:
            # The try wraps the WHOLE block, the provision() shape: the
            # IntegrityError may surface at flush or at commit, and catching
            # inside the block would try to raise from an aborted transaction.
            async with tenant_session(self._session_factory, tenant_id) as session:
                if await self._staff.by_email(session, tenant_id, address) is not None:
                    raise DuplicateEmailError
                created = await self._staff.insert(
                    session,
                    tenant_id=tenant_id,
                    email=address,
                    password_hash=password_hash,
                    display_name=display_name,
                    role=role,
                )
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.STAFF_CREATED,
                    actor_id=actor.id,
                    entity=str(created.id),
                    # No password material, plaintext or hashed, ever enters
                    # details (spec D8). Emails do: audit_log is per-tenant under
                    # forced RLS and the email is the identity the row is about.
                    details={"email": address, "role": role},
                )
                return created
        except IntegrityError as exc:
            raise DuplicateEmailError from exc

    async def update(
        self,
        tenant_id: uuid.UUID,
        staff_id: uuid.UUID,
        *,
        display_name: str | None = None,
        role: str | None = None,
        password: str | None = None,
        current_password: str | None = None,
        acting_token_hash: str | None = None,
        actor: StaffContext,
    ) -> StaffUser:
        # Hoisted for create's reason: argon2 is deliberately expensive and
        # nothing about it needs the advisory lock or a pooled connection. The
        # wasted hash on a refusal path is the trade create already makes.
        # verify_password below cannot move — it needs the row's own hash.
        new_password_hash = hash_password(password) if password is not None else None
        async with tenant_session(self._session_factory, tenant_id) as session:
            await session.execute(_STAFF_LOCK, {"tenant_id": str(tenant_id)})
            target = await self._staff.by_id(session, tenant_id, staff_id)
            if target is None:
                raise StaffNotFoundError
            is_self = target.id == actor.id

            # The guard fires on the role MOVING, not on the field being present.
            # The inline edit form posts display_name and role together, so the
            # stricter reading would 409 an owner for renaming herself.
            role_moves = role is not None and role != target.role
            if role_moves and is_self:
                raise StaffSelfManageError
            if (
                role_moves
                and target.role == StaffRole.OWNER.value
                and await self._staff.count_live_owners(session, tenant_id) <= 1
            ):
                raise LastOwnerRequiredError

            password_hash: str | None = None
            if password is not None:
                # Only on the self path. An owner resetting SOMEONE ELSE's
                # password sends no current_password — she does not know it, and
                # that is the field's whole point.
                if is_self and not (
                    current_password is not None
                    and verify_password(current_password, target.password_hash)
                ):
                    _refuse_current_password()
                password_hash = new_password_hash

            new_name = (
                display_name
                if display_name is not None and display_name != target.display_name
                else None
            )
            new_role = role if role_moves else None
            if new_name is None and new_role is None and password_hash is None:
                # F15's D3 no-op rule: nothing changed, so nothing is written and
                # nothing is audited. `password` is never compared — an argon2
                # verify against the new value to detect "same password" would be
                # a gratuitous verify that leaks nothing useful.
                return target

            previous_name, previous_role = target.display_name, target.role
            updated = await self._staff.update(
                session,
                tenant_id,
                staff_id,
                display_name=new_name,
                role=new_role,
                password_hash=password_hash,
            )
            if updated is None:  # pragma: no cover — read under the same lock
                raise StaffNotFoundError

            # One row per thing that ACTUALLY changed (spec D8).
            if new_name is not None:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.STAFF_UPDATED,
                    actor_id=actor.id,
                    entity=str(staff_id),
                    details={"display_name": {"from": previous_name, "to": new_name}},
                )
            if new_role is not None:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.STAFF_ROLE_CHANGED,
                    actor_id=actor.id,
                    entity=str(staff_id),
                    details={"from": previous_role, "to": new_role},
                )
            if password_hash is not None:
                # A password change must end the sessions the OLD password
                # could have leaked. Deactivation needs no sweep because
                # resolve_session re-reads staff_users; a password change gets
                # no such seam for free, so this is where the spec's «converts
                # a permanent takeover into a bounded one» claim is actually
                # paid for. Same transaction, same lock. The acting cookie is
                # excluded so the owner is not signed out of the tab she just
                # used — on the reset-someone-else path she holds no session of
                # the target's, so the exclusion is a no-op there.
                await self._sessions.revoke_for_staff_user(
                    session, tenant_id, staff_id, except_token_hash=acting_token_hash
                )
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.STAFF_PASSWORD_RESET,
                    actor_id=actor.id,
                    entity=str(staff_id),
                    details={"self": is_self},
                )
            return updated

    async def deactivate(
        self, tenant_id: uuid.UUID, staff_id: uuid.UUID, *, actor: StaffContext
    ) -> None:
        """Instantly effective, by construction: resolve_session re-reads
        staff_users on every request and by_id filters deleted_at IS NULL, so the
        target's live cookie is a 401 on her very next request. There is no
        session sweep and there must not be one."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            await session.execute(_STAFF_LOCK, {"tenant_id": str(tenant_id)})
            target = await self._staff.by_id(session, tenant_id, staff_id)
            if target is None:
                raise StaffNotFoundError
            if target.id == actor.id:
                raise StaffSelfManageError
            # Unreachable over HTTP as long as the router stays owner-only — the
            # acting owner is herself live, so a second owner target means the
            # count is at least 2. Kept because the invariant belongs to the
            # service, not to the gate, and the db suite races it directly.
            if (
                target.role == StaffRole.OWNER.value
                and await self._staff.count_live_owners(session, tenant_id) <= 1
            ):
                raise LastOwnerRequiredError

            email, role = target.email, target.role
            await self._staff.soft_delete(session, tenant_id, staff_id)
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.STAFF_DEACTIVATED,
                actor_id=actor.id,
                entity=str(staff_id),
                details={"email": email, "role": role},
            )
