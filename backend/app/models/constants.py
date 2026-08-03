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
    # 'occupied' is coming and is deliberately NOT here. F36 gives it a writer —
    # an open `fitting_room_assignments` row — and widens this in the SAME PR, the
    # ScheduledMessageKind rule. Shipping the literal now would put a status on
    # the wire that nothing in the product can ever produce, and the set-equality
    # assertion in test_floor_service.py is what makes that structurally
    # impossible rather than merely currently-unreached.
    AVAILABLE = "available"
    BREAK = "break"


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


class QueueTicketStatus(StrEnum):
    # The DB pins this exact set (F33's migration); F58 is the feature that
    # widens it, and test_the_queue_tickets_migration_pins_its_checks_and_its_one_index
    # holds the deparsed literal so that widening collides with a review.
    #
    # F33 writes only the WAITING default — every transition out of it is F58's,
    # which is why nothing in the shipped product can currently reach a terminal.
    # WAITING and IN_SERVICE are the live states; DONE and REMOVED are terminal
    # and are what stop the customer's poll.
    WAITING = "waiting"
    IN_SERVICE = "in_service"
    DONE = "done"
    REMOVED = "removed"


class VisitType(StrEnum):
    # The DB pins this exact set (F33's migration). Bride-priority ordering is
    # explicitly NOT built (e6-instore-realtime.md:74): this column records what
    # she is here for, and nothing sorts on it.
    BRIDE = "bride"
    EVENING = "evening"


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


class PlatformAuditAction(StrEnum):
    TENANT_PROVISIONED = "tenant_provisioned"
    TENANT_PROVISION_FAILED = "tenant_provision_failed"
    TENANT_SUSPENDED = "tenant_suspended"
    OWNER_PASSWORD_RESET = "owner_password_reset"
    # F16's one-time deploy step (D10). platform_audit_log.action is plain TEXT
    # with no CHECK (0004), so this needs no migration.
    BOOKING_LINKS_BACKFILLED = "booking_links_backfilled"
