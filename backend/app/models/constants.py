from enum import StrEnum


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class StaffRole(StrEnum):
    # The DB pins this exact set (0011, widened by F57's migration), and
    # test_the_floor_roles_migration_pins_the_widened_constraint_definition holds
    # the deparsed literal so the next widening collides with a review.
    #
    # The floor program is the consumer 0011's comment demanded before the last
    # three could be added — pre-adding speculative roles is the un-lazy thing
    # (the ScheduledMessageKind rule), and this block is the record that the bar
    # was MET rather than waived: the roles arrive in the same PR as the surface
    # that reads them.
    OWNER = "owner"
    SHIFT_MANAGER = "shift_manager"
    RECEPTION = "reception"
    SALES_ASSISTANT = "sales_assistant"  # supersedes pre-decided #24's 'sales'
    SEAMSTRESS = "seamstress"


class StaffCardStatus(StrEnum):
    # F57's floor cards. NOT pinned by the DB and deliberately not: it is DERIVED
    # on read from `staff_users.break_started_at` (D2 adds no status column and no
    # break history table), so there is no stored value for a CHECK to constrain.
    #
    # F36 GAVE 'occupied' ITS WRITER and widened this in the same PR — the
    # ScheduledMessageKind rule MET rather than waived. Its producer is an open
    # `fitting_room_assignments` row, derived on read exactly like the other two,
    # and the set-equality assertions in test_floor_service.py and
    # test_floor_api.py are what keep the next value honest the same way.
    #
    # ⚠ 'occupied' BEATS 'break'. A staffer standing in a fitting room with a
    # client is not «בהפסקה» — the break is a stale toggle nobody cleared, and a
    # shift manager looking for help would be told something she can see is
    # false. `break_started_at` stays on the wire regardless, so a card can still
    # say she forgot to end one. Declined a fourth combined status: two
    # orthogonal facts in one enum is the shape that forces the impossible-tuple
    # conversation later.
    AVAILABLE = "available"
    BREAK = "break"
    OCCUPIED = "occupied"


class AppointmentAudience(StrEnum):
    # brides_only on a type — or the tenant-wide brides_only toggle — hides it
    # from non-bride visitors (consumers: E3 slot engine, E2 storefront).
    ALL = "all"
    BRIDES_ONLY = "brides_only"


class DressMediaStatus(StrEnum):
    # pending is written at presign; ready only after confirm has verified the
    # object's magic bytes. The DB pins this exact set — a third value would put
    # an unverified upload on the gallery read path.
    PENDING = "pending"
    READY = "ready"


class MessageKind(StrEnum):
    # The DB pins this exact set (0007, widened by F19's migration); F16
    # consumes the lifecycle kinds.
    OTP = "otp"
    CONFIRMATION = "confirmation"
    REMINDER = "reminder"
    OWNER_CANCEL = "owner_cancel"
    OWNER_RESCHEDULE = "owner_reschedule"
    # F19 MD2: her money arrived after her seat had already been given away.
    # The deposit is held and the boutique will call — this body promises no
    # refund and names no new time, because neither is decided at send time.
    PAYMENT_RECEIVED_NO_SLOT = "payment_received_no_slot"


class MessageStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class BookingStatus(StrEnum):
    # The DB pins this exact set (0008, widened by F19's migration). Only
    # CANCELLED frees a seat — the slot-seat unique index and every occupancy
    # query exclude it and nothing else.
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    COMPLETED = "completed"
    # F19's deposit hold: the seat IS claimed, the money is not in yet. Because
    # every occupancy predicate excludes only CANCELLED, a held seat is an
    # occupied seat with no index change and no query change — which is the
    # entire reason this is a status rather than a booking_holds table.
    #
    # Nothing but the sweeper can move a row OUT of this state: every owner and
    # customer verb 409s on an unpaid hold, so the sweeper is the only writer
    # that turns it into CANCELLED and the webhook confirm is the only one that
    # turns it into CONFIRMED.
    PENDING_PAYMENT = "pending_payment"


class BookingCancelledBy(StrEnum):
    # The DB pins this exact set (0010, widened by F19's migration). F15's owner
    # cancel is the 'owner' writer; the value predates it so E4 needed no second
    # migration for that one.
    CUSTOMER = "customer"
    OWNER = "owner"
    # F19 MD5. Nobody cancelled it — the deposit hold ran out. Its own value
    # rather than reusing 'customer' because MD5 turns on telling them apart: an
    # abandoned checkout must not count against the boutique's headline
    # cancellation rate, and `cancelled_by` is the only column that can say so.
    EXPIRED = "expired"


class ScheduledMessageKind(StrEnum):
    # The DB pins this exact set (0010). E4's hold-expiry sweep and E5's offer
    # cascade widen the CHECK when they arrive — pre-adding speculative kinds is
    # exactly the un-lazy thing (D9).
    REMINDER = "reminder"


class ScheduledMessageStatus(StrEnum):
    # The DB pins this exact set (0010). CANCELLED covers both "the booking was
    # cancelled" and "the claim-time re-check found the appointment already
    # started" — neither is a delivery failure, so neither is FAILED.
    PENDING = "pending"
    SENT = "sent"
    CANCELLED = "cancelled"
    FAILED = "failed"


class GatewayCredentialStatus(StrEnum):
    # The DB pins this exact set (0012). There is deliberately no 'unvalidated':
    # credentials are pinged BEFORE they are stored (D4), so an unvalidated
    # stored credential is not a state the schema can represent — and
    # last_validated_at NOT NULL is the same decision spelled in the DDL.
    VALID = "valid"
    INVALID = "invalid"


class PaymentStatus(StrEnum):
    # The DB pins this exact set (0012). Recorded departure from the
    # ScheduledMessageKind "no speculative values" rule (Risk 6): F17 ships a
    # writer for PENDING and PAID only, and F19's brief names every remaining
    # transition — sweeper expiry, refund-due, forfeit, manual refund. If F19
    # renames one the correction is a single migration.
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUND_DUE = "refund_due"
    REFUNDED = "refunded"
    FORFEITED = "forfeited"


class AuditAction(StrEnum):
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    # F15's owner console (D2). audit_log.action is plain TEXT with no CHECK
    # (0003), so these need no migration. One value per action rather than a
    # single booking_status_changed carrying the pair in `details`: a filtered
    # read stays one WHERE instead of a JSONB predicate.
    BOOKING_CONFIRMED = "booking_confirmed"
    BOOKING_CANCELLED = "booking_cancelled"
    BOOKING_NO_SHOW = "booking_no_show"
    BOOKING_COMPLETED = "booking_completed"
    BOOKING_RESCHEDULED = "booking_rescheduled"
    BOOKING_PHONE_CORRECTED = "booking_phone_corrected"
    BOOKING_LINK_RESENT = "booking_link_resent"
    # F34's live shift board (D8). Same fact as every block here: audit_log.action
    # is plain TEXT with no CHECK (0003), so these need no migration.
    #
    # The undo keeps its own value rather than folding into BOOKING_CHECKED_IN
    # with a flag in `details`, for the reason the BOOKING_* block above already
    # gives: the question this table gets asked is "who recorded that she
    # arrived, and who took it back", and each stays one WHERE action = ….
    BOOKING_CHECKED_IN = "booking_checked_in"
    BOOKING_CHECK_IN_UNDONE = "booking_check_in_undone"
    # F51's owner-only staff section (D8). Same fact as the BOOKING_* block above:
    # audit_log.action is plain TEXT with no CHECK, so these need no migration.
    # Role change and password reset keep their own values rather than folding
    # into STAFF_UPDATED, because those are the two questions a security audit
    # actually asks of this table — "who was made an owner" and "whose password
    # did someone else change" — and each stays one WHERE action = ….
    STAFF_CREATED = "staff_created"
    STAFF_UPDATED = "staff_updated"
    STAFF_ROLE_CHANGED = "staff_role_changed"
    STAFF_PASSWORD_RESET = "staff_password_reset"
    STAFF_DEACTIVATED = "staff_deactivated"
    # F57's floor breaks (D8). Same fact as every block above: audit_log.action is
    # plain TEXT with no CHECK (0003), so these need no migration.
    #
    # These two rows are the ONLY record that a break happened — D2 ships no
    # break history table and nothing reads them yet (F53's activity log is the
    # first read surface). That is why the END carries
    # `previous_break_started_at`: ending a break destroys the only copy of when
    # it began, so a row without it records that something stopped and cannot say
    # what.
    STAFF_BREAK_STARTED = "staff_break_started"
    STAFF_BREAK_ENDED = "staff_break_ended"
    # F17's payment gateway. Same fact as the two blocks above: audit_log.action
    # is plain TEXT with no CHECK (0003), so these need no migration.
    #
    # The first four carry a real actor_id and commit in the SAME tenant_session
    # as the write they describe. GATEWAY_VALIDATED exists because the
    # invalid -> valid flip is the transition that RE-ENABLES money movement for
    # the boutique (D26) — auditing only the failure would leave the recovery,
    # the state change an incident review most wants to place in time, with no
    # row at all.
    GATEWAY_CONNECTED = "gateway_connected"
    GATEWAY_DISCONNECTED = "gateway_disconnected"
    GATEWAY_VALIDATED = "gateway_validated"
    GATEWAY_VALIDATION_FAILED = "gateway_validation_failed"
    # The last four have NO actor — an unauthenticated caller reached them —
    # and are failure-path writes, so they must COMMIT BEFORE the raise or the
    # return (.memory/patterns/commit-before-raise-in-tenant-session.md, which
    # names "future booking/payment failure records" as exactly this class).
    #
    # GATEWAY_PAYMENT_DECLINED is the one that is NOT an anomaly: a signed
    # `paid=false` delivery is the ordinary decline notification every PSP posts
    # to the success URL. It is audited anyway because it is the only record that
    # a charge was ATTEMPTED and refused — the row it describes stays 'pending'
    # and is otherwise indistinguishable from a hold nobody ever paid.
    GATEWAY_WEBHOOK_REJECTED = "gateway_webhook_rejected"
    GATEWAY_AMOUNT_MISMATCH = "gateway_amount_mismatch"
    GATEWAY_PAYMENT_DECLINED = "gateway_payment_declined"
    # A SECOND, distinct provider transaction against a row already paid — two
    # real charges for one booking. Its own value rather than a flavour of
    # LATE_SETTLEMENT because it is the one row a reconciliation actually
    # searches for, and one WHERE action = … is the whole point of the split.
    GATEWAY_DUPLICATE_TRANSACTION = "gateway_duplicate_transaction"
    GATEWAY_LATE_SETTLEMENT = "gateway_late_settlement"
    # F19's deposit flow. Same fact as every block above: audit_log.action is
    # plain TEXT with no CHECK (0003), so these need no migration. The last two
    # have NO actor and are failure-path writes, so they follow the
    # commit-before-raise pattern the four above them use.
    #
    # The hold's own lifecycle. OPENED and EXPIRED are separate values rather
    # than one DEPOSIT_HOLD row with a state in `details` for the reason the
    # BOOKING_* block gives: "how many holds did we open and how many did we
    # lose" is the question this table gets asked, and each stays one WHERE.
    DEPOSIT_HOLD_OPENED = "deposit_hold_opened"
    DEPOSIT_HOLD_EXPIRED = "deposit_hold_expired"
    # The late-payment fork, and the two values are the whole point of D5: the
    # money arrived after the seat was freed, and either it bought the seat back
    # or it did not. UNRESOLVED is the one a human must act on — the owner is
    # holding money for an appointment that no longer exists — so it must be
    # findable without a JSONB predicate over a shared action value.
    DEPOSIT_LATE_HONOURED = "deposit_late_honoured"
    DEPOSIT_LATE_UNRESOLVED = "deposit_late_unresolved"
    # A signature-valid webhook whose provider_session_id matches NO payment row.
    # Real money moved and the platform has no row to attach it to — an
    # unregistered or wrong-subdomain webhook URL is the likeliest cause. Without
    # this value the event's only trace is a 400 in an access log, because the
    # raise happens INSIDE `async with tenant_session` (which is session.begin())
    # and the transaction rolls back.
    GATEWAY_WEBHOOK_UNMATCHED = "gateway_webhook_unmatched"
    # MD4: the gateway was unreachable at checkout, so the booking was confirmed
    # with NO deposit taken. Not an error the bride ever sees — she gets an
    # ordinary confirmation — which is exactly why the owner needs a record that
    # this appointment is unsecured.
    GATEWAY_UNAVAILABLE_AT_CHECKOUT = "gateway_unavailable_at_checkout"
    # F53's customer CRM (D8). Same fact as every block above: audit_log.action
    # is plain TEXT with no CHECK (0003), so this needs no migration.
    #
    # ONE value, not CUSTOMER_NOTES_UPDATED + CUSTOMER_TAGS_UPDATED. The split
    # criterion this file applies is not "is this a distinct field" — it is "is
    # this a distinct question a security audit actually asks of this table",
    # and nobody will ever ask it "who edited tags but not notes". Which of the
    # two moved rides in `details` as FIELD NAMES ONLY.
    #
    # Field names only is a deliberate departure from STAFF_UPDATED's
    # {from, to} directly above, and the asymmetry is the point: a display name
    # is a label a staffer chose for herself, while customer notes are free text
    # written ABOUT A THIRD PARTY who never sees them. audit_log has no
    # retention policy and platform operators read across tenants, so copying a
    # bride's notes here would export them out of the tenant that owns them.
    CUSTOMER_UPDATED = "customer_updated"
    # F36's fitting rooms (D13). The SEVENTH block to rely on the same fact:
    # audit_log.action is plain TEXT with no CHECK (0003), so these need no
    # migration.
    #
    # FOUR values and not six. FITTING_ROOM_CREATED / _UPDATED are declined —
    # both are non-destructive, both are visible on the screen that performed
    # them, and created_at / updated_at already time them. The trail is still
    # write-only in v1, so every action added now is a line with no reader; these
    # four earn it because they are the only record of a destructive or an
    # occupancy-changing act.
    #
    # FITTING_DRESS_ADDED / _REMOVED are declined too, and on a different
    # ground: the binding ROW is the record. It is soft-deleted rather than
    # dropped, so it survives with `deleted_at` AND `removed_by` stamped and
    # answers what was in the room, when it left and who took it out — from the
    # table itself, at a volume (a dozen per fitting) that would swamp these four.
    #
    # A NO-OP WRITES NO ROW: a second release, a claim that resolved to the
    # caller's own existing assignment, and a duplicate dress add all changed
    # nothing, and a row asserting otherwise would be a lie about a person.
    FITTING_ROOM_CLAIMED = "fitting_room_claimed"
    FITTING_ROOM_RELEASED = "fitting_room_released"
    # `details` carries {"from", "to"} — STAFF_ROLE_CHANGED's shape — because the
    # handover's single UPDATE DESTROYS the only copy of who held the room. `from`
    # must be captured into a local before the writer runs.
    FITTING_ROOM_HANDED_OVER = "fitting_room_handed_over"
    # Carries the LABEL and not only the id, for previous_break_started_at's
    # reason: the row it names is soft-deleted and its label may be re-typed onto
    # a new room tomorrow, so an id alone records that something was removed and
    # cannot say what.
    FITTING_ROOM_DELETED = "fitting_room_deleted"


class PlatformAuditAction(StrEnum):
    TENANT_PROVISIONED = "tenant_provisioned"
    TENANT_PROVISION_FAILED = "tenant_provision_failed"
    TENANT_SUSPENDED = "tenant_suspended"
    OWNER_PASSWORD_RESET = "owner_password_reset"
    # F16's one-time deploy step (D10). platform_audit_log.action is plain TEXT
    # with no CHECK (0004), so this needs no migration.
    BOOKING_LINKS_BACKFILLED = "booking_links_backfilled"
