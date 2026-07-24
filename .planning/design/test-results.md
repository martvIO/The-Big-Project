# Usability Test — F9 design package

**Created**: 2026-07-23 · **Status**: script ready, 0 sessions run · **Blocks**: the F9 final gate (see `research/interview-status.md`)
**Instrument**: `screens/design-system/prototype-test.html` · **Upstream**: `definition/brief.md`, `ideation/flows.md`, `system/tokens.md`, the four screen specs
**Method**: moderated, task-based, thinking aloud. Runs as the second half of the discovery interviews in `research/interview-script.md` — not as separate sessions.

The design passed the critic at rev 2. What the critic cannot settle is whether five specific bets hold with real people:

| # | The bet | Task |
|---|---|---|
| 1 | A bride reads budget-fit off a grid that mixes real prices with "מחיר בתיאום" | B2 |
| 2 | "הוזמן" reads as *this one's taken* — not *don't bother with this boutique* | B3 |
| 3 | A booking CTA that opens a phone/WhatsApp panel reads as a familiar side door, not a broken form | B4 |
| 4 | An empty catalog still reads as a real, complete boutique | B6 |
| 5 | The policy blocker reads as *urgent*, not *hostile* or *you broke something* | O2 |

---

## How this runs

**One session per participant. Order is fixed.**

| Segment | Brides | Owners | Source |
|---|---|---|---|
| Discovery (Mom Test) | 25–30 min | 30–40 min | `research/interview-script.md`, unchanged |
| Transition | 1 min | 1 min | below |
| Prototype tasks | 17 min | 10 min | this document |
| Wrap-up | 3 min | 3 min | below |
| **Total** | **~47 min** | **~55 min** | |

**Never open the prototype before discovery is finished.** Showing the design first contaminates every answer after it — she starts describing your product instead of her life.

**Transition script**
- HE: ״עכשיו אני רוצה להראות לך משהו גולמי ולראות אותך משתמשת בו. זה לא מוצר גמור — אם משהו מבלבל, זה מידע בשבילי, לא טעות שלך. תחשבי בקול רם.״
- EN: "Now I want to show you something rough and watch you use it. It isn't finished — if something confuses you, that's information for me, not a mistake by you. Think out loud."

**Wrap-up** (both audiences)
- ״מה היה הכי קל? מה היה הכי קשה?״ · ״משהו שציפית למצוא ולא מצאת?״ · ״מ-1 עד 5, כמה בטוחה הרגשת?״

---

## Logistics

**Device — her own phone.** The whole design premise is a bride on her phone at 23:00; a laptop session tests a layout she'll rarely see.

```bash
cd .planning/design/screens/design-system
python3 -m http.server 8080
# share http://<your-LAN-ip>:8080/prototype-test.html — a QR code is fastest
```
If she isn't on your wifi, use any static host or a tunnel. The file is one self-contained HTML, so it can also be emailed or AirDropped — **but only after the font check below passes offline**.

**Font check — do this before every session.** The prototype pulls Frank Ruhl Libre and Assistant from the Google Fonts CDN. On a weak connection the display serif silently falls back to a system sans and the quiet-luxury register — the thing under test — is simply not on screen. The build detects this and shows a red `FONT LOAD FAILED` banner. **If that banner appears, do not run the session.** To remove the dependency, download both families as woff2 and inline them as base64 `@font-face` in the override `<style>`.

**Reset between participants:** reload the page. No state persists.

**Recording:** screen-record the phone if she consents; otherwise note first-tap location and time-to-CTA by hand. Ask consent before the prototype segment, separately from the interview consent.

**One URL per task** — the screen switcher is hidden, so you steer by handing over a link:

| Route | Screen |
|---|---|
| `…/prototype-test.html#catalog` | Storefront catalog (default) |
| `#empty` | Catalog with zero dresses |
| `#detail` | Dress detail |
| `#about` | Profile, hours, contact |
| `#states` | Loading / error / monogram / closed-today |
| `#manage` | Console, **first-run** — blocker + setup progress |
| `#manage-steady` | Console, **steady** — version history, no blocker |

### Moderator brief — do NOT log these as findings

**Dead by design (the prototype has no backend):** footer links (הצהרת נגישות, אינסטגרם, phone), the contact rows inside the sheet and `/about`, share, the accessibility button (נגישות), the console tabs (פרופיל / שעות / סוגי תורים), the banner's "ליצירת מדיניות ←", and "נסו שוב" on the states screen. If she taps one, say ״נניח שזה עבד״ and carry on.

**Seeded states, not participant errors:** the חילוט field on the console is pre-filled with `150` so its inline error (״חילוט חייב להיות בין 0 ל-100״) is visible from the start. If an owner asks whether *she* did something wrong, that reaction is a real finding about the error's identity — round 2 already flagged error-block identity for build QA — but the value was pre-set, so say so before she starts hunting.

**Live paths:** dress card → detail, back-link → catalog, booking CTA → contact panel, Esc/backdrop → close.

**One deliberate deviation from rev 2:** the accessibility button sits higher on mobile than in `prototype.html`, working around defect **PRE-1** below. Everything else on screen is exactly what passed the gate.

---

## Bride tasks (7 · ~17 min)

Open on `#catalog` unless noted.

### B1 — First read (no tapping)
> HE: ״אל תלחצי על כלום עדיין. תסתכלי — איזה מין מקום זה? בערך כמה שמלה פה עולה, לדעתך?״
> EN: "Don't tap anything yet. Just look — what kind of place is this? Roughly what does a dress here cost, do you think?"

**Tests** `BoutiqueHeader`, the quiet-luxury register, the brief's claimed instant "is this my style/level" read.
**Pass** — names it as bridal *and* premium unprompted, and ventures a price range, inside ~30s.
**Watch** — does she say "boutique" or "website"? Does anything read as a tech product?

### B2 — Budget fit
> HE: ״התקציב שלך לשמלה הוא בערך 9,000 ₪. הסלון הזה בשבילך?״
> EN: "Your dress budget is about 9,000 ₪. Is this boutique for you?"

**Tests** the mixed price grid — 8,900 ₪ / מחיר בתיאום / 12,400 ₪ / 7,200 ₪ side by side (HMW #1: let her self-qualify without forcing boutiques to publish everything).
**Pass** — confident yes/no in under 30s, reasoning out loud from the prices.
**Watch** — **does "מחיר בתיאום" read as *expensive* or as *hiding something*?** If it reads as hiding, per-dress price visibility is a trust liability, not a feature. Does the mixed grid make her distrust the visible prices too?

### B3 — Find and judge a dress
> HE: ״תמצאי את השמלה שנקראת ׳שירה׳ ותספרי לי כל מה שאת יכולה לדעת עליה.״
> EN: "Find the dress called שירה and tell me everything you can about it."

**Tests** card tap affordance, catalog→detail navigation, the `הוזמן` badge, gallery, size chips.
**Pass** — reaches the detail page in ≤2 taps and describes name, price and status.
**Watch (critical)** — **what does she think "הוזמן" means for her?** The design deliberately keeps the booking CTA live on a reserved dress ([storefront-dress-detail.md](screens/design-system/storefront-dress-detail.md): "booking a fitting for a reserved dress is a boutique conversation, not a hard block"). If she reads it as "I can't have this / this boutique is picked over", that bet is dead and the badge needs different wording.

### B4 — Book a fitting
> HE: ״את רוצה למדוד אותה. תעשי את זה.״
> EN: "You want to try it on. Do that."

**Tests** `BookingCTA` discoverability and the honest v1 seam — the CTA opens a contact panel (phone / WhatsApp / navigation) because the real booking flow is E3.
**Pass** — finds and taps the CTA within 15s without hunting.
**Watch (critical)** — **when the contact panel appears instead of a booking form: relief or "it's broken"?** Research theme 2 says WhatsApp-first is a constraint to work with, not fight. If the panel reads as a dead end, the storefront needs different CTA copy until E3 ships. Note whether she reaches for WhatsApp or the phone number first — that ordering should drive the panel's row order.

### B5 — Vet the boutique
> HE: ״לפני שאת נוסעת לשם — המקום הזה אמיתי? הם פתוחים ביום שישי אחר הצהריים?״
> EN: "Before you drive over — is this place real? Are they open Friday afternoon?"

**Tests** the Flow S3 trust loop: `/about`, `HoursTable` on the Israeli week, Waze/Maps, tap-to-call.
**Pass** — finds hours and address unaided, and correctly answers **no** (Friday is 09:00–13:00).
**Watch** — does she navigate to `/about` on her own, or expect this on the catalog page? That answers the open question in [storefront-profile-hours.md](screens/design-system/storefront-profile-hours.md) about folding `/about` into `/` as a section. Does she look for reviews or a rating? (Directories get cross-checked regardless — research theme 3.)

### B6 — The empty boutique
Hand over `#empty`.
> HE: ״זה סלון אחר. מה את חושבת עליו?״
> EN: "This is a different boutique. What do you make of it?"

**Tests** the state flagged **critical** in [storefront-catalog.md](screens/design-system/storefront-catalog.md) — the storefront ships before the catalog does (F7 before F8), so a boutique with zero dresses must still feel like a complete business.
**Pass** — she does **not** call it broken, unfinished, or "coming soon", and can still find a way to contact them.
**Watch** — does ״הקולקציה בדרך״ read as *new and careful* or as *nothing here yet*? Would she still book?

### B7 — When things go wrong (~2 min)
Hand over `#states`. Point at each block in turn, don't explain anything.
> HE: ״מה קורה פה, לדעתך?״ (על כל בלוק בתורו)
> EN: "What's going on here, do you think?" (for each block in turn)

**Tests** the four states nobody would otherwise see: skeleton loading, the error block, the monogram placeholder for a dress with no photo, and the closed-today header.
**Pass** — reads the skeleton as *loading* (not broken), the error as *try again* (not "the boutique is gone"), the monogram as *no photo yet* (not a broken image), and closed-today as *information* (not an error).
**Watch** — the monogram is gold on paper at **2.16:1**. It's decorative and exempt (see the gold law), but it is also the entire visual content of that card. Ask if she can see the letter clearly. If she squints, that's a legibility finding even though it passes the audit.

---

## Owner tasks (3 + 1 · ~10 min)

### O1 — First-run orientation
Hand over `#manage`.
> HE: ״קיבלת עכשיו גישה למערכת. מה המסך הזה רוצה שתעשי?״
> EN: "You've just been given access. What does this screen want you to do?"

**Tests** `SetupProgress` (״הגדרה ראשונית 3/4״) and `PolicyBlockerBanner` together.
**Pass** — names the missing cancellation policy as the next action, unprompted.
**Watch** — which of the two does she read first? If the progress card wins, the blocker isn't carrying its weight.

### O2 — Blocker tone
> HE: ״ההודעה למעלה — איך היא נוחתת אצלך?״
> EN: "That message at the top — how does it land?"

**Tests** the tone calibration: warning-text on paper with a gold-strong stripe, no icon, deliberately *not* red.
**Pass** — reads as "I need to take care of this", not "something is broken" or "I did something wrong".
**Watch** — if she reads it as an error or an accusation, the restraint failed and it needs softening; if she skims past it entirely, it needs strengthening. Both are Major.

### O3 — Policy immutability
Hand over `#manage-steady`.
> HE: ״את רוצה לשנות את מדיניות הביטולים. תעשי את זה. … ועכשיו — מה קרה לגרסה הישנה?״
> EN: "You want to change your cancellation policy. Do that. … Now — what happened to the old one?"

**Tests** the immutable-ledger treatment: version chips, ״בתוקף״, and no edit affordance anywhere.
**Pass** — she doesn't hunt for an edit or delete button, and says the old version still applies to bookings already made.
**Watch (critical)** — **misreading this is automatically a Critical finding.** E4 #19 evaluates the structured fields and the accepted text is the evidence for forfeiture; an owner who believes editing a version retroactively changes past bookings will make a legally dangerous assumption. Also: does ״בתוקף״ clearly mark which one is live?

### O4 — Brand acceptance (ask last)
Hand over `#catalog`.
> HE: ״זה נראה כמו הסלון שאת מנהלת?״
> EN: "Does this look like the boutique you actually run?"

**Tests** the design-config premise — quiet luxury, editorial, restraint, no promo language.
**Watch** — would she send this link to a bride? Would she put it in her Instagram bio? Anything here she'd be embarrassed by? Research says owners are "proud of the craft, embarrassed by the website" — this asks whether that flips.

---

## Pass / fail criteria

| Severity | Meaning | Action |
|---|---|---|
| **Critical** | Can't complete the task, or forms a wrong mental model with legal or commercial consequence (O3; "הוזמן" read as blocked) | Must fix before the F9 build |
| **Major** | Completes, but with real confusion, a wrong first guess, or a needed hint | Fix before the build if possible |
| **Minor** | Notices and shrugs | Log for F10 |

- **Target:** 80% of participants pass each task.
- **Red flag:** 3+ participants fail the same task → that flow gets **redesigned**, not patched.
- **Metric hooks** from [brief.md](definition/brief.md): time from opening the link to tapping the CTA (proxy for the <3 min landing→booking target), and whether B1+B2 together land inside the 2 minutes the persona claims.

### Per-participant tally

| Participant | B1 | B2 | B3 | B4 | B5 | B6 | B7 | time→CTA | notes |
|---|---|---|---|---|---|---|---|---|
| Bride 1 | | | | | | | | | |
| Bride 2 | | | | | | | | | |
| Bride 3 | | | | | | | | | |
| Bride 4 | | | | | | | | | |
| Bride 5 | | | | | | | | | |

| Participant | O1 | O2 | O3 | O4 | notes |
|---|---|---|---|---|---|
| Owner 1 (pilot) | | | | | |
| Owner 2 | | | | | |
| Owner 3 | | | | | |

Mark `pass` / `partial` / `fail`.

---

## Accessibility baseline — automated, 2026-07-23

Run before any session so a human never spends attention on something a machine can catch. axe-core 4.11 against `prototype-test.html`, all 7 routes at 375px plus 4 at 1440px, plus the contact sheet open.

**WCAG 2.0 A/AA (the IS 5568 legal floor): 0 violations.** `color-contrast` ran and passed **264** node checks — the three-gold law holds up under measurement, not just arithmetic. Also clean: `label` (9), `button-name` (43), `link-name` (63), `aria-hidden-focus` (204), `nested-interactive` (43), `aria-valid-attr-value` (31).

**3 undecidable, all judged:**

| Node | Verdict |
|---|---|
| `<span class="mark" aria-hidden="true">◆</span>` | Exempt — decorative, and the exception text carries the meaning |
| `<span class="monogram" aria-hidden="true">ב</span>` — gold on paper, **2.16:1** | Exempt per the gold law (decorative placeholder art), but it is the *entire* visual content of a photo-less card. Pushed to **task B7** for a human read |
| `<textarea id="t">` background obscured | Symptom of **PRE-1** below |

**4 best-practice findings** (not the legal floor, but they become build requirements):

| Rule | Reality |
|---|---|
| `landmark-one-main` | No `<main>` anywhere. The skip-links target `<div class="page" id="…-main">`. In F9/F10 each route must have a real `<main>` as the skip-link target |
| `page-has-heading-one` | Dress detail and the console have no `h1`. Dress name → `h1`; console section → `h1` |
| `heading-order` | Dress names are `h3` directly under the `h1` boutique name. Either promote to `h2` or give the grid an `h2` section heading |
| `region` | Same root cause as the landmark finding |

The single-file prototype packs six "pages" into one document, so the landmark and `h1` counts are partly an artifact of that packaging — but the requirement they imply is real and belongs in the build.

**What automation still cannot tell us:** whether a screen reader can complete a booking, whether the focus order makes sense to someone who can't see it, whether 2.16:1 art is legible to a 55-year-old mother-of-the-bride, and whether the `A11yMenu` (dead in this prototype) helps anyone. Those need a participant who actually uses assistive tech — still unrecruited.

---

## Findings

### Pre-session — found by tooling, before any participant

| # | Screen / flow | What | Severity | Change |
|---|---|---|---|---|
| **PRE-1** | Catalog, empty, detail — 375px | The fixed `.a11y-btn` (z-index 60) renders **on top of** the fixed `.cta-bar` and swallows **60×44px, 13.8%** of the primary booking CTA. The left end of "קביעת תור למדידה" opens the accessibility menu instead of booking. Same collision hides 888px² of "יצירת גרסה" on the console. Measured on the **gate-approved `prototype.html`** — this is a rev-2 defect the Design Gate missed, not a test-build artifact | **Critical** | Reserve a bottom gutter: lift `.a11y-btn` clear of the CTA bar below 768px (`inset-block-end: 92px` — 80px bar + 12px), or move the bar's z-index above it and shift the button. Needs a tokens/components decision, then a critic re-run |
| **PRE-2** | About, console — 375px | With no bottom gutter reserved, the a11y button also floats over ordinary content (a Waze link, a form input). Reachable by scrolling, unlike PRE-1 | Minor | Add bottom padding equal to the button's footprint on scrollable pages |

**PRE-1 is already worked around in `prototype-test.html`** (override block, item 8) — otherwise roughly one B4 tap in seven would land on a dead accessibility button and read as "the booking button is broken", destroying the finding B4 exists to produce. **The fix still has to be made in the design itself.**

### From sessions

*Empty until sessions run. One row per finding, grouped by screen so revisions map to files.*

| # | Screen / flow | What happened | Verbatim | Hit by | Severity | Proposed change |
|---|---|---|---|---|---|---|
| | | | | /5 | | |

### Discovery synthesis
*Themes from the Mom Test half land here too — they validate the personas and journeys in `definition/brief.md`, which are still marked provisional. Both halves are needed for the final gate.*

---

## What happens after

Per [research/interview-status.md](research/interview-status.md):

1. Findings recorded above, severity-rated
2. Personas and journeys in `definition/brief.md` revised against the discovery half
3. Screens revised for every Critical and Major
4. `design-critic` re-run on the revised package
5. **Final gate** → F9 build unblocks → E2 Feature 9 moves from `spec` to `building`

Critical findings that survive into the build become QA items, not deferred debt.
