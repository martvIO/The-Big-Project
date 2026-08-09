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

import dataclasses
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import NoReturn

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.passwords import hash_password, verify_password
from app.auth.photo import build_staff_photo_key, validate_staff_photo_presign
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.boutique.validation import validate_phone
from app.catalog.service import (
    MediaMismatchError,
    MediaNotUploadedError,
    MediaPresignThrottledError,
)
from app.catalog.validation import (
    MAGIC_PREFIX_LENGTH,
    PRESIGN_TTL_SECONDS,
    matches_magic_prefix,
)
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

# The floor, and unlike the ceiling this one is a SECURITY bound, not a typo
# fence. `last_day` is the retention clock's zero, so an unbounded past date is
# the boutique choosing its own retention: back-date past
# `now - staff_retention_days` and the very next armed retention tick blanks
# display_name/email/phone, seven years early, at the request of the one role
# that already holds offboarding. `start_date` is NOT that floor — 0031 backfills
# `last_day` and never `start_date`, so every pre-F38 row has none, and
# `UpdateStaffRequest.start_date` would let an owner PATCH one backwards first
# anyway. This bound holds whatever the row says, and a year is orders of
# magnitude inside the retention window, so a legitimately late offboarding is
# clamped to a LONGER retention rather than a shorter one.
MAX_LAST_DAY_BACKDATE_DAYS = 365

_CURRENT_PASSWORD_REQUIRED = (
    "current_password is required and must match to change your own password"
)


@dataclasses.dataclass(frozen=True)
class StaffPhotoPresign:
    """What the browser needs to POST the file, and nothing else. No `photo_id`
    on the wire: the confirm route reads the pending triple off the row, so the
    client never holds an identifier it could substitute."""

    url: str
    fields: dict[str, str]
    expires_in: int
    max_bytes: int


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

    The `start_date` comparison is skipped when `start_date` is NULL, and that
    arm is load-bearing: every pre-F38 row has no start date, so comparing
    against it unconditionally would refuse every offboarding in the boutique
    until somebody backfilled a column nobody has.

    `MAX_LAST_DAY_BACKDATE_DAYS` is the REAL floor and is applied unconditionally
    for exactly that reason — `start_date` is absent on most rows and PATCHable
    on the rest, so it can bound nothing. See its constant for what an unbounded
    past `last_day` buys the caller.
    """
    today = today_jerusalem()
    resolved = last_day if last_day is not None else today
    if resolved > today + timedelta(days=MAX_LAST_DAY_LOOKAHEAD_DAYS):
        raise DomainValidationError(
            f"last_day must not be more than {MAX_LAST_DAY_LOOKAHEAD_DAYS} days from today"
        )
    if resolved < today - timedelta(days=MAX_LAST_DAY_BACKDATE_DAYS):
        raise DomainValidationError(
            f"last_day must not be more than {MAX_LAST_DAY_BACKDATE_DAYS} days in the past"
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
        presign_rate_limiter: FixedWindowRateLimiter,
    ) -> None:
        # F38 threads storage in, and this is the one dependency this service
        # gained since F51. Keyword-only and required rather than defaulted: a
        # None default would let a mis-wired create_app() ship an offboarding
        # that silently leaves every photo in the bucket.
        self._session_factory = session_factory
        self._storage = media_storage
        # Its OWN instance, never the catalog's — `max_attempts` lives on the
        # limiter, so two keys on one limiter share a single ceiling and a
        # morning of dress uploads would lock out one avatar
        # (`.memory/limiter-max-is-per-instance`).
        self._presign_limiter = presign_rate_limiter
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

    # --- F38: the profile photo, over F8's two-phase pipeline ----------------

    async def presign_photo(
        self,
        tenant_id: uuid.UUID,
        staff_id: uuid.UUID,
        *,
        content_type: str,
        byte_size: int,
        actor_id: uuid.UUID,
    ) -> StaffPhotoPresign:
        """`presign_media`'s sequence exactly: throttle → validate →
        `is_configured` → lock → resolve → write the pending triple → audit,
        then sign OUTSIDE the transaction.

        The throttle is the OUTERMOST guard so a blocked tenant cannot spend a
        transaction discovering it is blocked, and it runs on its OWN limiter
        instance — `max_attempts` lives on the limiter, so sharing the catalog's
        would give dress uploads and staff photos a single ceiling and let a
        morning of gallery work lock out one avatar.
        """
        throttle_key = f"presign:staff:{tenant_id}"
        if self._presign_limiter.is_blocked(throttle_key):
            raise MediaPresignThrottledError
        validate_staff_photo_presign(content_type=content_type, byte_size=byte_size)
        # Before the row is written: an unconfigured bucket would otherwise leave
        # a pending triple nobody can ever upload against.
        if not self._storage.is_configured:
            raise MediaNotConfiguredError

        photo_id = uuid.uuid4()
        async with tenant_session(self._session_factory, tenant_id) as session:
            await session.execute(_STAFF_LOCK, {"tenant_id": str(tenant_id)})
            target = await self._staff.by_id(session, tenant_id, staff_id)
            if target is None:
                raise StaffNotFoundError
            # Captured BEFORE the overwrite — after it, this key exists nowhere.
            superseded_pending = target.photo_pending_key
            storage_key = build_staff_photo_key(
                tenant_id=tenant_id,
                staff_user_id=staff_id,
                photo_id=photo_id,
                content_type=content_type,
            )
            await self._staff.set_pending_photo(
                session,
                tenant_id,
                staff_id,
                storage_key=storage_key,
                content_type=content_type,
                at=datetime.now(UTC),
            )
            # In the SAME transaction as the pending triple, so a presign refused
            # by an unknown id leaves no trace of a credential never issued.
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.STAFF_PHOTO_PRESIGNED,
                actor_id=actor_id,
                entity=str(staff_id),
                details={
                    "storage_key": storage_key,
                    "content_type": content_type,
                    "byte_size": byte_size,
                },
            )
        # FixedWindowRateLimiter counts only what is explicitly recorded — its
        # docstring says successes never count. A successful presign authorises a
        # 2 MiB write to our bucket, so it is recorded by hand or the throttle is
        # inert. Deleting this line because it reads like a bug is how the
        # throttle dies.
        self._presign_limiter.record_failure(throttle_key)

        # Outside the transaction: the row no longer names this key, so this is
        # the only thing bounding the orphan window.
        if superseded_pending is not None:
            await self._best_effort_delete(tenant_id, staff_id, superseded_pending)
        try:
            presigned = self._storage.presigned_post(
                key=storage_key,
                content_type=content_type,
                exact_bytes=byte_size,
                expires_in=PRESIGN_TTL_SECONDS,
            )
        except (MediaNotConfiguredError, MediaStorageUnavailableError):
            # `is_configured` passed the early guard and signing failed anyway —
            # a rotated IAM key. The pending triple is committed, so leaving it
            # would make the console render a permanent "uploading…" against an
            # upload the browser never received a policy for.
            async with tenant_session(self._session_factory, tenant_id) as session:
                await self._staff.set_pending_photo(
                    session, tenant_id, staff_id, storage_key=None, content_type=None, at=None
                )
            raise
        return StaffPhotoPresign(
            url=presigned.url,
            fields=presigned.fields,
            expires_in=PRESIGN_TTL_SECONDS,
            # The POST policy pins an EXACT content-length range, so the maximum
            # the browser may post is precisely what it declared.
            max_bytes=byte_size,
        )

    async def confirm_photo(
        self, tenant_id: uuid.UUID, staff_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> StaffUser:
        """`confirm_media`'s sequence exactly, and the ORDER is the security
        argument: `head_object` → declared-type match → `read_prefix` → magic
        match → promote in a SECOND transaction, with every storage call outside
        any session.

        ⚠ Scope the magic check honestly: it verifies the object AT CONFIRM TIME
        only. An S3 POST policy cannot be revoked, so within the remainder of
        `PRESIGN_TTL_SECONDS` the same policy can re-POST a different body of the
        identical size to the identical key, after this check has run. The two
        layers covering that window are `signed_get_url` pinning
        ResponseContentType with an attachment disposition, and media-origin
        isolation. Neither is optional and neither may be trimmed on the strength
        of this one.
        """
        if not self._storage.is_configured:
            raise MediaNotConfiguredError

        async with tenant_session(self._session_factory, tenant_id) as session:
            target = await self._staff.by_id(session, tenant_id, staff_id)
            if target is None:
                raise StaffNotFoundError
            pending_key = target.photo_pending_key
            pending_type = target.photo_pending_content_type
        if pending_key is None or pending_type is None:
            # The idempotent short-circuit: a retried confirm after a lost
            # response has nothing to promote and answers the same row without
            # touching storage.
            return target

        # Outside any session: two real network calls, neither of which may hold
        # a Postgres transaction open.
        head = await self._storage.head_object(key=pending_key)
        if head is None:
            raise MediaNotUploadedError
        if head.content_type != pending_type:
            await self._reject_photo(tenant_id, staff_id, pending_key)
        prefix = await self._storage.read_prefix(key=pending_key, length=MAGIC_PREFIX_LENGTH)
        if not matches_magic_prefix(pending_type, prefix):
            # The content-type-honest polyglot: it passed the POST policy at
            # exactly the declared size, and this is what refuses it.
            await self._reject_photo(tenant_id, staff_id, pending_key)

        async with tenant_session(self._session_factory, tenant_id) as session:
            await session.execute(_STAFF_LOCK, {"tenant_id": str(tenant_id)})
            current = await self._staff.by_id(session, tenant_id, staff_id)
            if current is None:
                raise StaffNotFoundError
            if current.photo_pending_key != pending_key:
                # ⚠ THE VERIFIED OBJECT AND THE PROMOTED OBJECT MUST BE THE SAME
                # ONE. `promote_pending_photo` copies whatever key is on the row
                # AT PROMOTE TIME, and the two network calls above ran outside
                # any session against the key read in the FIRST transaction — so
                # a presign landing in that window replaces the pending triple
                # and, without this line, an object whose magic bytes were never
                # read becomes the live photo while the audit row names the key
                # that was checked. `confirm_media` has no such gap because each
                # upload is its own `dress_media` row keyed by `media_id`;
                # collapsing that into one mutable pending triple is what opens
                # it here. Idempotent, not an error: the newer presign's own
                # confirm is the one entitled to promote.
                return current
            superseded_live = current.photo_key
            promoted = await self._staff.promote_pending_photo(
                session, tenant_id, staff_id, at=datetime.now(UTC)
            )
            if promoted is None:
                # Another request promoted it between the two transactions.
                # Idempotent, not an error.
                return current
            # INSIDE the promote branch, not beside it: a retried confirm
            # promoted nothing, and a row asserting otherwise would name an act
            # nobody performed.
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.STAFF_PHOTO_CONFIRMED,
                actor_id=actor_id,
                entity=str(staff_id),
                details={"storage_key": pending_key, "superseded_storage_key": superseded_live},
            )
        # AFTER the audit row that names it — that row is the only durable record
        # if this delete fails.
        if superseded_live is not None and superseded_live != pending_key:
            await self._best_effort_delete(tenant_id, staff_id, superseded_live)
        return promoted

    async def delete_photo(
        self, tenant_id: uuid.UUID, staff_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> StaffUser:
        if not self._storage.is_configured:
            raise MediaNotConfiguredError

        async with tenant_session(self._session_factory, tenant_id) as session:
            await session.execute(_STAFF_LOCK, {"tenant_id": str(tenant_id)})
            target = await self._staff.by_id(session, tenant_id, staff_id)
            if target is None:
                raise StaffNotFoundError
            # `live_key` is read here and not below: `clear_photo` is ORM-enabled
            # DML whose `evaluate` synchronization stamps its NULLs onto this very
            # identity-mapped instance, so `target.photo_key` reads None by the
            # time the audit row is written — and that row is the only durable
            # record of which object the best-effort delete below was meant to
            # remove. Same capture-before-the-write discipline as `confirm_photo`.
            live_key = target.photo_key
            orphaned = [key for key in (live_key, target.photo_pending_key) if key]
            cleared = await self._staff.clear_photo(session, tenant_id, staff_id)
            if cleared is None:  # pragma: no cover — read under the same lock
                raise StaffNotFoundError
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.STAFF_PHOTO_DELETED,
                actor_id=actor_id,
                entity=str(staff_id),
                details={"storage_key": live_key},
            )
        for key in orphaned:
            await self._best_effort_delete(tenant_id, staff_id, key)
        return cleared

    async def _reject_photo(
        self, tenant_id: uuid.UUID, staff_id: uuid.UUID, storage_key: str
    ) -> NoReturn:
        """Clear the pending triple, delete the object, then refuse.

        The object goes FIRST in intent and the clear goes first in order: a
        cleared row with an orphaned object is a wasted byte, while an uncleared
        row pointing at a deleted object is a console stuck on "verifying…"
        forever.

        The clear is CONDITIONAL on the triple still naming this key, under the
        same lock and for the same reason `confirm_photo` compares before it
        promotes: a rejected confirm racing a fresh presign would otherwise wipe
        the NEW triple while deleting only the old object, leaving an upload the
        browser is still waiting on with nothing to confirm.
        """
        async with tenant_session(self._session_factory, tenant_id) as session:
            await session.execute(_STAFF_LOCK, {"tenant_id": str(tenant_id)})
            current = await self._staff.by_id(session, tenant_id, staff_id)
            if current is not None and current.photo_pending_key == storage_key:
                await self._staff.set_pending_photo(
                    session, tenant_id, staff_id, storage_key=None, content_type=None, at=None
                )
        await self._best_effort_delete(tenant_id, staff_id, storage_key)
        # MediaMismatchError, not DomainValidationError — the SAME catalog error
        # the dress-media pipeline raises for this exact refusal, and the reason
        # `MediaNotUploadedError` two branches up is imported rather than
        # restated. main.py maps it to 409 `{"code": "MEDIA_MISMATCH"}`, which is
        # in StaffSection.tsx's MAPPED_CODES; DomainValidationError maps to
        # VALIDATION_ERROR, which is not, so the one security refusal in this
        # pipeline would print its English sentence into a Hebrew RTL alert.
        raise MediaMismatchError("the uploaded file is not a valid image")

    async def _best_effort_delete(
        self, tenant_id: uuid.UUID, staff_id: uuid.UUID, storage_key: str
    ) -> None:
        try:
            await self._storage.delete_object(key=storage_key)
        except (MediaNotConfiguredError, MediaStorageUnavailableError):
            logger.warning(
                "staff photo object was not deleted, it is orphaned: "
                "tenant_id=%s staff_user_id=%s storage_key=%s",
                tenant_id,
                staff_id,
                storage_key,
            )
