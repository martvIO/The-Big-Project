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

import logging
import uuid
from datetime import date, timedelta
from typing import NoReturn

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.passwords import hash_password, verify_password
from app.auth.service import StaffContext
from app.boutique.validation import validate_phone
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.sessions import SessionsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError, DomainValidationError
from app.models.constants import AuditAction, StaffRole
from app.models.staff_user import StaffUser
from app.storage.base import (
    MediaNotConfiguredError,
    MediaStorage,
    MediaStorageUnavailableError,
)
from app.storefront.validation import today_jerusalem

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

logger = logging.getLogger(__name__)

# A TYPO FENCE, not a policy about notice periods: `2036` for `2026` is one
# keystroke and would park her outside the retention scrub for a decade.
MAX_LAST_DAY_LOOKAHEAD_DAYS = 365

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


def _resolve_last_day(last_day: date | None, *, start_date: date | None) -> date:
    """`None` means TODAY IN JERUSALEM and never "leave it NULL".

    The retention policy's predicate requires `last_day IS NOT NULL`, so a NULL
    is not "unknown" — it is "never scrub this person", and that is not a state
    an owner pressing a button should be able to reach by omitting a field.

    Jerusalem and not UTC because this is the date a seven-year calendar clock
    counts from, and the two zones are different days for two or three hours of
    every night.

    The lower bound is skipped when `start_date` is NULL, and that arm is
    load-bearing: every pre-F38 row has no start date, so comparing against it
    unconditionally would refuse every offboarding in the boutique until somebody
    backfilled a column nobody has.
    """
    today = today_jerusalem()
    resolved = last_day if last_day is not None else today
    if resolved > today + timedelta(days=MAX_LAST_DAY_LOOKAHEAD_DAYS):
        raise DomainValidationError(
            f"last_day must not be more than {MAX_LAST_DAY_LOOKAHEAD_DAYS} days from today"
        )
    if start_date is not None and resolved < start_date:
        raise DomainValidationError("last_day must not be before start_date")
    return resolved


def _normalize_phone(phone: str | None) -> str | None:
    """`None` means NOT SENT and is the caller's problem; "" (or any blank) means
    CLEAR IT and resolves to NULL here.

    That second arm has to exist. `None` is already spoken for by this API's
    send-only-what-moved rule, so without an explicit clear a staffer who asks
    for her number to come off the system could not be obliged until the
    seven-year scrub. An emptied `<input>` posts "" natively, so it costs no
    sentinel and no tri-state — and the branch sits ABOVE `validate_phone`
    because that function refuses "" anyway (it requires a digit).

    Validation is the IMPORTED `validate_phone`, never a second regex: the
    boutique profile's number and a staffer's number are the same kind of
    string, and one gate is what keeps them agreeing.
    """
    if phone is None:
        return None
    stripped = phone.strip()
    if not stripped:
        return None
    validate_phone(stripped)
    return stripped


class StaffService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        media_storage: MediaStorage,
    ) -> None:
        # F38 threads storage in, and this is the one dependency this service
        # gained since F51. Keyword-only and required rather than defaulted: a
        # None default would let a mis-wired create_app() ship an offboarding
        # that silently leaves every photo in the bucket.
        self._session_factory = session_factory
        self._storage = media_storage
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
        phone: str | None = None,
        start_date: date | None = None,
        shift_manager_eligible: bool = False,
        actor: StaffContext,
    ) -> StaffUser:
        # Lowercased HERE, before anything else (spec D5). login lowercases before
        # its lookup and by_email matches exactly, so a row written as
        # Dana@Bella.example is an account that can never sign in — a silent,
        # total failure with no error anywhere. ProvisioningService already knows
        # this; so does this.
        address = email.lower()
        # Before the hash and before the session, for the same reason the
        # duplicate pre-check is early: a refusal must cost neither an argon2 nor
        # a pooled connection.
        stored_phone = _normalize_phone(phone)
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
                    phone=stored_phone,
                    start_date=start_date,
                    shift_manager_eligible=shift_manager_eligible,
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
        phone: str | None = None,
        start_date: date | None = None,
        shift_manager_eligible: bool | None = None,
        acting_token_hash: str | None = None,
        actor: StaffContext,
    ) -> StaffUser:
        # Above the lock and above the read: a malformed number must cost no
        # transaction, no advisory lock and no row. `phone_sent` is captured here
        # because _normalize_phone collapses "not sent" and "clear it" to the
        # same None, and only the caller's original can tell them apart.
        phone_sent = phone is not None
        stored_phone = _normalize_phone(phone)
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
            # F38's three, each on the SAME moved-not-present rule as the name
            # above: the inline edit form posts every field on every save, so a
            # presence test would write three audit rows every time the owner
            # pressed save without changing anything.
            #
            # `phone_sent` rather than `stored_phone is not None`, because
            # clearing a number IS a move and its stored value is None.
            phone_moves = phone_sent and stored_phone != target.phone
            start_date_moves = start_date is not None and start_date != target.start_date
            eligibility_moves = (
                shift_manager_eligible is not None
                and shift_manager_eligible != target.shift_manager_eligible
            )
            if (
                new_name is None
                and new_role is None
                and password_hash is None
                and not phone_moves
                and not start_date_moves
                and not eligibility_moves
            ):
                # F15's D3 no-op rule: nothing changed, so nothing is written and
                # nothing is audited. `password` is never compared — an argon2
                # verify against the new value to detect "same password" would be
                # a gratuitous verify that leaks nothing useful.
                return target

            previous_name, previous_role = target.display_name, target.role
            previous_phone_present = target.phone is not None
            previous_start_date, previous_eligibility = (
                target.start_date,
                target.shift_manager_eligible,
            )
            updated = await self._staff.update(
                session,
                tenant_id,
                staff_id,
                display_name=new_name,
                role=new_role,
                password_hash=password_hash,
                # `""` and not None on the clear path: None is "not sent"
                # all the way down this signature, so a cleared number has to
                # keep the HTTP boundary's own spelling one layer further in.
                phone=(stored_phone or "") if phone_moves else None,
                start_date=start_date if start_date_moves else None,
                shift_manager_eligible=shift_manager_eligible if eligibility_moves else None,
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
            if phone_moves:
                # PRESENCE, never the number — and that is STRICTER than the
                # shipped `phone_last4` convention, deliberately. `audit_log` has
                # no retention class at all, by ruling, because a clock on the
                # evidence would erase the proof of the erasures it records. So
                # any digits written here outlive the seven-year scrub that
                # exists to destroy exactly this identifier, permanently.
                # Presence is the whole fact an audit reader needs; the number
                # itself is on the row until the clock takes it.
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.STAFF_UPDATED,
                    actor_id=actor.id,
                    entity=str(staff_id),
                    details={
                        "phone": {
                            "from": previous_phone_present,
                            "to": stored_phone is not None,
                        }
                    },
                )
            if start_date_moves and start_date is not None:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.STAFF_UPDATED,
                    actor_id=actor.id,
                    entity=str(staff_id),
                    # `isoformat()` because audit `details` is JSONB and a
                    # `date` is not JSON — it would raise at flush, inside the
                    # transaction that was writing the change it describes.
                    details={
                        "start_date": {
                            "from": None
                            if previous_start_date is None
                            else previous_start_date.isoformat(),
                            "to": start_date.isoformat(),
                        }
                    },
                )
            if eligibility_moves:
                # Its OWN row and never a STAFF_ROLE_CHANGED: "may be assigned as
                # shift manager" is not "her job is shift manager", and folding
                # them would make the one query a security audit actually asks —
                # "who was made an owner" — return rows about rota eligibility.
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.STAFF_UPDATED,
                    actor_id=actor.id,
                    entity=str(staff_id),
                    details={
                        "shift_manager_eligible": {
                            "from": previous_eligibility,
                            "to": shift_manager_eligible,
                        }
                    },
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
        self,
        tenant_id: uuid.UUID,
        staff_id: uuid.UUID,
        *,
        last_day: date | None = None,
        actor: StaffContext,
    ) -> None:
        """Offboarding. F51's protocol unchanged, plus F38's leaving date and the
        removal of her photo.

        Instantly effective, by construction: resolve_session re-reads
        staff_users on every request and by_id filters deleted_at IS NULL, so the
        target's live cookie is a 401 on her very next request. **There is no
        session sweep and there must not be one** — F20's `sessions` policy
        reclaims the dead rows on its own clock, and a `revoke_for_staff_user`
        here would be a second mechanism for a fact the first already guarantees.

        `last_day=None` means "today in Jerusalem" and NEVER "leave it NULL". The
        retention policy's predicate requires `last_day IS NOT NULL`, so a NULL
        here does not mean "unknown" — it means "never scrub this person", which
        is not a state an owner pressing a button should be able to reach.

        Her photo OBJECT goes here rather than at the seven-year scrub, which is
        stricter than the brief and deliberately so: her face is the most
        identifying datum on the row, nothing operational reads it once she is
        gone, and it keeps the retention policy a pure SQL statement — the
        shipped `PolicyRun` contract hands a policy a session and nothing else.

        Every operational row she appears in is RETAINED, joined by a
        `staff_user_id` that is never nulled: her fitting-room assignments, the
        SOS alerts aimed at her, her alteration tickets and her audit trail. No
        CASCADE exists anywhere to undo that — the FK-less schema makes retention
        the default and erasure the deliberate act.
        """
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

            # AFTER the three guards, so a refused offboarding cannot stamp a
            # leaving date on a live employee, and after the read because the
            # lower bound is HER start date.
            leaving = _resolve_last_day(last_day, start_date=target.start_date)

            email, role = target.email, target.role
            # Captured BEFORE the write — the UPDATE nulls both columns, so this
            # is the last moment either key exists anywhere.
            orphaned = [key for key in (target.photo_key, target.photo_pending_key) if key]
            await self._staff.soft_delete(session, tenant_id, staff_id, last_day=leaving)
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.STAFF_DEACTIVATED,
                actor_id=actor.id,
                entity=str(staff_id),
                # `photo_storage_key` is load-bearing: the delete below is
                # best-effort and swallows a storage outage, so on that path this
                # row is the ONLY durable record of which object was orphaned.
                details={
                    "email": email,
                    "role": role,
                    "last_day": leaving.isoformat(),
                    "photo_storage_key": target.photo_key,
                },
            )

        # OUTSIDE the transaction, and best-effort. The row is already committed:
        # raising here would answer 503 to an owner whose staffer IS offboarded,
        # and she would press it again.
        for key in orphaned:
            try:
                await self._storage.delete_object(key=key)
            except (MediaNotConfiguredError, MediaStorageUnavailableError):
                logger.warning(
                    "offboarded staff photo object was not deleted, it is orphaned: "
                    "tenant_id=%s staff_user_id=%s storage_key=%s",
                    tenant_id,
                    staff_id,
                    key,
                )
