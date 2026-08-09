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


class StaffNotificationKind(StrEnum):
    # F35. The DB PINS this exact set (0030's staff_notifications_kind_check,
    # held byte-identical in test_migrations.py), so a fourth kind is a migration
    # and therefore a review.
    #
    # THREE values, and every one of them is «somebody else made you responsible
    # for a person». That is the whole membership rule: `handover` is in because
    # it is `assign` with the customer already in the room, and a bell that rang
    # for one and not the other would be a bug nobody could state. `accept_sos`,
    # `resolve_sos`, `claim`, `release`, `call`, `skip` and `remove` are all OUT
    # because none of them hands a person to somebody else.
    #
    # `dispatch_assigned` covers BOTH `take_next` and `assign`: the recipient's
    # sentence is identical («somebody sent you a customer») and the two verbs
    # differ only in which ticket the manager picked, which is her business and
    # not the recipient's.
    #
    # ⚠ The console SKIPS a kind it does not know rather than rendering the raw
    # enum, so a fourth value shipped server-first degrades to a missing row and
    # never to «sos_targeted» on a staffer's screen.
    DISPATCH_ASSIGNED = "dispatch_assigned"
    ROOM_HANDED_OVER = "room_handed_over"
    SOS_TARGETED = "sos_targeted"


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


class WaitlistEntryStatus(StrEnum):
    # The DB pins this exact set (F22's migration, `waitlist_entries_status_check`)
    # and test_the_waitlist_definitions_are_pinned holds the deparsed literal so
    # the next widening collides with a review.
    #
    # F22 writes exactly two — WAITING (the join's DB default) and CANCELLED
    # (the owner cancel). The other three are F23's lifecycle, shipped in the
    # CHECK now so the cascade inherits a contract it cannot re-litigate:
    # waiting -> offered -> claimed | expired | cancelled. Whether EXPIRED is
    # terminal or re-queues is F23's decision; every state it could need is
    # representable today.
    WAITING = "waiting"
    OFFERED = "offered"
    CLAIMED = "claimed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class VisitType(StrEnum):
    # The DB pins this exact set (F33's migration). Bride-priority ordering is
    # explicitly NOT built (e6-instore-realtime.md:74): this column records what
    # she is here for, and nothing sorts on it.
    BRIDE = "bride"
    EVENING = "evening"


class BookingSource(StrEnum):
    """Which surface created a booking. The DB pins this exact set
    (`bookings_source_check`, 0025).

    It is the DISCRIMINATOR for `bookings_terms_evidence_check`, not a label: a
    NULL `terms_version_accepted` is legal on WALK_IN and on nothing else, and
    without this column that NULL would also be indistinguishable from a
    storefront booking that lost its evidence to a bug.

    F50's remote/scheduled half will want a third member ('owner'). Adding it here
    and to the source CHECK is NOT enough on its own — the terms CHECK enumerates
    the exemption rather than the requirement, so a third value with no terms
    evidence is a FAILING INSERT until its author decides about terms on purpose.
    That failure is the hand-off, and it is deliberate.
    """

    STOREFRONT = "storefront"
    WALK_IN = "walk_in"


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


class MarketingConsentSource(StrEnum):
    """Which surface took the consent. The DB pins this exact set —
    `customers_marketing_consent_source_check` (0024) — and it has ONE member
    on purpose.

    F33's walk-in check-in is deliberately NOT here (plan DR-10). Its opt-in
    lives on `queue_tickets.marketing_opt_in_at` and stays there: that form has
    no possession proof of any kind, so promoting it into this column would
    launder an unverified submission into evidence that a specific woman
    consented — degrading every other row in a column whose only job is to be
    provable under the Spam Law. Adding `'walk_in'` here means widening the
    CHECK in a migration, in the feature that builds the verified promotion.
    """

    BOOKING_FORM = "booking_form"


class ScheduledMessageKind(StrEnum):
    # The DB pins this exact set (0010, widened by 0032). The rule 0010 wrote —
    # a kind lands with its producer, never speculatively — is MET here rather
    # than waived: F23's cascade writes WAITLIST_OFFER rows and `drain_due`
    # branches on it in the same change.
    #
    # ⚠ A WAITLIST_OFFER row's subject is a waitlist ENTRY, not a booking
    # (`ck_scheduled_messages_subject` is an XOR). Anything reading a
    # `scheduled_messages` row must branch on this field before dereferencing
    # `booking_id`, which is nullable from 0032 onward.
    REMINDER = "reminder"
    WAITLIST_OFFER = "waitlist_offer"


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
    # F50's owner-created walk-in (D6). Same fact as every block here:
    # audit_log.action is plain TEXT with no CHECK (0003), so this needs no
    # migration.
    #
    # This row is the ONLY record of WHO created a booking that carries no terms
    # evidence, which is what makes it the audit entry that most earns its place
    # in this area. Its `details` carry the two ids and NEITHER the phone NOR the
    # name — `customer_id` resolves both, and F20's rule for its own rows is
    # `phone_last4` and never the number.
    BOOKING_WALK_IN_CREATED = "booking_walk_in_created"
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
    # F38's profile photo, three rows over a two-phase upload. Each carries the
    # STORAGE KEY, and that is the load-bearing part rather than decoration:
    # every object delete in this feature is best-effort, so on the path where
    # one fails these rows are the ONLY durable record of which object was
    # orphaned. audit_log.action is plain TEXT with no CHECK (0003), so they need
    # no migration.
    STAFF_PHOTO_PRESIGNED = "staff_photo_presigned"
    STAFF_PHOTO_CONFIRMED = "staff_photo_confirmed"
    STAFF_PHOTO_DELETED = "staff_photo_deleted"
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
    # F42's second, and the NINTH member. It carries the whole NEW `atelier`
    # block and NO `from`, with `entity` = the tenant's id: the trail IS the
    # history, so the previous mapping is the previous row's value, and computing
    # a diff would need exactly the read-modify-write `merge_settings`' single
    # atomic statement exists to avoid. These are boutique configuration and
    # carry no personal data, so F41's names-only rule does not bind — and the
    # numbers are the whole point, because the question this row answers is
    # "what was «חצי יום» worth when that ticket was estimated".
    ATELIER_SETTINGS_UPDATED = "atelier_settings_updated"
    # F27's, and the TENTH block to rely on the same fact: audit_log.action is
    # plain TEXT with no CHECK (0003), so this needs no migration.
    #
    # F42 left `profile` and `toggles` unaudited on the recorded principle that a
    # feature audits the key it OWNS and does not widen a gap it did not create.
    # F27 owns `toggles` now — it is the feature that made the matrix, the deep
    # merge and the registry — so the same «nobody can say who or when» argument
    # that justified ATELIER_SETTINGS_UPDATED binds one key over, and harder:
    # `deposits_enabled` decides whether the boutique collects money at all.
    # `profile` STAYS unaudited; F27 does not widen past its own key either, and
    # `test_audit_coverage.py`'s partial-audit note records exactly that split.
    #
    # `details` is THE PATCH — the changed keys only, with `entity` = the
    # tenant's id. Same rule and same reason as its neighbour above: the trail IS
    # the history, so the previous value is the previous row's, and computing a
    # diff would need precisely the read-modify-write `merge_settings`' single
    # atomic statement exists to avoid. Storing the MERGED block instead would
    # also make every row read as a full rewrite of a matrix on which the owner
    # moved one switch.
    TOGGLES_UPDATED = "toggles_updated"

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

    # F20's retention job (D8). The NINTH block to rely on the same fact:
    # audit_log.action is plain TEXT with no CHECK (0003), so these six need no
    # migration.
    #
    # SIX values and not one `retention_applied` with the class in `details`,
    # because this file's split criterion is "is this a distinct question a
    # compliance audit actually asks", and here it plainly is: "show me that the
    # message log was purged on its clock" is the §17B evidence for ONE data
    # class, and an auditor asking it should not have to write a JSONB predicate
    # to separate it from the OTP sweep.
    #
    # The suffix is the POLICY NAME, and `app.privacy.retention.audit_action`
    # resolves it through this enum — so a policy added without a member here is
    # a ValueError in `test_retention_policies.py`, not a silent absence at 03:00
    # inside a tenant loop.
    #
    # A RUN THAT TOUCHED NOTHING WRITES NO ROW. Six rows per tenant per hour of
    # "deleted 0" is permanent bloat in the one table that has no retention class
    # of its own — and `audit_log` has none deliberately, because a clock on the
    # evidence would eventually erase the proof of the erasures it records.
    #
    # `details` carries counts and table NAMES only. Never a customer name, never
    # a phone: audit_log has no retention policy and platform operators read
    # across tenants, which is CUSTOMER_UPDATED's rule for CUSTOMER_UPDATED's
    # reason.
    # F20's two subject routes. Same fact again: `audit_log.action` is plain
    # TEXT with no CHECK (0003), so neither needs a migration.
    #
    # THE EXPORT HAS ITS OWN ACTION, and that is D19 correcting a first draft
    # that audited only the mutation. Checklist row 38 is "data ACCESS by
    # operators", not "data changes by operators" — assembling a named person's
    # whole record into one downloadable document is the access it means.
    #
    # `details` on both carries `customer_id` + `phone_last4` + a capped
    # `reason`, and NEVER a full number or a name (`privacy/service._last4`).
    # This table has no retention class at all — deliberately, because a clock
    # on the evidence would eventually erase the proof of the erasures it
    # records — so a full phone written here would be a permanent copy of the
    # exact identifier the erase exists to destroy.
    PRIVACY_SUBJECT_EXPORTED = "privacy_subject_exported"
    PRIVACY_SUBJECT_ERASED = "privacy_subject_erased"
    # The §30A revocation, and it is written on BOTH arms.
    #
    # `PLATFORM_DPA_HE` publishes, to every bride on every boutique's /privacy
    # page, that «פעולות שינוי ומחיקה שהצוות מבצע במידע של לקוחה נרשמות ביומן
    # פעילות» — staff changes and deletions to a customer's data are recorded in
    # an activity log. This is a staff-performed change to a customer's data, and
    # per Gate 1 Q4 it is the ONE privacy route a non-owner can reach, so it is
    # the route with the widest role exposure and was the one with no trail.
    #
    # Written ONLY when `changed` is true, which is what answers the bloat
    # objection the route's first draft raised: the statement is self-falsifying
    # (`IS NOT NULL` / `IS NULL` guards), so a repeat writes nothing.
    #
    # The phone arm needs it more than the id arm, not less: that arm NULLs
    # `queue_tickets.marketing_opt_in_at`, so after it runs the row is
    # indistinguishable from a walk-in who never ticked the box. Without this row
    # the boutique can evidence neither that she asked nor that it complied.
    # `details` carries `phone_last4` and never the number.
    PRIVACY_MARKETING_WITHDRAWN = "privacy_marketing_withdrawn"

    # F22's owner cancel (D5). Same fact as every block here: audit_log.action
    # is plain TEXT with no CHECK (0003), so this needs no migration. ONE
    # member — the join is anonymous and writes no audit row, and `details`
    # carries {entry_id, day, appointment_type_id} and NO phone (F20's
    # phone_last4 rule made moot by carrying no phone at all).
    WAITLIST_ENTRY_CANCELLED = "waitlist_entry_cancelled"

    RETENTION_OTP_CODES = "retention_otp_codes"
    RETENTION_SESSIONS = "retention_sessions"
    RETENTION_QUEUE_TICKETS = "retention_queue_tickets"
    RETENTION_MESSAGE_LOG = "retention_message_log"
    RETENTION_BOOKINGS = "retention_bookings"
    RETENTION_CUSTOMERS = "retention_customers"
    # F22's waitlist purge — `audit_action()` resolves `retention_{policy.name}`
    # through this enum, so the member lands in the same commit as the policy.
    RETENTION_WAITLIST_ENTRIES = "retention_waitlist_entries"
    # F38's ex-staff scrub, the EIGHTH class. `audit_action()` resolves
    # `retention_{policy.name}` through this enum and RAISES on a missing member,
    # so this line lands in the same commit as the policy or the registry test
    # goes red — which is the point: without the member the failure would be a
    # ValueError at 03:00, inside a tenant loop, three tables into an
    # irreversible run.
    RETENTION_STAFF_USERS = "retention_staff_users"

    # F21's catalog (D6), and it is the TENTH block to rely on the same fact:
    # audit_log.action is plain TEXT with no CHECK (0003_auth.py:71-79), so these
    # nine need no migration. F21 ships none at all.
    #
    # WHY NINE AND NOT FOUR. Every other block in this file has had to argue a
    # value DOWN — D13 declined FITTING_ROOM_CREATED/_UPDATED because a row and
    # its created_at already answered the question. That argument does not reach
    # here, and the difference is the audience: a fitting room is furniture only
    # the floor sees, while `dresses` and `dress_media` are the boutique's PUBLIC
    # STOREFRONT. A price that changed, a gown that vanished from the catalogue
    # and a photo that was replaced are all things a customer saw, and "who did
    # that, and when" is the question this table exists to answer for exactly the
    # surface the customer can reach. Before F21 catalog had zero rows of any
    # kind, which is checklist row 38's whole finding.
    #
    # `details` NEVER carries personal data — it cannot: nothing in this module
    # is about a person. Dress name, size label, content type, byte size and
    # storage key are boutique inventory, and the same rule that lets
    # ATELIER_SETTINGS_UPDATED carry its numbers applies unchanged.
    DRESS_CREATED = "dress_created"
    DRESS_UPDATED = "dress_updated"
    # Soft delete and its inverse. Two values rather than one with a flag, for
    # the BOOKING_CHECKED_IN / _CHECK_IN_UNDONE reason: "what did we take off the
    # website" and "what did we put back" are two questions, each one WHERE.
    # ARCHIVED carries the dress NAME as well as its id — FITTING_ROOM_DELETED's
    # argument, and it binds harder here, because the row it names is the one the
    # console stops listing by default.
    DRESS_ARCHIVED = "dress_archived"
    DRESS_RESTORED = "dress_restored"
    # ONE value for the whole matrix, with the resulting size labels in `details`.
    # `replace_variants` is a full replacement inside one transaction — there is
    # no per-size event to record — and the question asked here is "what was in
    # stock when she was told it was", which the resulting set answers and a
    # per-row split would not.
    DRESS_VARIANTS_REPLACED = "dress_variants_replaced"
    # ⚠ MEDIA_PRESIGNED IS AUDITED AND IT IS THE LEAST OBVIOUS OF THE NINE.
    # A successful presign authorises a 10 MiB write into OUR bucket under a
    # policy that CANNOT BE REVOKED for PRESIGN_TTL_SECONDS (service.py:658-660
    # states it). The row that lands afterwards may never be confirmed and may
    # never be visible anywhere, so this is the only record that the credential
    # was ever issued — which is exactly the shape of thing an incident review
    # asks for. It rides the same transaction as `insert_pending`, so a presign
    # refused by the limit or by a missing dress writes nothing.
    DRESS_MEDIA_PRESIGNED = "dress_media_presigned"
    # A RE-CONFIRM WRITES NO ROW. Confirm is idempotent by design (the
    # `already_ready` short-circuit and the `status == PENDING` guard), and a
    # retried confirm after a lost response performed no act. The write is inside
    # the promote branch for that reason, not beside it.
    DRESS_MEDIA_CONFIRMED = "dress_media_confirmed"
    # Carries `storage_key`, and that is the one field here doing real work: the
    # object delete is best-effort by design (`_best_effort_delete` swallows a
    # storage outage), so on the failure path this row is the only durable record
    # of which object was orphaned. `logger.warning` is the other, and a log line
    # is not evidence.
    DRESS_MEDIA_DELETED = "dress_media_deleted"
    DRESS_MEDIA_REORDERED = "dress_media_reordered"
    # F28's date-bound reservations (D8). Same fact as every block above:
    # audit_log.action is plain TEXT with no CHECK (0003), so these need no
    # migration.
    #
    # These two rows are the ONLY record of who took a gown off the floor for a
    # week and who put it back — there is no edit verb, so a corrected window is
    # a delete followed by a create and the pair must be separately readable.
    # Their `details` carry the range and the two ids and NEITHER a name NOR a
    # phone: `customer_id` resolves both, and a name copied in here would outlive
    # the erase that scrubs the customer row.
    DRESS_RESERVATION_CREATED = "dress_reservation_created"
    DRESS_RESERVATION_DELETED = "dress_reservation_deleted"


class PlatformAuditAction(StrEnum):
    TENANT_PROVISIONED = "tenant_provisioned"
    TENANT_PROVISION_FAILED = "tenant_provision_failed"
    TENANT_SUSPENDED = "tenant_suspended"
    OWNER_PASSWORD_RESET = "owner_password_reset"
    # F16's one-time deploy step (D10). platform_audit_log.action is plain TEXT
    # with no CHECK (0004), so this needs no migration.
    BOOKING_LINKS_BACKFILLED = "booking_links_backfilled"
    # F20's operator-invoked retention run. platform_audit_log.action is plain
    # TEXT with no CHECK (0004), so this needs no migration.
    #
    # ONE value covering the armed run AND the `--dry-run` rehearsal, with the
    # mode in `details`. Unlike the per-tenant `audit_log` rows — which are the
    # TENANT's evidence about its own data, and are therefore suppressed for a
    # dry run and for a policy that touched nothing — this row is the record that
    # a HUMAN pointed an irreversible multi-tenant job at production, and that is
    # worth recording whether or not it wrote anything. A rehearsal that leaves
    # no trace is the one an incident review most wants to find.
    RETENTION_RUN = "retention_run"
    # F21's cross-tenant read (D6). platform_audit_log.action is plain TEXT with
    # no CHECK (0004), so this needs no migration.
    #
    # A READ with a row, and the only one in this enum. `list` returns every
    # boutique's slug, trading name and status in one output — a full
    # cross-tenant read whose `--operator` was already parsed and thrown away.
    # `target_tenant_id` is NULL because no single tenant is the subject; the
    # subject is all of them. `details` carries the COUNT and never the slugs:
    # the row records that someone enumerated the platform, and reproducing the
    # enumeration inside the audit table would be the leak twice over.
    TENANTS_LISTED = "tenants_listed"
    # F25's four. platform_audit_log.action is plain TEXT with no CHECK (0004),
    # so these need no migration — the third feature in a row to rely on it.
    #
    # The bootstrap pair. Creating or deactivating the credential that controls
    # every boutique on the platform is the highest-privilege act this system
    # has, and it is reachable ONLY from a shell (spec D2: no HTTP route mints an
    # operator, so the console's own compromise cannot).
    OPERATOR_CREATED = "operator_created"
    OPERATOR_DEACTIVATED = "operator_deactivated"
    # ⚠ TWO MEMBERS THE SPEC'S AUDIT CONTRACT DOES NOT LIST, and the deviation is
    # deliberate. The plan requires the create/deactivate refusals to COMMIT a
    # failure audit (duplicate active email; the last-operator refusal), and the
    # spec names only the four success/login actions — so the refusal would have
    # had to ride `OPERATOR_CREATED`. A row reading "operator_created" when no
    # operator was created is not a weaker record, it is a false one, in the one
    # book that is the sole evidence of who touched the platform's credentials.
    # `TENANT_PROVISIONED` / `TENANT_PROVISION_FAILED` is the shipped precedent
    # and this is it, unchanged. Still no migration: action is TEXT with no CHECK.
    OPERATOR_CREATE_FAILED = "operator_create_failed"
    OPERATOR_DEACTIVATE_FAILED = "operator_deactivate_failed"
    # The login pair, and they are STRICTER than their staff twins on purpose:
    # staff logins write to the tenant's own `audit_log`, which is that
    # boutique's evidence about its own people. The platform's front door has no
    # tenant, so it logs to the platform's book. `details` carries the attempted
    # email on the failure and NEVER a password or hash.
    OPERATOR_LOGIN = "operator_login"
    OPERATOR_LOGIN_FAILED = "operator_login_failed"
