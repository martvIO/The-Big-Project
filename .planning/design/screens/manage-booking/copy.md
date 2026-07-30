# Copy deck — F16 Manage Booking (`/b/{token}`) + lifecycle SMS

**Date**: 2026-07-29 · **Status**: **APPROVED 2026-07-30** — `.planning/epics/interview-2026-07-30.md` **Q5** ("F16 Hebrew: approved as drafted"), with Q4's reminder rewrite and pre-decided #3/#4/#5 folded in · **Owner of the Hebrew: the user** · **Consumes**: `.planning/specs/booking-comms.md` (Gate 1 approved) · **Lands in**: `Frontend/apps/storefront/src/i18n/he.ts` (`manage.*`, `document.manageTitle`, one `booking.*` rewrite) and the backend SMS template module

**Counsel sign-off on the SMS bodies is still required before a real provider goes live** (Q5) — that gate is unchanged and is not a pre-merge gate.

The F14 deck's rules (`../booking/copy.md` §2) apply verbatim: no future-tense delivery claims the system can't keep, R19 split shapes for every mid-sentence value, ≤-length notes where layout constrains, no promotional wording anywhere (Amendment 40 — these SMS need counsel sign-off before a real provider ships).

## 1. Page copy (`manage.*`)

| Key | What it must say | Approved Hebrew | Status |
|---|---|---|---|
| `document.manageTitle` | Browser-tab title for the manage page | התור שלך | APPROVED |
| `manage.title` | Page heading — hers, calm, no exclamation | התור שלך | APPROVED |
| `manage.loading` | VisuallyHidden loading announcement (R30) | טוענות את פרטי התור | APPROVED |
| `manage.attendanceCta` | The confirm-attendance primary button | אישור הגעה | APPROVED |
| `manage.attendanceDone` | Replaces the primary button after confirmation; also the status announcement | ההגעה אושרה. נתראה. | APPROVED — **pre-decided #5** settles the register question: no exclamation mark. Q5 approved the draft «נתראה!» wholesale and #5 rules on this exact glyph; #5 is the specific, later ruling and its basis is mechanically checkable (`he.ts` and the approved F14 deck contain zero exclamation marks), so an exclamation here would be the one string that breaks the product's punctuation register |
| `manage.cancelCta` | Reveal trigger for the cancel step — states the act, no euphemism | ביטול התור | APPROVED |
| `manage.cancelQuestion` | Heading of the revealed block — a real question, not a warning | לבטל את התור? | APPROVED |
| `manage.cancelPolicyLead` | Lead of the window sentence; `{{hours}}` follows isolated (R19 split) | לפי המדיניות שאישרת, אפשר לבטל עד | APPROVED |
| `manage.cancelPolicySuffix` | Suffix after the isolated number | שעות לפני המועד. | APPROVED |
| `manage.cancelConsequenceFree` | The pre-E4 truth: no deposit was taken, cancelling costs nothing. E4 replaces the out-of-window variant | לא נגבה תשלום על התור, כך שהביטול אינו כרוך בעלות. | APPROVED — **pre-decided #4**: the same sentence renders on both window sides until E4, and the in/out-of-window split still ships as structure |
| `manage.cancelConfirm` | The danger button — the click that cancels | אישור הביטול | APPROVED |
| `manage.cancelKeep` | Collapses the reveal, keeps the appointment | השארת התור | APPROVED |
| `manage.cancelled` | The cancelled state line + status announcement — plain fact, no guilt | התור בוטל. | APPROVED |
| `manage.rebookCta` | ButtonLink to `/book/slot` on the cancelled state | קביעת תור חדש | APPROVED |
| `manage.past` | The past-appointment state — the link still answers, honestly | המועד הזה כבר עבר. | APPROVED |
| `manage.invalid` | Invalid/unknown token — no blame, no technical words | הקישור הזה כבר לא תקף. | APPROVED |
| `manage.invalidHint` | The human exit under it | לכל שאלה על התור, אפשר להתקשר לבוטיק. | APPROVED |
| `manage.loadFailed` | Retryable failure (429/network/5xx) — recoverable, unblaming (F-M1) | לא הצלחנו להציג את פרטי התור כרגע. | APPROVED |
| `manage.retry` | The retry button | ניסיון נוסף | APPROVED |

Facts-card labels reuse the approved F14 rows `booking.confirmWhen` / `booking.confirmWhat` / `booking.confirmDress` (P2 — no new Hebrew, no drift).

## 2. The one `booking.*` rewrite (design-gate ruling, `booking.md:1823`)

| Key | What it must say now | Approved F14 Hebrew (changes) | Approved Hebrew | Status |
|---|---|---|---|---|
| `booking.confirmKeepScreen` | The screen stops claiming to be her **only** record (the F16 premise-change, `booking.md:1823`) — but the save-the-screen instruction **stays**: at F16 ship time no provider is configured so zero confirmations send, and kosher-phone customers never receive one at any time. Dropping the screenshot nudge would re-open F-C7's dead end for exactly the people the SMS cannot reach. The copy may not promise delivery in any tense | זה האישור היחיד שלך — כדאי לצלם את המסך או לשמור אותו. אנחנו נחכה לך. | פרטי התור נשמרו אצלנו, וכדאי בכל זאת לצלם את המסך. אנחנו נחכה לך. | APPROVED — **pre-decided #3**: never promise a text. The save nudge is retained deliberately; only the «היחיד» premise drops. Revisit removing the nudge when a provider is live and delivery is observed |

## 3. SMS bodies (backend templates — same sign-off, counsel note applies)

Values `{{…}}` are rendered by the template functions; every body must clear its `*_MAX_SEGMENTS = 3` budget with the worst-case fixture (30-char slug, 43-char token).

**`{{boutique}}` is truncated to 25 characters inside the templates** — pre-decided #8, discharging design finding F-M3: `tenants.name` is unbounded TEXT but the budget arithmetic assumes ≤25 chars, and truncation is the only way production matches the tested fixture.

`{{date}}` renders as `d.m.yyyy` and `{{weekday}}` as the bare Hebrew day word (ראשון…שבת, so «ליום שלישי» reads correctly), both computed in `Asia/Jerusalem` — a server-side locale format would read the runner's calendar, not the boutique's.

| Template | What it must say | Approved Hebrew | Status |
|---|---|---|---|
| `confirmation` | Booking confirmed: boutique name, weekday+date+time, the manage link. **No location line** — the manage page's ContactPanel carries maps/waze, and a second free-text/URL block blew the 3-segment budget (critic finding 4; spec amended at this gate). No celebration, no marketing | {{boutique}}: התור נקבע ליום {{weekday}}, {{date}} בשעה {{time}}. לצפייה, אישור הגעה או ביטול: {{link}} | APPROVED — arithmetic: 50 fixed + ≤25 boutique (fixture bound) + ≤5 weekday + ≤10 date + 5 time + ≤98 link (30-slug + 43-token + domain/path) ≈ 193 ≤ 201 (3×67 UCS-2) |
| `reminder` | Reminder for every band: weekday + date + time, confirm-attendance ask, same link. **No «מחר»** — it is false for the 2–24h immediate band, and one date-led body serves all three bands | {{boutique}}: תזכורת — התור שלך ביום {{weekday}}, {{date}} בשעה {{time}}. לאישור הגעה או ביטול: {{link}} | APPROVED — **Q4**: send immediately under 24h notice and drop «מחר». Arithmetic: 57 fixed + ≤25 boutique + ≤5 weekday + ≤10 date + 5 time + ≤97 link ≈ 199 ≤ 201 (3×67 UCS-2) |
| `owner_cancel` | The boutique cancelled: state it, point at the phone; **no money words until E4** | {{boutique}}: התור שלך בתאריך {{date}} בוטל על ידי הבוטיק. לשאלות ולתיאום מחדש: {{phone}} | APPROVED — no money words until E4; the contact clause is dropped when the boutique published no phone |
| `owner_reschedule` | The boutique moved it: old→new, the manage link for the new time | {{boutique}}: התור שלך הועבר ליום {{weekday}}, {{date}} בשעה {{time}}. לצפייה ולאישור: {{link}} | APPROVED — the link is the new time's, minted by the reschedule upsert; arithmetic ≈ 190 ≤ 201 |

## 4. The four questions, answered

Answered in `.planning/epics/interview-2026-07-30.md`; recorded here so the deck stops asking a settled question.

1. **Register of `manage.attendanceDone`** — the stricter luxury read wins: «ההגעה אושרה. נתראה.» (**pre-decided #5**).
2. **`booking.confirmKeepScreen` rewrite** — the proposed shape is approved; the conditional «אם הזנת נייד» alternative stays rejected, and the copy may not promise delivery in any tense (**pre-decided #3**).
3. **The reminder's «מחר»** — dropped. One date-led body serves the 24h+, 2–24h and under-2h bands (**Q4**).
4. **`owner_cancel` carries the boutique's phone, not the manage link** — confirmed: after an owner cancel the page would only say "cancelled", so the phone is the useful next step (**Q5**, approving the row as drafted).
