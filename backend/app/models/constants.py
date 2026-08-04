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


class SosStatus(StrEnum):
    # F37. The DB PINS this exact set (0021's sos_alerts_status_check, held
    # byte-identical in test_migrations.py), unlike StaffCardStatus directly
    # above — because unlike a card status this one is STORED, and the whole
    # first-accept-owns guarantee is a conditional UPDATE whose predicate names
    # one of these values.
    #
    # FOUR values and not five. There is deliberately no 'escalated' and no
    # 'stalled': both are read-time predicates over a row and a clock (D6), so
    # neither has an instant at which it happens or a writer to hang it on.
    # Adding either as a status would make escalation a write on a read path,
    # which is the design this feature explicitly rejects.
    #
    # RESOLVED and CANCELLED are separate terminal values rather than one
    # `closed` with a reason: they mean different things to the person who
    # pressed them («she got help» vs «false alarm»), the verbs that reach them
    # have different predicates — resolve from either live state, cancel from
    # `open` ONLY — and cancelling an ACCEPTED alert is a 409 precisely because
    # a colleague is already walking to that curtain.
    OPEN = "open"
    ACCEPTED = "accepted"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class TicketStage(StrEnum):
    # F41's atelier board. NOT pinned by the DB and deliberately not: there is no
    # stored value for a CHECK to constrain. The state is DERIVED from five
    # nullable TIMESTAMPTZ columns on alteration_tickets (pre-decided #39's
    # mechanism, relabelled by the 2026-07-31 ATELIER ruling), and StaffCardStatus
    # above is the shipped precedent for a derived, DB-unpinned wire enum.
    #
    # DECLARATION ORDER IS THE TOTAL ORDER and D3's predicate builder reads it.
    # A member inserted in the MIDDLE changes the semantics of every advance and
    # every undo in the feature — the conditional write is
    # `AND <every column after the target> IS NULL`, which is spelled from this
    # order and nowhere else. test_the_declaration_order_is_the_total_order is
    # what makes that a red test rather than a silent behaviour change.
    INTAKE = "intake"
    IN_PROGRESS = "in_progress"
    QC = "qc"
    READY = "ready"
    DELIVERED = "delivered"


class EffortBand(StrEnum):
    # Q13's five, verbatim. NOT pinned by the DB: what persists is
    # alteration_tickets.effort_minutes, and a band is only ever an INPUT
    # affordance — the client never sends a number, so there is no request shape
    # in which 37 minutes reaches the row.
    #
    # The MINUTES are what persist, never the label, which is why the table has
    # no effort_band column: a boutique that re-tunes half_day from 240 to 300
    # must not silently re-value every ticket already estimated. The consequence
    # is that a stored effort_minutes may match no current band, and the board
    # renders that honestly.
    THIRTY_MIN = "thirty_min"
    ONE_HOUR = "one_hour"
    TWO_HOURS = "two_hours"
    HALF_DAY = "half_day"
    FULL_DAY = "full_day"


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
    # F58's floor dispatch (D13). No migration, same as every block above.
    #
    # ONE value for both dispatch verbs, with the mode in `details`, and that is
    # CUSTOMER_UPDATED's split criterion rather than BOOKING_*'s: the question
    # this table gets asked is "who put whom in which room", and nobody will
    # ever ask it "who used the take-next button but not the assign one". The
    # row already names the ticket, the room, the assignment and the staffer, so
    # a second action value would carry no information the first does not.
    #
    # ⚠ A dispatch writes THIS row and NOT a second FITTING_ROOM_CLAIMED: the
    # claim row's whole content is a subset of this one's, and two rows for one
    # act is the noise D13 declined FITTING_ROOM_CREATED over.
    #
    # A NO-OP WRITES NO ROW, and on this path that is not a guard but a
    # consequence: `_audit.record` is inside the transaction, so a lost race
    # rolls the row back with the ticket write (D3a). The trail cannot claim a
    # dispatch that did not happen.
    #
    # NO NAME AND NO PHONE in `details`, ever. audit_log has no retention policy
    # and platform operators read across tenants.
    QUEUE_TICKET_DISPATCHED = "queue_ticket_dispatched"
    # `{ticket, called_at}`. A SECOND call writes NO row — the summons is
    # idempotent by predicate (`called_at IS NULL`), she wanted her called and
    # she is called, and a {called → called} entry would be noise in a trail this
    # area has only four rows in.
    QUEUE_TICKET_CALLED = "queue_ticket_called"
    # `{ticket, skip_count, status}`. The count and the RESULTING status ride in
    # `details` so a removal-by-second-skip is legible without a fifth action
    # value — "who put her out of the queue" is answered by this row or by
    # QUEUE_TICKET_REMOVED, and the two are the same question asked of two
    # controls.
    QUEUE_TICKET_SKIPPED = "queue_ticket_skipped"
    # `{ticket}`. This and the row above close F33's Risk 12 by name: "'who
    # called her forward' and 'who removed her' are the two questions that will
    # want rows".
    QUEUE_TICKET_REMOVED = "queue_ticket_removed"

    # F41's atelier board (D11). Same fact as every block above: audit_log.action
    # is plain TEXT with no CHECK (0003), so these six need no migration.
    #
    # ONE STAGE_ADVANCED VALUE RATHER THAN FIVE, and the split rule is followed
    # rather than broken. The questions this table gets asked here are "who moved
    # this ticket, and when" — both one WHERE action = … plus the row's own
    # `details`. The question a per-stage split would serve, "how many tickets
    # reached delivered", is answered from the five TIMESTAMP COLUMNS and never
    # from audit_log, which is the whole point of the derived-state mechanism.
    # Five values would buy a query nobody runs.
    #
    # ⚠ STAGE_UNDONE carries `previous_stamp` and it is LOAD-BEARING in a way
    # `previous_break_started_at` was not: the five timestamps ARE the trail, so
    # an un-stamp is the one write in this feature that DESTROYS history, and
    # this row is the only place it survives. It must be captured into a local
    # BEFORE the write — the ORM's `evaluate` synchronization stamps NULL onto
    # the very instance the reader is about to read.
    #
    # TICKET_UPDATED's `details` carries changed key NAMES AND NEVER VALUES:
    # `notes` may hold a bride's measurements, and audit_log has a different
    # retention clock from the row it describes. Same asymmetry, same reason as
    # CUSTOMER_UPDATED directly above.
    #
    # ⚠ AND A SEVENTH, added at review: CUSTOMER_RENAMED. Intake routes through
    # `CustomersRepository.upsert`, which assigns `existing.name = name`
    # UNCONDITIONALLY, so a seamstress typing «מ» for a phone stored as «מיכל
    # לוי» rewrites a row that F53 renders on a screen she cannot open — and the
    # atelier router is the first writer of `customers.name` whose actor does not
    # control the phone (the booking path proves it with an OTP first). D6
    # accepts the rename; this makes it recoverable. `details` names the FIELD
    # and never either spelling, CUSTOMER_UPDATED's rule for CUSTOMER_UPDATED's
    # reason, and `entity` is the CUSTOMER's id rather than the ticket's, because
    # the customer is the row that changed.
    ATELIER_CUSTOMER_RENAMED = "atelier_customer_renamed"
    ATELIER_TICKET_CREATED = "atelier_ticket_created"
    ATELIER_TICKET_UPDATED = "atelier_ticket_updated"
    ATELIER_TICKET_ASSIGNED = "atelier_ticket_assigned"
    ATELIER_TICKET_STAGE_ADVANCED = "atelier_ticket_stage_advanced"
    ATELIER_TICKET_STAGE_UNDONE = "atelier_ticket_stage_undone"
    ATELIER_TICKET_DELETED = "atelier_ticket_deleted"
    # ⚠ F42's, and it is the EIGHTH member of a seven-member block. No migration:
    # audit_log.action is plain TEXT with no CHECK (0003_auth.py:71-79), and this
    # is the eighth block to rely on that.
    #
    # It carries {"from": int|null, "to": int|null} captured BEFORE the write —
    # the UPDATE's `evaluate` synchronization stamps the new hours onto the very
    # instance the `from` is read off — with `entity` = the seamstress's id. A
    # no-op writes no row at all: setting the hours she already has changed
    # nothing and a row claiming otherwise names an act nobody performed.
    ATELIER_CAPACITY_SET = "atelier_capacity_set"

    # F37's SOS paging (D13). The EIGHTH block to rely on the same fact:
    # audit_log.action is plain TEXT with no CHECK (0003), so these four need no
    # migration.
    #
    # ⚠ SOS_RAISED's `details` carries BOTH `requested_target` AND `target`, and
    # the pair is the whole point. The reroute writes NULL into
    # `target_staff_user_id`, destroying the only record of whom she actually
    # tried to page — `previous_break_started_at`'s argument and the handover
    # `from` argument, third instance. Without the pair the trail records that a
    # page went to the shift manager and cannot say Dana was meant to get it,
    # which is the single most useful thing a pilot review could ask this table.
    #
    # ⚠ SOS_RESOLVED carries `from_status`, CAPTURED INTO A LOCAL BEFORE THE
    # WRITER RUNS. This is the fourth appearance of the identity-map trap in this
    # repo and the only one where the destroyed value is a STATE rather than a
    # timestamp: the UPDATE is ORM-enabled DML whose `evaluate` synchronization
    # stamps 'resolved' onto the very instance the reader is about to read, so a
    # capture placed afterwards records `resolved -> resolved` and empties the
    # row of its whole informational content.
    #
    # A NO-OP WRITES NO ROW: a re-accept by the current owner, a second resolve,
    # a resolve of an already-cancelled alert. A row asserting otherwise would be
    # a lie about a person.
    #
    # ⚠ SOS_ESCALATED IS DECLINED and this is where a reader will look for it.
    # There is no escalation EVENT — escalation is a predicate over a row and a
    # clock (D6), so there is no instant at which anything happens and no writer
    # to hang an action on. Recording one from a read path would be a write on a
    # read path, which is exactly what D6 rejects.
    SOS_RAISED = "sos_raised"
    SOS_ACCEPTED = "sos_accepted"
    SOS_RESOLVED = "sos_resolved"
    SOS_CANCELLED = "sos_cancelled"


class PlatformAuditAction(StrEnum):
    TENANT_PROVISIONED = "tenant_provisioned"
    TENANT_PROVISION_FAILED = "tenant_provision_failed"
    TENANT_SUSPENDED = "tenant_suspended"
    OWNER_PASSWORD_RESET = "owner_password_reset"
    # F16's one-time deploy step (D10). platform_audit_log.action is plain TEXT
    # with no CHECK (0004), so this needs no migration.
    BOOKING_LINKS_BACKFILLED = "booking_links_backfilled"
