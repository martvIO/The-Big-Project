import { describe, expect, it } from "vitest";
import i18n from "../i18n";
import { paymentActionKey, paymentBadge, statusBadge } from "../lib/booking";

// F19 D14/D18. The bug these guard: `statusBadge` was a FOUR-entry Map with a
// raw-value fallback, so the day the backend grew `pending_payment` the owner's
// Hebrew RTL console rendered the literal LTR string "pending_payment". The same
// trap is re-armed by every value on `payment_status`, which is a seven-value
// DB-pinned CHECK (0012) — so every one of the seven is mapped, and the fallback
// below is unreachable by construction rather than by hope.
describe("statusBadge", () => {
  it("gives pending_payment a real Hebrew label, never the raw wire value", () => {
    const badge = statusBadge("pending_payment");
    expect(badge.labelKey).toBe("booking.statusPendingPayment");
    expect(i18n.t(badge.labelKey)).toBe("ממתין לתשלום");
    expect(i18n.t(badge.labelKey)).not.toBe(badge.labelKey);
  });

  it("still renders the four shipped statuses", () => {
    for (const [status, hebrew] of [
      ["confirmed", "מאושר"],
      ["completed", "התקיים"],
      ["no_show", "לא הגיעה"],
      ["cancelled", "בוטל"],
    ]) {
      expect(i18n.t(statusBadge(status).labelKey)).toBe(hebrew);
    }
  });
});

describe("paymentBadge", () => {
  it("maps every value of the DB-pinned PaymentStatus set to its own Hebrew", () => {
    const all = [
      "pending",
      "paid",
      "failed",
      "expired",
      "refund_due",
      "refunded",
      "forfeited",
    ];
    const labels = all.map((status) => i18n.t(paymentBadge(status).labelKey));
    for (const label of labels) {
      expect(label).not.toMatch(/[a-z_]{4,}/);
    }
    expect(new Set(labels).size).toBe(all.length);
  });

  it("falls back to Hebrew, not to the raw value — the statusBadge bug, not repeated", () => {
    const badge = paymentBadge("something_new");
    expect(badge.labelKey).toBe("booking.paymentOther");
    expect(i18n.t(badge.labelKey)).not.toContain("something_new");
  });

  it("reserves danger for the one payment state the owner must fix", () => {
    // MD4: a `failed` row means the appointment was booked and no deposit was
    // taken. Every other value is a settled fact or a wait.
    expect(paymentBadge("failed").variant).toBe("danger");
    expect(paymentBadge("paid").variant).toBe("success");
    expect(paymentBadge("expired").variant).toBe("muted");
  });
});

describe("paymentActionKey", () => {
  it("flags a cancelled booking whose deposit is still held", () => {
    // Her money is held and her appointment is gone. MD1's reschedule is the
    // button behind this marker.
    expect(paymentActionKey("cancelled", "paid")).toBe("booking.paymentActionCancelledPaid");
  });

  it("flags MD4 — a confirmed booking whose deposit was never taken", () => {
    expect(paymentActionKey("confirmed", "failed")).toBe("booking.paymentActionNoDeposit");
  });

  it("stays silent on every ordinary combination", () => {
    for (const [status, payment] of [
      ["confirmed", "paid"],
      ["confirmed", null],
      ["cancelled", null],
      ["cancelled", "expired"],
      ["cancelled", "failed"],
      ["pending_payment", "pending"],
      ["completed", "paid"],
    ] as [string, string | null][]) {
      expect(paymentActionKey(status, payment)).toBeNull();
    }
  });
});
