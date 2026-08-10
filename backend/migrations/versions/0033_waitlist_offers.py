"""waitlist offers: offer columns on waitlist_entries, offer subject on scheduled_messages

Revision ID: 0033
Revises: 0032

Built as 0033 / down_revision 0031 — resolved from `alembic heads` on the day of
writing, and re-resolved immediately before the pre-push rebase (0018's header
records the renumber-at-rebase hazard this paragraph inherits, and 0026's own
header repeats it for this very table).

RE-PARENTED 0031 -> 0032 AT THAT REBASE, and this is the hazard above actually
firing. F38 merged while this branch was open and its 0032 ALSO named 0031 as
its parent. Two revisions naming one parent BRANCHES the history: `alembic
heads` then reports two heads and every db-marked test reds with a message that
points at nothing in the diff. House rule — whichever migration merges SECOND
re-parents onto the other. The chain is linear again: 0031 -> 0032 -> 0033.

ADDITIVE ONLY on two shipped tables. No RLS re-run: `ALTER TABLE … ADD COLUMN`
preserves the policies 0026 and 0010 installed, so
`test_every_tenant_id_table_has_forced_rls` stays green unedited. No sixth
`waitlist_entries.status` value — F22 shipped all five states in its CHECK
precisely so F23 would not have to widen it (spec D1, conflict 4).
"""

from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The offer bookkeeping 0026's header deferred to here. All four nullable:
    # a `waiting` entry has never been offered, and an `expired` one has had its
    # token and deadline cleared, so "no live offer" is spelled NULL rather than
    # by a sentinel nobody would remember to compare against.
    #
    # `offer_starts_at` is THE slot instant this offer names. One offer names one
    # instant (spec, Out of scope: multi-slot offers), which is what lets the
    # claim re-materialize exactly one grid position instead of a set.
    #
    # `offer_token_hash` is sha256 ONLY — the raw token lives in the SMS body and,
    # while the offer message is still pending, on `scheduled_messages.manage_token`
    # (its existing "raw link token while pending" semantics, cleared on every
    # terminal transition). Storing the raw value beside its own hash would put a
    # live credential in the forever-table, which is the same reasoning
    # `mask_manage_link` applies to `message_log`.
    op.execute(
        """
        ALTER TABLE waitlist_entries
          ADD COLUMN offered_at       TIMESTAMPTZ,
          ADD COLUMN offer_expires_at TIMESTAMPTZ,
          ADD COLUMN offer_starts_at  TIMESTAMPTZ,
          ADD COLUMN offer_token_hash TEXT
        """
    )
    # The claim's whole lookup, and collision-impossible by construction rather
    # than by a retry loop. UNIQUE and GLOBAL (no tenant_id leading column) on
    # purpose: `/w/{token}` resolves a tenant FROM the token, so a per-tenant
    # index could not serve it. Tenancy is still enforced — RLS makes a foreign
    # tenant's row unreadable, so a stolen token from another boutique 404s
    # exactly as an invented one does (pinned by test_waitlist_offer_token.py).
    op.execute(
        "CREATE UNIQUE INDEX idx_waitlist_entries_offer_token "
        "ON waitlist_entries (offer_token_hash) "
        "WHERE offer_token_hash IS NOT NULL AND deleted_at IS NULL"
    )
    # The cascade's expiry claim, once per tenant per 60-second tick. Leading
    # tenant_id because the sweep is per-tenant inside a tenant_session; the
    # `status = 'offered'` half is what keeps the index the size of the live
    # offers rather than of the whole retention window.
    op.execute(
        "CREATE INDEX idx_waitlist_entries_offer_expiry "
        "ON waitlist_entries (tenant_id, offer_expires_at) "
        "WHERE status = 'offered' AND deleted_at IS NULL"
    )

    # An offer has no booking. Pre-decided #16 rules that offers ride
    # `scheduled_messages` rather than growing a second poller, and this is the
    # honest price of that: the subject becomes one-of-two rather than always a
    # booking. The XOR CHECK is what stops it becoming neither or both.
    op.execute(
        """
        ALTER TABLE scheduled_messages
          ALTER COLUMN booking_id DROP NOT NULL,
          ADD COLUMN waitlist_entry_id UUID,
          ADD CONSTRAINT ck_scheduled_messages_subject
            CHECK ((booking_id IS NULL) <> (waitlist_entry_id IS NULL))
        """
    )
    op.execute("ALTER TABLE scheduled_messages DROP CONSTRAINT scheduled_messages_kind_check")
    op.execute(
        "ALTER TABLE scheduled_messages ADD CONSTRAINT scheduled_messages_kind_check "
        "CHECK (kind IN ('reminder','waitlist_offer'))"
    )
    # The offer half of the idempotency key, and it cannot interfere with the
    # booking half: `idx_scheduled_messages_pending_unique` is on
    # (tenant_id, booking_id, kind) and NULLs are distinct in a unique index, so
    # every offer row is invisible to it. Two indexes, two disjoint populations,
    # one guarantee each — a second cascade tick that re-offers the same entry
    # converges on an IntegrityError instead of double-texting her.
    op.execute(
        "CREATE UNIQUE INDEX idx_scheduled_messages_offer_pending_unique "
        "ON scheduled_messages (tenant_id, waitlist_entry_id, kind) "
        "WHERE deleted_at IS NULL AND status = 'pending' AND waitlist_entry_id IS NOT NULL"
    )

    # ⚠ A SECOND kind CHECK, on a different table, and it is not the same fact.
    # `scheduled_messages.kind` above says what may be QUEUED; `message_log.kind`
    # says what may be RECORDED as having been sent. 0016 widened this one for
    # F19's `payment_received_no_slot` in exactly this drop-then-add shape.
    #
    # Without it the offer send raises on its evidence row — after the provider
    # has already taken the message. `message_log.booking_id` is already nullable
    # (0007), so the offer's absent booking needs nothing else.
    op.execute("ALTER TABLE message_log DROP CONSTRAINT message_log_kind_check")
    op.execute(
        "ALTER TABLE message_log ADD CONSTRAINT message_log_kind_check "
        "CHECK (kind IN ('otp','confirmation','reminder','owner_cancel','owner_reschedule',"
        "'payment_received_no_slot','waitlist_offer'))"
    )


def downgrade() -> None:
    # The evidence rows go first: narrowing the CHECK is refused while any row
    # still holds the value, and an offer send that happened cannot be un-sent —
    # deleting its log line is the only way back, and it is why this downgrade is
    # a development affordance rather than a production one.
    op.execute("DELETE FROM message_log WHERE kind = 'waitlist_offer'")
    op.execute("ALTER TABLE message_log DROP CONSTRAINT IF EXISTS message_log_kind_check")
    op.execute(
        "ALTER TABLE message_log ADD CONSTRAINT message_log_kind_check "
        "CHECK (kind IN ('otp','confirmation','reminder','owner_cancel','owner_reschedule',"
        "'payment_received_no_slot'))"
    )

    # Restoring `booking_id NOT NULL` is safe because it is only reachable once
    # every offer row is gone, and an offer row is the only kind that can carry a
    # NULL booking_id — so the DELETE below is both the precondition and the
    # cleanup. Reminder rows are untouched.
    op.execute("DROP INDEX IF EXISTS idx_scheduled_messages_offer_pending_unique")
    op.execute("DELETE FROM scheduled_messages WHERE booking_id IS NULL")
    op.execute(
        "ALTER TABLE scheduled_messages "
        "DROP CONSTRAINT IF EXISTS ck_scheduled_messages_subject, "
        "DROP COLUMN IF EXISTS waitlist_entry_id, "
        "ALTER COLUMN booking_id SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE scheduled_messages DROP CONSTRAINT IF EXISTS scheduled_messages_kind_check"
    )
    op.execute(
        "ALTER TABLE scheduled_messages ADD CONSTRAINT scheduled_messages_kind_check "
        "CHECK (kind IN ('reminder'))"
    )

    op.execute("DROP INDEX IF EXISTS idx_waitlist_entries_offer_expiry")
    op.execute("DROP INDEX IF EXISTS idx_waitlist_entries_offer_token")
    op.execute(
        "ALTER TABLE waitlist_entries "
        "DROP COLUMN IF EXISTS offer_token_hash, "
        "DROP COLUMN IF EXISTS offer_starts_at, "
        "DROP COLUMN IF EXISTS offer_expires_at, "
        "DROP COLUMN IF EXISTS offered_at"
    )
