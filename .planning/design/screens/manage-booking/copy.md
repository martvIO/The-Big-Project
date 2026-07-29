# Copy deck — F16 Manage Booking (`/b/{token}`) + lifecycle SMS

**Date**: 2026-07-29 · **Status**: **DRAFT — awaiting user sign-off** · **Owner of the Hebrew: the user** · **Consumes**: `.planning/specs/booking-comms.md` (Gate 1 approved) · **Lands in**: `Frontend/apps/storefront/src/i18n/he.ts` (`manage.*`, `document.manageTitle`, one `booking.*` rewrite) and the backend SMS template module

The F14 deck's rules (`../booking/copy.md` §2) apply verbatim: no future-tense delivery claims the system can't keep, R19 split shapes for every mid-sentence value, ≤-length notes where layout constrains, no promotional wording anywhere (Amendment 40 — these SMS need counsel sign-off before a real provider ships).

## 1. Page copy (`manage.*`)

| Key | What it must say | DRAFT Hebrew | Status |
|---|---|---|---|
| `document.manageTitle` | Browser-tab title for the manage page | התור שלך | DRAFT |
| `manage.title` | Page heading — hers, calm, no exclamation | התור שלך | DRAFT |
| `manage.loading` | VisuallyHidden loading announcement (R30) | טוענות את פרטי התור | DRAFT |
| `manage.attendanceCta` | The confirm-attendance primary button | אישור הגעה | DRAFT |
| `manage.attendanceDone` | Replaces the primary button after confirmation; also the status announcement | ההגעה אושרה. נתראה! | ⚠ DRAFT — register check: is «נתראה!» too casual for the quiet-luxury voice? |
| `manage.cancelCta` | Reveal trigger for the cancel step — states the act, no euphemism | ביטול התור | DRAFT |
| `manage.cancelQuestion` | Heading of the revealed block — a real question, not a warning | לבטל את התור? | DRAFT |
| `manage.cancelPolicyLead` | Lead of the window sentence; `{{hours}}` follows isolated (R19 split) | לפי המדיניות שאישרת, אפשר לבטל עד | DRAFT |
| `manage.cancelPolicySuffix` | Suffix after the isolated number | שעות לפני המועד. | DRAFT |
| `manage.cancelConsequenceFree` | The pre-E4 truth: no deposit was taken, cancelling costs nothing. E4 replaces the out-of-window variant | לא נגבה תשלום על התור, כך שהביטול אינו כרוך בעלות. | ⚠ DRAFT — P1: same sentence on both window sides until E4 |
| `manage.cancelConfirm` | The danger button — the click that cancels | אישור הביטול | DRAFT |
| `manage.cancelKeep` | Collapses the reveal, keeps the appointment | השארת התור | DRAFT |
| `manage.cancelled` | The cancelled state line + status announcement — plain fact, no guilt | התור בוטל. | DRAFT |
| `manage.rebookCta` | ButtonLink to `/book/slot` on the cancelled state | קביעת תור חדש | DRAFT |
| `manage.past` | The past-appointment state — the link still answers, honestly | המועד הזה כבר עבר. | DRAFT |
| `manage.invalid` | Invalid/unknown token — no blame, no technical words | הקישור הזה כבר לא תקף. | DRAFT |
| `manage.invalidHint` | The human exit under it | לכל שאלה על התור, אפשר להתקשר לבוטיק. | DRAFT |
| `manage.loadFailed` | Retryable failure (429/network/5xx) — recoverable, unblaming (F-M1) | לא הצלחנו להציג את פרטי התור כרגע. | DRAFT |
| `manage.retry` | The retry button | ניסיון נוסף | DRAFT |

Facts-card labels reuse the approved F14 rows `booking.confirmWhen` / `booking.confirmWhat` / `booking.confirmDress` (P2 — no new Hebrew, no drift).

## 2. The one `booking.*` rewrite (design-gate ruling, `booking.md:1823`)

| Key | What it must say now | Approved F14 Hebrew (changes) | DRAFT Hebrew | Status |
|---|---|---|---|---|
| `booking.confirmKeepScreen` | The screen stops claiming to be her **only** record (the F16 premise-change, `booking.md:1823`) — but the save-the-screen instruction **stays**: at F16 ship time no provider is configured so zero confirmations send, and kosher-phone customers never receive one at any time. Dropping the screenshot nudge would re-open F-C7's dead end for exactly the people the SMS cannot reach. The copy may not promise delivery in any tense | זה האישור היחיד שלך — כדאי לצלם את המסך או לשמור אותו. אנחנו נחכה לך. | פרטי התור נשמרו אצלנו, וכדאי בכל זאת לצלם את המסך. אנחנו נחכה לך. | ⚠ DRAFT — design-critic blocker 2: the save nudge is retained deliberately; drop only the «היחיד» premise. Revisit removing the nudge when a provider is live and delivery is observed |

## 3. SMS bodies (backend templates — same sign-off, counsel note applies)

Values `{{…}}` are rendered by the template functions; every body must clear its `*_MAX_SEGMENTS = 3` budget with the worst-case fixture (30-char slug, 43-char token).

| Template | What it must say | DRAFT Hebrew | Status |
|---|---|---|---|
| `confirmation` | Booking confirmed: boutique name, weekday+date+time, the manage link. **No location line** — the manage page's ContactPanel carries maps/waze, and a second free-text/URL block blew the 3-segment budget (critic finding 4; spec amended at this gate). No celebration, no marketing | {{boutique}}: התור נקבע ליום {{weekday}}, {{date}} בשעה {{time}}. לצפייה, אישור הגעה או ביטול: {{link}} | ⚠ DRAFT — arithmetic: 50 fixed + ≤25 boutique (fixture bound) + ≤5 weekday + ≤10 date + 5 time + ≤98 link (30-slug + 43-token + domain/path) ≈ 193 ≤ 201 (3×67 UCS-2) |
| `reminder` | 24h reminder: tomorrow/date + time, confirm-attendance ask, same link | {{boutique}}: תזכורת — התור שלך מחר, {{date}} בשעה {{time}}. לאישור הגעה או ביטול: {{link}} | ⚠ DRAFT — «מחר» is false for the 2–24h immediate band on same-day bookings; propose dropping «מחר» and letting the date speak: תזכורת — התור שלך ביום {{weekday}}, {{date}} בשעה {{time}} |
| `owner_cancel` | The boutique cancelled: state it, point at the phone; **no money words until E4** | {{boutique}}: התור שלך בתאריך {{date}} בוטל על ידי הבוטיק. לשאלות ולתיאום מחדש: {{phone}} | ⚠ DRAFT |
| `owner_reschedule` | The boutique moved it: old→new, the manage link for the new time | {{boutique}}: התור שלך הועבר ליום {{weekday}}, {{date}} בשעה {{time}}. לצפייה ולאישור: {{link}} | ⚠ DRAFT |

## 4. Questions for the user

1. **Register of `manage.attendanceDone`** — «נתראה!» keeps the F14 confirm screen's warmth; a stricter luxury read drops the exclamation. Which voice?
2. **`booking.confirmKeepScreen` rewrite** — the proposed shape avoids promising an SMS (it can't, honestly). Alternative: name the SMS conditionally («אם הזנת נייד — נשלח גם אישור») — rejected in draft as the conditional reads like small print. Agree?
3. **The reminder's «מחר»** — see the row's ⚠. Drop it for the date-led shape?
4. **`owner_cancel` carries the boutique's phone, not the manage link** — after an owner cancel the page would only say "cancelled"; the phone is the useful next step. Confirm?
