import { describe, expect, it } from "vitest";
import i18n from "../i18n";
import type { EffortBandRef } from "../api";
import { bandLabel, laterStages, STAGE_LABEL_KEY, STAGE_ORDER } from "../lib/stages";

// `lib/stages.ts` is the client half of a state machine that has no status
// column: the stage is the RIGHTMOST STAMPED of five nullable timestamps, and
// the order below is the only place the client knows what "later" means.
//
// The plan names these assertions and names no file to hold them. They go here
// rather than in i18n.test.ts because two of the three are not about copy —
// `jerusalem.test.ts` and `validation.test.ts` are the shipped precedent for a
// pure-lib suite of its own.

const BANDS: EffortBandRef[] = [
  { band: "thirty_min", minutes: 30 },
  { band: "one_hour", minutes: 60 },
  { band: "two_hours", minutes: 120 },
  { band: "half_day", minutes: 240 },
  { band: "full_day", minutes: 480 },
];

const t = (key: string, options?: Record<string, unknown>): string => i18n.t(key, options);

describe("the stage order", () => {
  it("is the five stages in the order the server derives them", () => {
    expect(STAGE_ORDER).toEqual(["intake", "in_progress", "qc", "ready", "delivered"]);
  });

  it("resolves every label key to its own Hebrew", () => {
    // The `Record<TicketStage, string>` type catches a MISSING MEMBER at compile
    // time; this catches a member pointing at a key that does not exist, which
    // types cannot see. `lib/roles.ts`'s header says why both halves are needed
    // — a column rendering the raw slug `in_progress` and a column rendering the
    // wrong Hebrew word are different bugs.
    for (const key of Object.values(STAGE_LABEL_KEY)) {
      expect(i18n.t(key)).not.toBe(key);
    }
    expect(i18n.t(STAGE_LABEL_KEY.in_progress)).toBe("בעבודה");
    expect(i18n.t(STAGE_LABEL_KEY.delivered)).toBe("נמסר");
  });
});

describe("laterStages", () => {
  it("offers only stages STRICTLY later than the card's current one", () => {
    // The skip Select's options. A forward skip is legal and audited; a
    // backwards one is a 409 the server refuses, so offering it would be the
    // console inviting a refusal.
    expect(laterStages("intake")).toEqual(["in_progress", "qc", "ready", "delivered"]);
    expect(laterStages("qc")).toEqual(["ready", "delivered"]);
  });

  it("excludes the current stage itself", () => {
    // Re-entering the stage the card is already in is a no-op the server would
    // answer 200 to, which is worse than a refusal: the cue would announce a
    // move that did not happen.
    expect(laterStages("ready")).not.toContain("ready");
  });

  it("returns the empty array at the last stage", () => {
    // Which is what makes «the skip Select renders only when two or more later
    // stages exist» expressible as a length check rather than a special case.
    expect(laterStages("delivered")).toEqual([]);
  });
});

describe("bandLabel", () => {
  it("returns the band's own word when the stored minutes match a live band", () => {
    expect(bandLabel(240, BANDS, t)).toBe("חצי יום");
    expect(bandLabel(30, BANDS, t)).toBe("חצי שעה");
  });

  it("falls back to the raw minutes when no live band matches", () => {
    // The visible consequence of "minutes persist, never the label": a boutique
    // re-tuned «חצי יום» from 240 to 300 AFTER this ticket was estimated, and a
    // ticket estimated under the old mapping must not be silently re-valued.
    expect(bandLabel(300, BANDS, t)).toBe("300 דק׳");
  });

  it("takes the FIRST band when a tenant has mapped two of them to one number", () => {
    // Reachable: the server bounds each band to 1..1440 and forbids no
    // duplicate. Pinned so the answer cannot quietly become last-wins, which
    // would relabel every «חצי יום» ticket «יום מלא» the day an owner flattens
    // her two longest bands.
    const flattened: EffortBandRef[] = [
      { band: "half_day", minutes: 480 },
      { band: "full_day", minutes: 480 },
    ];
    expect(bandLabel(480, flattened, t)).toBe("חצי יום");
  });

  it("falls back rather than throwing on an empty band list", () => {
    // Unreachable from the shipped payload — the server iterates the ENUM, so
    // five bands always ship — but the fallback is what makes that a property of
    // the server rather than an assumption of the client.
    expect(bandLabel(60, [], t)).toBe("60 דק׳");
  });
});
