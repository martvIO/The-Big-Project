# F20 — Hebrew legal copy (PPL Amendment 13)

**Status**: DRAFT — awaiting user approval · **Author**: Claude (Gate 1 Q1 ruling, 2026-08-04) · **Drafted**: 2026-08-04 · **Revised**: 2026-08-04 after adversarial review (26 findings — 24 applied, 2 rejected on the record; see "Findings raised and REJECTED")
**Feature**: F20 PPL compliance · **Spec**: `.planning/specs/ppl-compliance.md` · **Plan**: `.planning/plans/ppl-compliance.md`
**Gate**: this document must be approved **before the F20 PR merges** (Gate 1 Q1).

---

## How to read this document

You are approving **wording**, not law. For every string below you get three things:

1. **The exact Hebrew that will ship**, in a copy-paste block. This is the literal, character for character.
2. **A clause-by-clause table** — each sentence in plain English, and *which legal duty it discharges*. If a row's "why" does not convince you, that sentence is wrong and should be struck or rewritten. You should not have to take my word for any of it.
3. **The exact byte count**, computed (not estimated), against the 8192-byte cap.

Approve by saying so. Reject any individual clause by naming its row.

**The review's one structural lesson, applied throughout.** The first draft verified that every sentence was *true of the platform*. It did not verify that **every right a sentence grants has a code path reaching the subject it is shown to**. That check is now run on every clause, and it changed three things: the walk-in marketing exception (finding F5), the walk-in's console reachability (item 7 of "What this approval does NOT cover"), and the correction right (item 8). Where a right exists in law but the console cannot serve it, the clause **stays** — the law does not care what we built — and the gap is named in that section instead of hidden.

---

## ⚠ READ THIS FIRST — five things I found in the code that the spec did not anticipate

The spec was written 2026-07-30 against a tree that has moved. I verified every factual claim in the copy against the code as it is **today**, and five of them contradict the spec.

### F1 — The Twilio adapter is real and shipped. The spec says there is no SMS provider. **The list must name Twilio — conditionally.**

The spec (§"In-repo compliance artifacts", D5, Risk 7) states, twice and in bold, that there is **no SMS provider yet** and that the list "must not name Twilio as live, because it isn't". Here is the code as it is, stated precisely — **the first draft of this section over-claimed and the correction matters**:

| Evidence | What it actually says |
|---|---|
| `Backend/app/core/config.py:58` | `sms_provider: Literal["fake", "twilio"] \| None = None` — **ships unset**. The comment above it: *"None → UnconfiguredSmsSender: **no provider is a supported deployment** where OTP send answers 503, exactly like the missing media bucket. `fake` is the dev/staging adapter; `twilio` is the real one and the only value that makes production legal."* |
| `Backend/app/core/config.py:259-268` (`_forbid_sms_test_paths_in_production`) | rejects **only** `"fake"` (and `OTP_DEV_CODE`) in production. **`None` passes it.** So "in production the only legal value is `twilio`" — which the first draft wrote — is **an invalid inference**. The honest statement is: `"fake"` is a boot failure in production; `None` is a supported 503-everywhere deployment; `"twilio"` is the only value that actually sends anything. |
| `Backend/app/notifications/twilio.py` | exists — a real adapter, one form-encoded POST, four `SecretStr` credential fields (`config.py:66-70`). |
| `Backend/.env.example:33-38` | *"`twilio` sends for real — money and real handsets, so it is opt-in per environment and **dev/staging stay on `fake`**."* `SMS_PROVIDER` is commented out. |
| `docs/infra-runbook.md:123` | the only documented deployment runs **`APP_ENV=staging`**. On it, Twilio receives nothing — the in-memory fake outbox holds her number and body. |

**Consequence for the copy**: the Twilio bullet is **conditional**, not a statement of present fact. Writing «חברת Twilio מקבלת את מספר הטלפון שלך» unconditionally would be a falsehood in a statutory disclosure on the deployment we actually run — the over-disclosure direction of exactly the error D14 exists to prevent. Omitting Twilio entirely would be the under-disclosure direction, which is worse. The bullet therefore names Twilio, says what it receives, and says **when**.

### F2 — Lemon Squeezy is **forbidden in production**. No payment processor is live. The list must say so.

`config.py` `_forbid_fake_payment_paths_in_production` raises on **both** allowed values:

```
PAYMENT_PROVIDER must not be 'fake' when APP_ENV is 'production'
PAYMENT_PROVIDER must not be 'lemonsqueezy' when APP_ENV is 'production'
```

`payment_provider: Literal["fake", "lemonsqueezy"] | None = None`, and the field comment calls `lemonsqueezy` *"F18's TEST-MODE development engine"*. There is no third literal. So **a production tenant cannot have a payment gateway configured at all**, and deposits answer `503`.

**Consequence for the copy**: the list names no payment processor and says plainly that no payment service is used yet, plus that one will be listed *before* it is used.

### F2b — the disclosure principle, stated once and applied to all four bullets

The first draft applied three different standards to three processors without stating any of them: it excluded Lemon Squeezy because the code ships it unset, named Twilio on a broken inference, and named AWS without considering the question. A reviewing lawyer finds that in one pass.

**The principle, now stated in the Hebrew itself** (String 4, clause 0, last sentence): *the list names every processor the platform is built to use, and says of each whether it is in use today.* Applied uniformly:

| Processor | In the list? | In use today? | Evidence |
|---|---|---|---|
| Railway (compute + Postgres) | yes | **yes, unconditionally** | `docs/infra-runbook.md:115-119` — `api`, `worker` and a Railway-managed `Postgres` are the deployment. |
| Twilio (SMS) | yes | **conditionally — the bullet says so** | F1. `sms_provider` ships unset; staging runs `fake`. |
| Amazon Web Services (S3, `il-central-1`) | yes | **yes on the deployed environment** | `config.py:45` `media_bucket` ships **unset**, but `docs/infra-runbook.md:211` records `MEDIA_BUCKET=boutique-staging-media`, `MEDIA_REGION=il-central-1` set on both Railway services. Unset default, configured deployment — so "in use", and the bullet also says it holds none of her data. |
| any payments/clearing service | **no, and the absence is stated** | no — boot failure on both literals | F2. |

That reading also makes String 4's own closing promise («אם יתווסף שירות כזה, הוא יופיע ברשימה הזאת לפני שייעשה בו שימוש») a rule the list follows rather than a special case for payments.

### F3 — **The queue check-in flow already collects name + phone and already carries an INTERIM notice that the shipped code says F20 must replace.** This adds a fourth collection point and two more strings.

The spec's D1 says "three collection points, not four" and treats the walk-in queue as F33's future work. F33 has **shipped**. `Backend/app/models/queue_ticket.py` exists (migration `0018_queue_tickets`), carries `name`, `phone`, `visit_type` and `marketing_opt_in_at`, and `Frontend/apps/storefront/src/i18n/he.ts:452-482` says, verbatim:

> `notice` and `optIn` are COUNSEL-GATED … The values below are the spec's **INTERIM** Hebrew … **F20 replaces both VALUES, here and in ar.ts, and that is the whole swap**: no component may hardcode any part of either sentence, and no second copy may exist anywhere.

So the shipped code names F20 as the owner of `checkin.notice` and `checkin.optIn`. Replacements for both are drafted here (strings 6 and 7). **If you approve only the five strings the task named, `/checkin` keeps shipping interim, un-approved Hebrew that the code itself flags as provisional — including the false deletion promise in F4 and the unservable marketing exception in F5.**

### F4 — Nothing in this system is ever hard-deleted today, and one shipped sentence already promises otherwise.

`grep "delete(" Backend/app/db/repositories/` returns only `soft_delete`. The retention job F20 builds ships with `retention_enabled = False` (Gate 1 Q2, your ruling). So on the day this merges, **no data is deleted on any schedule.**

The shipped interim `checkin.notice` says «ונמחקים כמה ימים לאחר הביקור» — *"and are deleted a few days after the visit"*. **That statement is false today**, and it is a statement made at the moment of collection to a member of the public. It is a live compliance defect, not a future one.

**Consequence for the copy**: none of my strings promise a deletion schedule. They say the data is kept as long as it is needed, and that she can ask for erasure at any time — which is true, enforceable today (the erase endpoint), and does not become a lie because a flag is off.

> If you would rather the notice state the concrete periods (15 minutes / 24 months / 7 years), it can — but only once `retention_enabled` is `True` in production, which by your Q2 ruling it is not. Say the word and I will draft the alternate paragraph for use after F21.

### F5 — **BLOCKER, found at review.** The shipped walk-in notice promises to keep an opted-in bride's contact detail *until she asks to remove the consent*, and F20 could honour neither half.

`he.ts:483` (shipped, live) says, in the same sentence F4 is about:

> «…אם סימנת אותה, **השם ומספר הטלפון יישמרו לצורך זה עד שתבקשי להסיר את ההסכמה**.»
> *(if you ticked it, the name and phone will be kept for this purpose until you ask to remove the consent)*

Two independent problems, and the first draft of this deck quoted only the **first** half of that sentence (the deletion clause, F4) and reproduced the second half unchanged:

1. **The plan's `queue_tickets` retention policy (DR-11) destroys it.** An unconditional 7-day SCRUB blanking `name` and `phone`, with no `marketing_opt_in_at IS NULL` carve-out. A walk-in who ticks the box has her contact detail destroyed in 7 days by F20's own job, while the notice at the moment of collection told her it would be kept until she withdrew.
2. **There was no way for her to withdraw.** `POST /manage/privacy/marketing-withdraw` is keyed on `customer_id` and writes `customers.marketing_consent_withdrawn_at`. A walk-in who has never booked online has **no `customers` row** (spec: *"A customer row can only be created inside `create_booking`"*), and DR-10 declines the promotion of a queue-ticket opt-in into `customers`. So the operative consent text promised a revocation method that did not exist — and a §30A consent whose stated revocation method does not exist is arguably not a valid consent.

**Resolution, agreed with the plan and applied in both documents** (plan §1 DR-11, task C5, and Risk R-H):

- **The 7-day SCRUB stays unconditional.** Holding an opted-in walk-in's name and phone *without a clock* — to honour a marketing promise that has no sender (Out of scope: no marketing send exists in v1, `MessageKind` gains no member) and, until now, no withdrawal control — would be the "kept forever" this whole feature exists to end. The promise being dropped is one in the **boutique's** commercial favour, not a subject protection; dropping it narrows nothing she is entitled to.
- **`marketing-withdraw` gains a `phone` arm** that clears `queue_tickets.marketing_opt_in_at` for that tenant and phone. One `UPDATE`, one optional schema field, on a route F20 already builds. This makes the §30A revocation sentence in Strings 6 and 7 **true for a walk-in for the first time**.
- **The retention sentence in String 6 is rewritten** to what the code does: kept only as long as needed for managing the queue, with erasure available on request. The exception clause is struck.

This is a spec-level change and it is recorded as such, not absorbed into the Hebrew silently.

---

## Open question for the plan (not decided here)

D13 says there is **one** notice document, rendered both inline at collection and on `/privacy`. That was written when the only collection point was the booking form. There are now two collection surfaces with a materially different fact each:

- **booking** — she gives a phone that receives an SMS; nothing about her is published anywhere.
- **check-in** — her queue position and **the first word of the name she typed** are published on an anonymous public web page (the F59 queue board).

One document cannot state the board fact correctly for both: on the booking form it would be over-broad (describing a publication that does not happen to her), and omitting it from `/checkin` would be under-broad, which at the moment of collection is worse.

**What I have done**: drafted `PLATFORM_NOTICE_HE` as the general notice (booking flow + `/privacy` page), and drafted a **separate, shorter, point-specific** `checkin.notice` that carries the board clause and links onward to `/privacy`. That is what the shipped code's structure already assumes.

**What the plan must decide**: whether `checkin.notice` stays an i18n key (as shipped) or becomes a second tenant-overridable field. It is a spec/plan question, not a copy question, and I have not resolved it by writing the copy one way.

---

## String 1 — `PLATFORM_NOTICE_HE`

**Where it renders**: (a) inline on the booking form's `details` step, above the card, at the moment she types her name; (b) as the body of the `/privacy` page. Same string, both places. Overridable per boutique.

**Byte count: 3 746 bytes** (2 100 characters) — **45.7 % of the 8 192-byte cap**. No `<` character anywhere.

```
הפרטים שאת מוסרת לנו נשמרים אצל {{boutique}}. הבוטיק הוא בעל המאגר והאחראי למידע שבו, ואנחנו משתמשות בפרטים כדי לקבוע את התור שלך ולנהל אותו, ולא לשום מטרה אחרת — למעט פניות שיווקיות, ורק אם סימנת בעצמך את תיבת ההסכמה. מסירת הפרטים היא מרצון, ובכל עת אפשר לבקש מאיתנו לעיין במידע שנשמר עלייך, לתקן אותו או למחוק אותו.

מה אנחנו מבקשות, ולמה:
• שם מלא — כדי לרשום את התור על שמך ולקרוא לך בשמך כשתגיעי.
• מספר טלפון נייד — כדי לשלוח קוד אימות חד-פעמי לפני קביעת התור, לאשר לך את המועד, לשלוח תזכורת לקראתו וליצור איתך קשר אם משהו משתנה.
• סוג הפגישה, המועד, השמלה והמידה שבחרת, וכל מה שסיפרת לנו מראש — כדי להכין את הביקור.

אין חובה חוקית למסור לנו את הפרטים האלה, וההחלטה היא שלך. בלי שם ובלי מספר נייד לא נוכל לקבוע לך תור באתר — אי אפשר לאמת את המספר, לשמור לך את המועד או לעדכן אותך אם משהו משתנה. תמיד אפשר לפנות אלינו ולקבוע תור ישירות מול הבוטיק.

למי המידע מגיע:
• לצוות הבוטיק, לפי התפקיד של כל אחת.
• לחברה שמפעילה עבורנו את האתר ואת מערכת התורים, ולספקי התשתית שהיא נעזרת בהם כדי לאחסן את המידע ולשלוח אלייך את המסרונים. הם מעבדים את המידע עבורנו בלבד ולפי הוראותינו.
• לגורם שאנחנו חייבות למסור לו מידע לפי דין, אם נידרש לכך.

איננו מוכרות את הפרטים שלך ואיננו מעבירות אותם למפרסמים.

את פרטי התור ואת ההודעות ששלחנו לך אנחנו שומרות כל עוד הם דרושים לניהול הביקורים ולחובות הרישום והדיווח שחלות עלינו. אפשר לבקש מחיקה גם לפני כן, וכך נעשה — למעט מידע שאנחנו חייבות לשמור לפי דין, שיישמר בלי שמך ובלי מספר הטלפון שלך.

הזכויות שלך:
• לעיין במידע שנשמר עלייך.
• לבקש לתקן מידע שאינו מדויק.
• לבקש למחוק את המידע.

כדי לממש כל אחת מהזכויות האלה אפשר לפנות אלינו ישירות — בבוטיק, או בפרטי הקשר שמופיעים באתר. נבקש לוודא את זהותך לפני שנמסור מידע או נמחק אותו, כדי שהפרטים שלך לא יגיעו לאדם אחר, ונשיב לפנייה בתוך שלושים יום.

הפרטים שלך לא ישמשו לפניות שיווקיות אלא אם סימנת בעצמך את תיבת ההסכמה שבטופס קביעת התור. התיבה אינה מסומנת מראש, וקביעת התור אינה תלויה בה.

אם סימנת אותה ואת רוצה להפסיק — אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת, בטלפון או בבוטיק. אין צורך להסביר למה, אפשר לומר זאת לכל אחת מאיתנו, וההסרה נכנסת לתוקף מיד. הסרת ההסכמה אינה משפיעה על התור שלך או על השירות שאת מקבלת.
```

### Clause by clause

| # | Hebrew (opening words) | What it says, in plain English | Why it is there |
|---|---|---|---|
| 1 | «הפרטים שאת מוסרת לנו נשמרים אצל {{boutique}}. הבוטיק הוא בעל המאגר…» | The details you give us are kept by **[boutique name]**. The boutique is the *owner of the database* and is responsible for the information in it. | **§11(b)(1) — who the controller is.** «בעל מאגר» is the statute's own term (PPL §1), not a paraphrase. This is also the sentence that puts the boutique's *name* in front of her, which is why the string is a template. **Revised at review**: the first draft opened «הפרטים שאת **ממלאת כאן**» — *"the details you are filling in here"*. That is the booking form's deixis, and D13 renders this same string on `/privacy`, where she is filling in nothing. «מוסרת לנו» reads correctly inline (she is giving them now) and as a standalone page. |
| 2 | «…ואנחנו משתמשות בפרטים כדי לקבוע את התור שלך ולנהל אותו, ולא לשום מטרה אחרת — למעט פניות שיווקיות, ורק אם סימנת בעצמך את תיבת ההסכמה.» | We use the details to book and manage your appointment, and for nothing else — except marketing approaches, and only if you yourself ticked the consent box. | **§11(b)(2) — the purpose.** **Revised at review**: the first draft ended the sentence at «ולא לשום מטרה אחרת» and was then contradicted eight paragraphs later by clause 11. An absolute purpose limitation that the same document contradicts is worse than a scoped one, and it is the sentence a complainant would quote. The exception is now stated where the limit is stated. |
| 3 | «מסירת הפרטים היא מרצון, ובכל עת אפשר לבקש מאיתנו לעיין… לתקן… או למחוק…» | Giving the details is voluntary, and at any time you may ask us to see, correct or delete what is stored about you. | **§11(b)(3) voluntariness + §13/§14 rights, front-loaded.** Deliberate: this first block alone discharges the core of §11, so the notice is compliant even for a reader who reads one paragraph and stops. ⚠ On correction, see item 8 of "What this approval does NOT cover" — the right is stated because it is the law; the console serves one third of it. |
| 4 | «מה אנחנו מבקשות, ולמה:» + three bullets | What we ask for and why: full name (to register the appointment in your name and greet you by it); mobile number (one-time verification code, confirmation, a reminder ahead of it, and to reach you if something changes); appointment type / time / dress / size / anything you told us in advance (to prepare the visit). | **§11(b)(2), itemised.** Per-datum purposes rather than one blanket sentence — a blanket purpose is what makes a notice unfalsifiable. Every purpose here maps to shipped code (`otp/send`, `confirmation_sms_body`, `reminder_sms_body`, `bookings.notes`, `dress_size`). «תזכורת **לקראתו**» rather than «לפניו» — the idiom. |
| 5 | «אין חובה חוקית למסור… וההחלטה היא שלך. בלי שם ובלי מספר נייד לא נוכל לקבוע לך תור באתר… תמיד אפשר לפנות אלינו ולקבוע תור ישירות מול הבוטיק.» | There is no legal obligation to give these details, and the decision is yours. Without a name and a mobile number we cannot book you online — we cannot verify the number, hold the time, or tell you if something changes. You can always contact us and book directly with the boutique. | **§11(b)(3) — voluntariness *and the consequence of refusing*.** The second half is the part most notices omit and the part the statute actually asks for. **Revised at review**: the first draft said «תמיד אפשר **להתקשר** אלינו» — but `he.ts:685` proves a tenant can publish neither a phone nor an Instagram (*"בשלב זה לא פורסמו כאן מספר טלפון או חשבון אינסטגרם"*), so the notice named a channel that may not exist. The wording now names no channel. |
| 6 | «למי המידע מגיע:» + three bullets | Who the information reaches: the boutique's staff, by each person's role; the company that runs the website and queue system for us and the infrastructure suppliers it uses to store the data and send the text messages — they process it only for us and on our instructions; and any body we are legally required to give information to. | **§11(b)(4) — to whom the data is transferred and for what purpose.** "By each person's role" is true (`require_role`, `StaffRole` — five members). "Only for us and on our instructions" is the processor relationship (`architecture.md:20`). **Two revisions at review**: (a) the trailing pointer «והרשימה המלאה שלהם מופיעה **בעמוד הפרטיות של האתר**» is **deleted** — on `/privacy` the reader is already on that page with the list rendered directly below, a self-referential dead end, and inline it is redundant because the block's only chrome is a real `/privacy` link (spec §Frontend changes); (b) «הודעות ה-SMS» → «המסרונים», removing the one `ה-` + Latin-acronym juncture, which was the deck's most awkward BiDi seam. |
| 7 | «איננו מוכרות את הפרטים שלך ואיננו מעבירות אותם למפרסמים.» | We do not sell your details and we do not pass them to advertisers. | Not a statutory requirement. It is the single question a bride actually has, and it is true. Strike it if you want a leaner document — nothing depends on it. |
| 8 | «את פרטי התור ואת ההודעות ששלחנו **לך** אנחנו שומרות כל עוד הם דרושים… אפשר לבקש מחיקה גם לפני כן…» | We keep your appointment details and the messages we sent **you** for as long as they are needed to manage visits and for the record-keeping and reporting duties that apply to us. You can ask for deletion sooner, and we will do it — except for information we are legally required to keep, which will be kept **without your name and without your phone number**. | **Honest retention, deliberately not a schedule** — see finding F4. The last clause is a precise description of what the erase endpoint actually does: it scrubs `customers.name`/`phone`/`notes`/`tags` and `bookings.notes` and keeps the business record. The «לך» was missing in the first draft; without it the phrase reads as messages sent to anyone. |
| 9 | «הזכויות שלך:» + three bullets | Your rights: to see the information stored about you; to ask to correct inaccurate information; to ask to delete the information. | **§13 (access) and §14 (correction / deletion), stated as rights.** ⚠ Correction is one-third served in the console — see "does NOT cover" item 8. The clause stays: §14 is the law regardless of what we built, and the boutique must honour it by hand. |
| 10 | «כדי לממש… אפשר לפנות אלינו ישירות — בבוטיק, או בפרטי הקשר שמופיעים באתר. נבקש לוודא את זהותך… ונשיב לפנייה בתוך שלושים יום.» | To exercise any of these, contact us directly — at the boutique, or through the contact details shown on the site. We will ask to verify your identity before handing over or deleting information, so that your details do not reach someone else. We will answer within thirty days. | **The channel and the statutory 30-day response clock.** **Revised at review** for the same reason as clause 5: «בטלפון או כאן בבוטיק» named a phone that may not be published, and «כאן» is wrong on `/privacy` and wrong for a bride booking online at 11pm — `he.ts:685` fixes «בבוטיק **עצמו**» as the physical shop. ⚠ **Two operational obligations no code enforces** live in this sentence — the 30-day clock and the identity check. Both are named in "does NOT cover" item 3. |
| 11 | «הפרטים שלך לא ישמשו לפניות שיווקיות אלא אם סימנת בעצמך את תיבת ההסכמה **שבטופס קביעת התור**. התיבה אינה מסומנת מראש, וקביעת התור אינה תלויה בה.» | Your details will not be used for marketing approaches unless **you yourself** ticked the consent box **on the booking form**. The box is not pre-ticked, and booking does not depend on it. | **Communications Law §30A — consent must be separate, affirmative, unbundled and default-off.** All three properties are stated because all three are structurally true in the build: a NULL timestamp is the absence of consent, the box lives two navigations away from the required terms checkbox, and nothing in `create_booking` conditions on it. **Revised at review**: the first draft used the definite «תיבת ההסכמה» / «התיבה» twice with no box on screen — correct inline, incoherent on `/privacy`. Naming the form fixes both renderings. |
| 12 | «אם סימנת אותה ואת רוצה להפסיק — …» (String 2, below) | see String 2 | **§30A — the revocation method.** |

---

## String 2 — the §30A withdrawal sentence

This is **not a separate constant**. It is the last block of `PLATFORM_NOTICE_HE`, extracted here because it is the clause your Q4 ruling reaches into and the one clause no code change can discharge on its own.

**Byte count: 402 bytes** (225 characters), inside String 1's 3 746.

```
אם סימנת אותה ואת רוצה להפסיק — אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת, בטלפון או בבוטיק. אין צורך להסביר למה, אפשר לומר זאת לכל אחת מאיתנו, וההסרה נכנסת לתוקף מיד. הסרת ההסכמה אינה משפיעה על התור שלך או על השירות שאת מקבלת.
```

**Plain English**: *If you ticked it and you want to stop — you can ask us to remove the consent at any time, by phone or at the boutique. There is no need to explain why, you can say it to any one of us, and the removal takes effect immediately. Removing the consent does not affect your appointment or the service you receive.*

| Phrase | Why exactly this wording |
|---|---|
| «אפשר לבקש **מאיתנו**» — *"you can ask **us**"* | Your **Q4 ruling** is what this phrase encodes. The opt-out route ships `(OWNER, SHIFT_MANAGER)`, so any front-desk staffer can honour it. The sentence therefore says *the boutique*, not *the owner*. A bride standing in a shop has no way to tell which woman behind the counter is the owner, and a notice that told her to find one would make the right harder to exercise than the code makes it. |
| «בטלפון או **בבוטיק**» (not «כאן בבוטיק») | **Revised at review.** «כאן» was wrong in **both** of this string's renderings: a bride booking online is not in the shop, and a reader of `/privacy` is not either. `he.ts:685`'s «בבוטיק עצמו» fixes the word as the physical place. String 6 keeps «כאן» — it is the one surface where she really is standing there. |
| «אין צורך להסביר למה» | §30A revocation may not be conditioned. Saying so pre-empts a staffer asking "why?" at the counter. |
| «וההסרה נכנסת לתוקף מיד» | True: `POST /manage/privacy/marketing-withdraw` is one UPDATE, and no marketing send exists to race it. The missing «ו» before «אפשר» is also fixed — the first draft was a comma splice. |
| «אינה משפיעה על התור שלך **או** על השירות» | Anti-detriment. Consent that a customer fears will cost her the appointment is not free consent. «ועל» → «או על»: after a negation Hebrew takes «או». |

> **What this sentence deliberately does NOT say**: «אפשר להסיר את ההסכמה בכל הודעה» — *"you can remove consent in every message"*. The **currently shipped** `checkin.optIn` says exactly that (`he.ts:488`), and it is a promise about messages that do not exist and an unsubscribe path that is not built — F46/E10 owns it, per the spec's own Out-of-scope. My replacements for both opt-in labels drop that clause. When F46 ships the in-message opt-out, the clause can be added back and it will be true.

---

## String 3 — `PLATFORM_DPA_HE`

**Where it renders**: the second section of the public `/privacy` page. **Overridable per boutique** — written as a sensible default a boutique's own lawyer might edit.

**Byte count: 1 544 bytes** (860 characters) — **18.8 % of cap**. No `<`.

```
הבוטיק הוא בעל המאגר והאחראי למידע שנאסף באתר הזה. את אתר הבוטיק, את מערכת התורים ואת משלוח ההודעות מפעילה עבורנו MODRYN, מפעילת הפלטפורמה, שמחזיקה במידע ומעבדת אותו עבורנו בלבד ולפי הוראותינו.

MODRYN אינה רשאית להשתמש במידע למטרות משלה, למכור אותו או להעביר אותו לאחרים — למעט ספקי התשתית שרשומים בהמשך, ולמעט מסירה שאנחנו או היא חייבות בה לפי דין. ההתקשרות איתה כוללת התחייבות לשמירת סודיות ולנקיטת אמצעי אבטחה.

אלה אמצעי האבטחה שננקטים בפועל:
• הגישה למידע ניתנת רק לצוות הבוטיק, לפי התפקיד של כל אחת, ומחייבת כניסה אישית עם סיסמה.
• המידע של כל בוטיק מופרד מהמידע של בוטיקים אחרים ברמת בסיס הנתונים.
• התקשורת בין הדפדפן לשרת מוצפנת.
• סיסמאות נשמרות בגיבוב חד-כיווני ולא בטקסט גלוי.
• פעולות שינוי ומחיקה שהצוות מבצע במידע של לקוחה נרשמות ביומן פעילות.

אם יתרחש אירוע אבטחה שיש בו חשש לפגיעה במידע שלך, ניידע אותך ואת הרשות להגנת הפרטיות כנדרש לפי דין.
```

### Clause by clause

| # | Plain English | Why it is there — and what in the code makes it true |
|---|---|---|
| 1 | The boutique is the owner of the database and responsible for the information collected on this site. The boutique's site, the queue system and the sending of messages are operated for us by **MODRYN, the platform operator**, which **holds** the information and processes it only for us and on our instructions. | Establishes the **controller / processor** split in the statute's own vocabulary — «בעל מאגר» (owner) and «מחזיק» (holder, PPL §3). **Revised at review — this is a real §11(b)(4) fix.** The first draft said «חברת שירות חיצונית» (*an external service company*) and never named it, which was backwards: the notice named the **sub**-processors (Railway, Twilio, AWS) and refused to name the **processor** — the one entity that holds every name, phone and note. ⚠ `MODRYN` is the platform's **brand** (`README.md:3,7`; the domain is `*.modryn.co.il`), not a verified registered company name. The **registered legal entity** must replace or accompany it before pilot — see "does NOT cover" item 9. |
| 2 | MODRYN may not use the information for its own purposes, sell it, or pass it to others — except the infrastructure suppliers listed below, and except a disclosure that we or it are legally required to make. The engagement with it includes an undertaking of confidentiality and of security measures. | The three prohibitions a processor clause has to carry, plus the two honest exceptions. The "listed below" pointer is what ties this section to String 4 and is why String 4 must render *beneath* it. ⚠ The last sentence asserts a **contractual fact** about a DPA that `architecture.md:20` places "in ToS". If that ToS clause does not exist at merge, the sentence is false — flagged in "does NOT cover" item 3. |
| 3a | Access is given only to the boutique's staff, by each person's role, and requires a personal login with a password. | True: `require_role(StaffRole…)`, per-staff sessions, `staff_users`. **Revised**: «אנשי הצוות» (masculine) + «כל אחת» (feminine) was a gender clash inside one clause; String 1 clause 6 already had «לצוות הבוטיק» right. «התחברות» → «כניסה» drops a calque. |
| 3b | Each boutique's information is separated **from other boutiques'** at the database level. | True: Postgres row-level security per tenant. This is the strongest single security claim in the document and it is the one a lawyer will ask about. **Revised**: the «מ…» complement was stranded from «מופרד»; it now follows it. |
| 3c | Communication between browser and server is encrypted. | True: HTTPS in every deployed environment. |
| 3d | Passwords are stored as a one-way hash, not **in plain text**. | True: `argon2-cffi` is a declared runtime dependency; `staff_users` stores a hash. **Revised**: «כטקסט **קריא**» reads as *legible* (a font property); the security term is «גלוי». |
| 3e | **Change and deletion actions** staff take on a customer's information are recorded in an activity log. | **Revised at review — the first draft over-stated the claim.** `AuditLogRepository.record` is called from a scattered set of **mutation** paths (`customers/service.py`, `atelier/service.py`, `payments/`, `booking/owner.py`). **No read is logged**: an owner opening a booking list and reading a customer's phone leaves no trace. Under the Security Regulations an access-logging claim is a specific one, and the unqualified plural made it. Narrowed to what the code does. |
| 4 | If a security incident occurs that raises a concern of harm to your information, we will notify you and the Privacy Protection Authority as required by law. | **Amendment 13's breach-notification duty.** «הרשות להגנת הפרטיות» is the regulator's current legal name. The spec commits to a written incident-response procedure as section 3 of `.planning/ppl-compliance-record.md`; this sentence is its public face. ⚠ It is a promise only as good as that procedure — do not approve this clause if the procedure will not exist at merge. |

> **On «גיבוב חד-כיווני»** (*one-way hashing*): this is the one piece of technical vocabulary in the whole deck. It is the correct Hebrew term and it is what a reviewing lawyer will look for. Say the word if you would rather have the plainer «בצורה מוצפנת שאי אפשר להפוך בחזרה» — it is less precise but readable by anyone.

---

## String 4 — `PLATFORM_SUBPROCESSORS_HE`

**Where it renders**: the third section of `/privacy`, beneath the DPA clause. **Platform-owned and structurally un-overridable** (D14, your Q3 ruling) — a boutique may rewrite what it promises about processing, and may not misstate who the processors are.

**Derived from the code as it is today**, not from the spec's list, and under the single disclosure principle stated in F2b: *the list names every processor the platform is built to use, and says of each whether it is in use today.*

**Byte count: 1 583 bytes** (896 characters) — **19.3 % of cap**. No `<`.

```
כדי להפעיל את השירות אנחנו נעזרות בספקי תשתית. הרשימה הזאת נקבעת על ידי מפעילת הפלטפורמה, היא זהה בכל הבוטיקים שמשתמשים בפלטפורמה, והיא מתעדכנת כשמצטרף ספק חדש. לצד כל ספק כתוב גם אם הוא בשימוש כיום.

• אחסון והפעלה — חברת Railway מפעילה את השרתים ואת בסיס הנתונים שבו נשמרים הפרטים שמסרת. שרתיה ממוקמים מחוץ לישראל, ולכן המידע מועבר ונשמר מחוץ לגבולות המדינה.
• משלוח הודעות SMS — כשמשלוח ההודעות מופעל, חברת Twilio מקבלת את מספר הטלפון שלך ואת תוכן ההודעה, לצורך שליחת קוד האימות, אישור התור והתזכורות בלבד. גם היא פועלת מחוץ לישראל. כשהמשלוח אינו מופעל, לא נשלחות הודעות ולא מועבר אליה מידע.
• אחסון תצלומים — שירותי האחסון של Amazon Web Services שומרים את תצלומי השמלות של הקולקציה, באזור השירות שבישראל. אין בהם שם, מספר טלפון או כל פרט אחר שלך.

בשלב זה איננו נעזרות בשירות סליקה או תשלומים, ולא נאספים באתר פרטי אמצעי תשלום. אם יתווסף שירות כזה, הוא יופיע ברשימה הזאת לפני שייעשה בו שימוש.
```

### Clause by clause, with the evidence for each

| # | Plain English | Evidence in the code | Note |
|---|---|---|---|
| 0 | To run the service we use infrastructure suppliers. This list is set by the platform operator, it is identical across every boutique that uses **the platform**, and it is updated when a new supplier joins. **Beside each supplier it also says whether it is in use today.** | D14 / your Q3 ruling; the disclosure principle of F2b. | **Revised twice at review**: «שמשתמשים **בה**» had «הרשימה» as its nearest feminine antecedent, giving the circular *"every boutique that uses the list"* — the intended antecedent «הפלטפורמה» is three words further back. And the last sentence is new: it is the stated principle that makes the conditional Twilio bullet legible rather than odd. |
| 1 | **Storage and operation — Railway.** It runs the servers and the database in which the details you gave are stored. Its servers are located outside Israel, so the information is transferred and stored outside the country. | `docs/infra-runbook.md:115-119`: services `api`, `worker`, and **`Postgres` — Railway-managed**. The database holding every name, phone and note is Railway's. | ⚠ **The most consequential single line in the deck.** The runbook documents **no Railway region**, and Railway's default regions are not in Israel. A cross-border transfer must be disclosed, so the line discloses it. **I could not verify which country.** If you can establish the region, the line should name it; pinning Railway to an EU region is a materially better legal position and worth doing before pilot. **Revised**: «ונשמר **גם** מחוץ לגבולות המדינה» asserted it is *also* stored inside Israel, which is the opposite of what the sentence exists to say. «גם» struck. |
| 2 | **Sending SMS — Twilio.** *When message sending is enabled*, it receives your phone number and the content of the message, for sending the verification code, the appointment confirmation and the reminders only. It too operates outside Israel. *When sending is not enabled, no messages are sent and no information is passed to it.* | Finding F1. `sms_provider` ships **unset**; `_forbid_sms_test_paths_in_production` rejects only `"fake"`; the documented deployment runs `APP_ENV=staging` with `fake`. `twilio.py` is a real adapter and `httpx` is a runtime dependency because of it. | **Revised at review — conditional, not present-tense fact.** Names *what* Twilio receives (number + body) and *when*. That is the disclosure that matters: the message body carries her appointment time and a manage link. |
| 3 | **Photo storage — Amazon Web Services storage.** Its storage services **hold the collection's dress photographs**, in the Israel service region. They contain no name, phone number or any other detail of yours. | `media_region = "il-central-1"` (AWS Israel/Tel Aviv), `Backend/.env.example:20`, `docs/infra-runbook.md:15-29,211`. `s3.py` is reached only from the catalog media path — the key embeds `tenant_id, dress_id, media_id` and no customer-facing upload path exists. | The "holds nothing of yours" clause is doing real work: without it, a reader assumes her data is on AWS too. And it is genuinely true — S3 here is a dress-photo bucket. **Revised**: bullets 1 and 2 are full sentences and bullet 3 was a bare noun phrase; it now has a verb. |
| 4 | At this stage we do not use a clearing or payments service, and **no payment-method details are collected** on the site. If such a service is added, it will appear in this list **before** it is used. | Finding F2. `payment_provider` accepts only `"fake"` and `"lemonsqueezy"`, and `config.py` raises at boot on **both** when `APP_ENV=production`. | The forward promise in the second sentence is the mitigation for Risk 7 (nothing in CI can catch a missed amendment) stated as a public commitment. **Revised**: «גבייה של אמצעי תשלום» conflated גבייה (collecting *money*) with איסוף (collecting *data*) — nobody writes that. |

### Processors the spec anticipated that are **not** in this list, and why

| Spec mentions | Verdict | Reason |
|---|---|---|
| Twilio ("must not name as live") | **Named, conditionally — the spec is stale and its correction is argued in F1, not absorbed.** | Finding F1. |
| Grow (F17/F18 payments) | **Not named.** | Never wired. `payment_provider` has no such literal. |
| Lemon Squeezy (F18) | **Not named.** | Finding F2 — forbidden in production by a boot validator. Naming a test-mode engine as a live processor would be a false disclosure. |
| Cloudflare Stream (F47) | **Not named.** | Not built. No dependency, no config field, no code. |
| AWS KMS (`gateway_secret_box="kms"`) | **Not named.** | The literal does not exist yet — `Literal["fake"] \| None`. Add to the list when `KmsSecretBox` ships. |

**Processors I checked for and did not find**: analytics, error tracking (no Sentry), email, CDN, font hosting (`he.ts:644` states the Hebrew fonts are self-hosted precisely so no external service is called), maps (the maps link is an outbound `href`, not a request the site makes). The runtime dependency list is `fastapi, uvicorn, sqlalchemy, asyncpg, alembic, pydantic-settings, argon2-cffi, pydantic, boto3, httpx, tzdata, segno` — nothing there reaches a service the list omits.

---

## String 5 — the manage-app disclaimer, and the `reason`-field hint

**Where they render**: the **manage console only** — the disclaimer above the two textareas in `PrivacySection`, the hint under the `reason` field in the erase panel. **Neither may appear in any of the three public documents**, and `test_privacy_text.py` asserts exactly that, bidirectionally. The person who needs this warning is the controller; a public privacy notice that announces its own legal unreliability is worse than no notice.

### 5a — the not-lawyer-reviewed disclaimer

**Byte count: 956 bytes** (531 characters). No `<`.

```
הנוסח שמופיע כאן הוא ברירת מחדל שהכינה מפעילת הפלטפורמה. הוא לא נבדק על ידי עורך דין ואינו ייעוץ משפטי.

הבוטיק הוא בעל המאגר והאחראי החוקי למידע של הלקוחות, ולכן האחריות על מה שכתוב בהודעת הפרטיות שלו היא של הבוטיק. מומלץ להעביר את הנוסח לעורך דין לפני שמסתמכים עליו, ולוודא שהוא מתאר את מה שהבוטיק באמת עושה עם המידע.

אפשר לערוך כאן את הודעת הפרטיות ואת סעיף עיבוד המידע. רשימת ספקי התשתית נקבעת על ידי מפעילת הפלטפורמה ואי אפשר לערוך אותה — כך היא נשארת נכונה בכל הבוטיקים כשמצטרף ספק חדש. שדה שנשאר ריק חוזר לנוסח ברירת המחדל.
```

| # | Plain English | Why |
|---|---|---|
| 1 | The wording shown here is a default prepared by the platform operator. It has **not been reviewed by a lawyer** and is not legal advice. | Risk 1. The pilot goes live on un-reviewed text; the owner must know that before she publishes it under her own name. |
| 2 | The boutique is the owner of the database and the legally responsible party for customers' information, so responsibility for what its privacy notice says belongs to the boutique. It is recommended to have the wording reviewed by a lawyer before relying on it, and to check that it describes what the boutique actually does with the information. | Tells her **why** it is her problem, not just that it is. The last clause is the useful instruction: the default describes what the *platform* does; if her shop does something else with the data, the text is wrong for her. |
| 3 | You can edit the privacy notice and the data-processing clause here. The list of infrastructure suppliers is set by the platform operator and cannot be edited — that way it stays correct across every boutique when a new supplier joins. **A field left empty reverts to the default wording.** | D14 explained to the person who will otherwise ask why one box is missing, and D4's revert sentinel explained where she will discover it. |

### 5b — the `reason`-field hint ("record why, never who")

**Byte count: 286 bytes** (159 characters). No `<`. Comfortably inside `MAX_ERASE_REASON_BYTES = 500`, which the hint deliberately does not state — the field's byte counter does.

```
לרשום למה נמחק המידע — למשל: בקשת מחיקה טלפונית שאומתה מול הלקוחה. לא לרשום שם, מספר טלפון או פרט מזהה אחר: השורה הזאת נשמרת ביומן הפעילות לצמיתות ואינה נמחקת.
```

**Plain English**: *Record **why** the information was deleted — for example: a telephone deletion request, verified with the customer. Do **not** record a name, phone number or any other identifying detail: this line is kept in the activity log permanently and is not deleted.*

| Part | Why |
|---|---|
| The worked example | D19 predicts the failure mode precisely — the field is free text on a route whose subject is a named person, so it will read «רונית ביקשה שימחקו אותה, 050-…». A hint that only forbids gets ignored; a hint that shows an acceptable sentence gets copied. |
| «לא לרשום שם, מספר טלפון או פרט מזהה אחר» | The prohibition, itemised. A test asserts no subject name or full phone reaches `audit_log.details`, but the test fires *after* the owner has typed it — the hint is the only control that fires before. |
| «נשמרת ביומן הפעילות לצמיתות ואינה נמחקת» | The reason for the rule. `audit_log` is exempt from every retention class **forever** (deliberately — it is the evidence the erasures happened). Writing a phone number into it would put a permanent copy of the identifier in the one table designed never to be erased, inside the very action that exists to destroy it. |

---

## Strings 6–8 — required by shipped code, not named in the brief (finding F3)

`he.ts:452-482` names F20 as the owner of these values. They are drafted here so that approving this deck leaves no interim, un-approved Hebrew on any collection surface.

### 6 — `checkin.notice` (replaces the interim value at `he.ts:483`)

**Byte count: 1 169 bytes** (658 characters). No `<`. Renders as an i18n string with `{{boutique}}` interpolation, exactly as today. **Three blank-line-separated paragraphs** (R1's `pre-line` rendering does real work here).

```
הפרטים שאת מוסרת כאן נשמרים אצל {{boutique}} לצורך ניהול התור בלבד — לשמור את מקומך ולקרוא לך כשיגיע תורך. מסירתם היא מרצון; בלי שם ובלי מספר נייד לא נוכל לרשום אותך לתור, ותמיד אפשר לפנות לאחת מאיתנו כאן.

מקומך בתור והמילה הראשונה בשם שהזנת מוצגים בלוח התור של הבוטיק — עמוד אינטרנט ציבורי שכל מי שיודע את כתובת האתר של הבוטיק יכול לפתוח, ולא רק מסך שנמצא בתוך החנות. מספר הטלפון שלך לא מוצג שם.

הפרטים לא ישמשו לפניות שיווקיות אלא אם סימנת את התיבה שלמטה, ואפשר לבקש מאיתנו להסיר את ההסכמה בכל עת. את הפרטים אנחנו שומרות רק כל עוד הם דרושים לניהול התור, ואפשר לבקש מאיתנו לעיין במידע שנשמר עלייך, לתקן אותו או למחוק אותו. פירוט מלא בעמוד הפרטיות של האתר.
```

**What changed from the shipped interim value:**

| Change | Why |
|---|---|
| **Removed** «ונמחקים כמה ימים לאחר הביקור» (*"and are deleted a few days after the visit"*) | **Finding F4 — it is false.** Nothing is hard-deleted anywhere in the system, and by your Q2 ruling the retention job ships switched off. |
| **Removed** «אם סימנת אותה, השם ומספר הטלפון יישמרו לצורך זה עד שתבקשי להסיר את ההסכמה» (*"if you ticked it, the name and phone will be kept for this purpose until you ask to remove the consent"*) | **Finding F5 — the BLOCKER.** F20's own `queue_tickets` retention policy blanks name and phone at 7 days regardless of the box, so the sentence promised the opposite of what the feature does. The replacement clause states the actual rule: kept only as long as needed for managing the queue. What she loses is a promise in the **boutique's** commercial favour; what she gains is a revocation control that now exists. |
| **Replaced** the retention promise with «את הפרטים אנחנו שומרות רק כל עוד הם דרושים לניהול התור» | True today (purpose limitation), true after F21 (the 7-day scrub is what "no longer needed" means for a queue ticket), and it does not become a lie because a flag is off. Same posture as String 1 clause 8. |
| **Added** «מסירתם היא מרצון; בלי שם ובלי מספר נייד לא נוכל לרשום אותך לתור, ותמיד אפשר לפנות לאחת מאיתנו כאן» | §11(b)(3) — the interim value stated no voluntariness and no consequence at all. This is a §11 element that was simply missing from a live collection point. «לפנות **לאחת מאיתנו** כאן» rather than «בדלפק»: one approaches a person, not a counter. |
| **Added** «אפשר לבקש מאיתנו לעיין… לתקן… או למחוק…» | §13/§14 — also entirely absent from the interim value. ⚠ For a walk-in who has never booked online, the console cannot serve these — see "does NOT cover" item 7. The clause stays because the right does. |
| **Added** «ואפשר לבקש מאיתנו להסיר את ההסכמה בכל עת» | §30A revocation method, under your Q4 ruling — front desk, not the owner. Absent from the interim value, and **only true because of finding F5's `phone` arm on `marketing-withdraw`**. |
| **Added** «פירוט מלא בעמוד הפרטיות של האתר» | Ties the short point-of-collection notice to the full document. |
| **Kept verbatim** the queue-board clause and «מספר הטלפון שלך לא מוצג שם» | The shipped comment at `he.ts:452-475` argues the board wording carefully and correctly — a public web page, not a screen in the shop; *the first word of the name she entered*, not "her first name". Both arguments hold. Nothing changed there, and `PUBLIC_PAGE_CLAUSE` («עמוד אינטרנט ציבורי») survives verbatim, so `i18n-keys.test.ts:132-143` passes **unedited**. |
| **Kept** «הם» → «הפרטים» in the marketing sentence | `he.ts:472-475` records this as a required collateral edit, not a tidy. It stays. |

**On length, honestly.** The interim value is 464 characters / 826 bytes; this is 658 / 1 169 — **+42 %**. The first draft argued the pointer sentence "keeps this string short enough to be read in a doorway" while shipping something half again as long, which is having it both ways. The honest framing: the interim was short because it was **missing three §11 elements**, and a notice cannot be shortened by omitting the law. What the length *does* buy is a paragraph structure — three blank-line-separated blocks instead of one unbroken run with two semicolons — so the doorway reader can stop after any of them and still have been told something complete.

> The shipped comment asks a fifth counsel question: *what must the notice say about a first name published on a public, unauthenticated web page?* This draft says it plainly and states that the phone number is not published. That is drafting, not legal clearance — the question stays open for counsel.

### 7 — `checkin.optIn` (replaces `he.ts:488`)

**Byte count: 196 bytes** (116 characters).

```
אני מאשרת קבלת הודעות SMS מ{{boutique}} על מבצעים, קולקציות חדשות ואירועים. אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת.
```

**Plain English**: *I agree to receive SMS messages from **[boutique]** about promotions, new collections and events. You can ask us to remove the consent at any time.*

Two changes from the shipped interim value:

1. «אפשר להסיר את ההסכמה **בכל הודעה**» (*"in every message"*) → «אפשר **לבקש מאיתנו** להסיר את ההסכמה **בכל עת**». See String 2's closing note — the in-message unsubscribe is F46's and does not exist. The replacement is true **only because of finding F5's `phone` arm**; without it this clause would be the same kind of promise it replaces.
2. **«אני מאשרת ש{{boutique}} תשלח לי…» → «אני מאשרת קבלת הודעות SMS מ{{boutique}}…»** — a review finding, and it affects every tenant with a non-feminine name. `תשלח` is feminine singular and forces that agreement on an arbitrary boutique name: «סטודיו כלות», «מרכז השמלות» and any Latin-script name («Bella Bride») all break it. The interim value has the same bug, but F20 *is* the swap, so it is F20's to fix. The nominalised form takes no verb agreement on the name at all — and, for free, removes the «ש»+name juncture, which was the hardest place to thread R4's FSI/PDI isolate.

### 8 — `booking.marketingOptIn` / `booking.marketingOptInHint` (new, booking form `details` step)

**Byte counts: 196 bytes** (116 characters) and **79 bytes** (44 characters).

```
אני מאשרת קבלת הודעות SMS מ{{boutique}} על מבצעים, קולקציות חדשות ואירועים. אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת.
```
```
לא חובה. קביעת התור אינה תלויה בסימון התיבה.
```

**Plain English (hint)**: *Not required. Booking the appointment does not depend on ticking the box.*

The label is **byte-identical to String 7 by design**: it is the same consent, to the same channel, from the same person, and two differently-worded consent labels in one product is how a §30A defence gets argued over. The hint is the anti-detriment statement, placed where the decision is made rather than only in the long notice. **Revised at review**: «סימון או אי-סימון של התיבה **אינם** משפיעים» — subjects joined by «או» take singular agreement, and the phrase duplicated String 1 clause 11 at greater length. The shorter form says the same thing correctly.

---

## What each clause is for — statutory duty map

| Clause | String | Statutory duty |
|---|---|---|
| Controller named, by name | 1 (cl. 1), 3 (cl. 1), 6 | **PPL §11(b)(1)** — the identity of the person requesting the data / the database owner |
| Processor named, by name | 3 (cl. 1) | **PPL §11(b)(4)** — added at review; the first draft named the sub-processors and not the processor |
| Purpose of collection, per datum | 1 (cl. 2, 4), 6 | **PPL §11(b)(2)** |
| Voluntariness + consequence of refusing | 1 (cl. 3, 5), 6 | **PPL §11(b)(3)** — the duty most notices omit |
| Recipients and their purpose | 1 (cl. 6), 3, 4, 6 | **PPL §11(b)(4)** |
| Right of access | 1 (cl. 3, 9, 10), 6 | **PPL §13** |
| Right of correction / deletion | 1 (cl. 3, 8, 9, 10), 6 | **PPL §14** — ⚠ correction is one-third served in the console; see "does NOT cover" item 8 |
| 30-day response | 1 (cl. 10) | **PPL §13/§14** response period |
| Marketing consent: separate, affirmative, default-off, unbundled | 1 (cl. 11), 7, 8 | **Communications Law §30A** |
| Marketing consent: how to revoke | 2, 6, 7, 8 | **Communications Law §30A** — revocation method. Servable for a booking subject via `customer_id` and, after finding F5, for a walk-in via the `phone` arm |
| Processor relationship + confidentiality + security measures | 3 | **PPL §8/§17B**, Amendment 13's controller-processor obligations |
| Cross-border transfer **disclosed** | 4 (cl. 1, 2) | Privacy Protection (Transfer of Data Abroad) Regulations. ⚠ **Disclosure is not the legal basis for transfer under those regulations** — the first draft's map credited this line with discharging them, which it does not. The Hebrew never claimed it; the map did. Corrected here: the transfer's lawful basis is a separate question for counsel. |
| Breach notification | 3 (cl. 4) | **Amendment 13** breach-notification duty |
| Sub-processor list, platform-owned | 4 | D14 / your Q3 ruling — makes an amendment reach every tenant structurally |
| Controller warned the text is not counsel-reviewed | 5a | Risk 1 — internal only, **must never appear publicly** |
| `reason` records why, never who | 5b | D19 — keeps the audit trail from defeating the erasure it records |

---

## Rendering requirements these strings impose

These are **testable build constraints**, not suggestions. Each one, if missed, silently damages a legal document.

| # | Requirement | What breaks without it |
|---|---|---|
| R1 | **Blank line = paragraph break; a single newline inside a block must be preserved** (CSS `white-space: pre-line` on the rendered block, or split on `\n` as well as `\n\n`). | Every bullet list in Strings 1, 3 and 4 collapses into one run-on line — and String 6's three paragraphs collapse into the wall of text the review objected to. The spec says the page "splits on a blank line into `<p>` elements"; that alone is not enough. |
| R2 | **`{{boutique}}` is substituted by literal string replacement, never `str.format()`.** | An overriding boutique whose text contains a `{` raises `KeyError`/`ValueError` at render time and blanks a legally-required document. `str.replace()` cannot fail. Placeholder token matches the shipped `he.ts` convention (`{{boutique}}`, `{{name}}`) so one token spans backend constants and i18n values. |
| R3 | **Substitution runs *after* resolution**, on whichever text won — platform default or boutique override. | An overriding boutique that keeps the `{{boutique}}` placeholder would publish the literal characters `{{boutique}}` on her privacy page. |
| R4 | **Wrap the substituted name in U+2068 (FSI) … U+2069 (PDI).** | **The first draft's stated reason was wrong and is corrected here.** It claimed a Latin-script name makes "the sentence-final period jump to the far left of the line" — but in an RTL paragraph, per UAX#9 N1/N2, a neutral between an LTR run and paragraph end resolves to the **paragraph** direction and lands left of the LTR island, which is where an RTL sentence-final period belongs. That is correct rendering, not a bug. The isolate is still worth having for the case that is real: a substituted name containing its **own** punctuation, digits or mixed script reorders the surrounding Hebrew. These are invisible characters, contain no `<`, and are exactly what `<bdi>` does. The **already-shipped** `checkin.notice` has the same exposure, so the isolate belongs in the shared substitution helper, not in F20's copy. |
| R5 | **No Latin run may be the last thing in a block.** | Follows from R4's *real* case, not its stated one. **Narrowed at review**: the first draft said "or immediately before a block-final period" and claimed every sentence in String 4 had been shaped for it — while String 1 carried «…את הודעות ה-SMS.» un-checked. Rather than keep a constraint that was violated in the deck that imposed it, R5 is now the narrow rule (nothing Latin block-final) and String 1's Latin run was removed outright («המסרונים»). Verified across all ten strings: every block ends in Hebrew. |
| R6 | **Plain text only. No `<` anywhere.** Verified: `'<' in s` is `False` for all ten strings. | Stored XSS with a legal document as the vector. |
| R7 | **Section headings are i18n keys on the page, never lines inside the strings.** | The strings deliberately contain **no** headings. The `/privacy` page gives each of the three documents an `<h2>` from an i18n key (spec, Frontend changes). If headings were baked into the strings they would render as `<p>` — visual headings with no semantics, a WCAG 1.3.1 failure on the twin of the accessibility statement, and a duplicate of the inline block's own heading on the booking form. |
| R8 | **Non-Hebrew characters used, exhaustively** (recomputed, all ten strings): U+2014 EM DASH ×17, U+2022 BULLET ×17, **U+002D HYPHEN-MINUS ×2** (in «חד-פעמי» and «חד-כיווני» only), plus ASCII space, `,` `.` `:` `;` `{` `}` and the Latin runs `SMS`, `MODRYN`, `Railway`, `Twilio`, `Amazon Web Services`, `{{boutique}}`. **No digits anywhere** — the 30-day figure is spelled «שלושים יום», which is the right call under BiDi. | The first draft's list called itself exhaustive and omitted the hyphen-minus, so a character-allowlist test written from R8 would have failed on merge. Bullet is new to this repo — confirm it renders in the storefront's Hebrew display font before merge; if it does not, substitute «–» or drop to prose. |

---

## Byte counts — all ten strings, computed

Cap is `MAX_PRIVACY_TEXT_BYTES = 8 × 1024 = 8192` bytes (applies to the three stored/overridable documents; the i18n values and the manage strings are not stored in `tenants.settings` and are not capped, counted here for completeness).

| String | Characters | **Bytes** | % of 8192 | Capped? |
|---|---:|---:|---:|---|
| `PLATFORM_NOTICE_HE` | 2 100 | **3 746** | 45.7 % | yes |
| ↳ §30A withdrawal sentence (inside the above) | 225 | **402** | 4.9 % | — |
| `PLATFORM_DPA_HE` | 860 | **1 544** | 18.8 % | yes |
| `PLATFORM_SUBPROCESSORS_HE` | 896 | **1 583** | 19.3 % | no (platform-owned) |
| manage disclaimer (5a) | 531 | **956** | 11.7 % | no |
| `reason` hint (5b) | 159 | **286** | 3.5 % | no |
| `checkin.notice` (6) | 658 | **1 169** | 14.3 % | no (i18n) |
| `checkin.optIn` (7) | 116 | **196** | 2.4 % | no (i18n) |
| `booking.marketingOptIn` (8a) | 116 | **196** | 2.4 % | no (i18n) |
| `booking.marketingOptInHint` (8b) | 44 | **79** | 1.0 % | no (i18n) |

Method: `len(s.encode("utf-8"))` on the exact literals above. Hebrew is 2 bytes per character in UTF-8; em dash and bullet are 3 bytes each; ASCII is 1. The largest string uses **45.7 %** of the cap, so a boutique's own lawyer has room to roughly double the notice before hitting it — which is the headroom the 8 KB figure was chosen for.

Mechanical invariants re-verified after the review edits: **no `<` in any of the ten**; String 2 is a literal substring of String 1; Strings 7 and 8a are byte-identical; `PUBLIC_PAGE_CLAUSE` («עמוד אינטרנט ציבורי») is present in String 6; and «עורך דין» / «ייעוץ משפטי» / «נבדק» appear in 5a and in **no** other string, which is what `test_privacy_text.py`'s bidirectional disclaimer assertion checks.

**Payload note**: all three public documents ride the existing `GET /storefront/boutique` response (D13). Combined that is **6 873 bytes** of Hebrew added to every storefront first paint, against a catalog page that ships dress imagery. Worth knowing; not worth a second endpoint.

---

## What this approval does NOT cover

Please read this before approving, because the gap is easy to misread as closed.

1. **This is a DRAFTING approval, not a legal review.** It confirms the Hebrew says what we intend it to say, in language a customer can read, and that every factual claim in it matches the code. It confirms nothing about whether those statements satisfy Israeli law.

2. **The standing counsel review is still open and is not discharged by this document.** `LOOP-STATE.md` carries a `user_actions` entry — *"Get counsel to review the F16 SMS bodies and the F20 privacy default before either goes live"*. That entry stays open after this approval. Spec Risk 1 names the trigger: **before pilot go-live.** This document is the drafting approval that precedes it, exactly as Gate 1 Q1's ruling states.

3. **Five clauses are commitments no code enforces**, and each needs an owner before pilot. The first draft listed three; the review found two more of identical shape:
   - the **30-day** response undertaking (String 1, clause 10) — procedural, must be in `.planning/ppl-compliance-record.md` §2;
   - the **identity-verification** undertaking (String 1, clause 10) — spec line 327 makes this *the boutique's* step, living only in the compliance record. Same dependency as the 30-day clock, and the first draft did not flag it;
   - the **breach-notification** undertaking (String 3, clause 4) — depends on the incident-response procedure existing, `.planning/ppl-compliance-record.md` §3;
   - the **confidentiality-and-security undertaking** asserted of MODRYN (String 3, clause 2) — this states a **contractual fact** about a DPA that `architecture.md:20` places "in ToS". If that ToS clause does not exist at merge, the sentence is false, which is exactly the condition clause 4 was warned about;
   - the **"a new supplier appears in this list before it is used"** promise (String 4, clause 4) — Risk 7 says no CI check can catch a missed amendment. It is a human commitment.

4. **The Railway region is unverified.** String 4 discloses a transfer outside Israel without naming a country, because the runbook documents no region and I would not state one I could not verify. Establishing it — and, if possible, pinning Railway to an EU region — is worth doing before pilot and would improve both the disclosure and the legal position.

5. **Arabic is untranslated.** Per Interview Q3 / pre-decided #47, `ar.ts` takes the Hebrew as placeholder values. The three long documents are data rather than i18n keys, so an Arabic-speaking boutique overrides them per tenant like any other text. ⚠ **Build note the review surfaced**: `i18n-keys.test.ts`'s value-parity guard is scoped to exactly `["checkin.guideTrigger", "checkin.guideHint"]` and does **not** cover `checkin.notice` or `checkin.optIn`. `checkin.notice` is held in both bundles only by the `PUBLIC_PAGE_CLAUSE` substring check; `checkin.optIn` is held by **nothing**. A builder who swaps `he.ts` and forgets `ar.ts` gets a green suite and an Arabic bundle serving un-approved interim consent text. The plan's task E6 now adds the parity assertion for both keys in the same commit.

6. **The three §11 elements I could not verify against code, and took from the statute:** the 30-day figure, the regulator's current name («הרשות להגנת הפרטיות»), and the statutory terms «בעל מאגר»/«מחזיק». These are the rows most worth a lawyer's eye.

7. **A walk-in who has never booked online is invisible to the console's subject-request panel.** Strings 6's §13/§14 sentence is stated because the rights exist in law — but `subject-export` resolves through `CustomersRepository.by_phone`, a customer row is only ever created inside `create_booking`, and F20 declines the queue-ticket→customer promotion (plan DR-10). So for a pure walk-in, "look her up" returns 404 and the owner must serve the request **by hand**. The `phone` arm added by finding F5 covers the §30A marketing withdrawal and nothing else. `.planning/ppl-compliance-record.md` §2 must state the manual procedure, and the plan records it as Risk R-H.

8. **Correction is one-third served.** Spec line 325 is explicit: F15 corrects a **phone**; a **name** is corrected only by making a new booking; `bookings.notes` cannot be corrected **at all** (Risk 4, F53 as the trigger). String 1 clauses 3, 9 and 10 and String 6 all state the right flatly, and the first draft's claim that "every factual claim in it matches the code" did not survive this row. The clause stays — §14 is the law regardless of what the console offers — but the boutique must be able to honour it by hand, and the compliance record §2 must say how.

9. **The platform operator's registered legal entity is not named.** String 3 names **MODRYN**, which is verifiable as the platform's brand (`README.md:3,7`; `*.modryn.co.il`) and is a large improvement on the first draft's unnamed «חברת שירות חיצונית». It is **not** a company registration. §11(b)(4)'s identification expectation reaches the processor, so the registered entity name (and, if it exists, its company number) should replace or accompany the brand before pilot — the same class of gap as the Railway region, and worth closing at the same time.

---

## Findings raised at adversarial review and REJECTED

Recorded because a silently dropped finding is indistinguishable from an oversight to the next reader.

1. **"Cut Strings 6 and 7 from this approval and leave `checkin.notice`/`checkin.optIn` interim until the walk-in promotion has an owner."** *(Offered as option (b) under the F5 blocker.)*

   **Rejected.** It is the only one of the three offered options that leaves a **known-false** sentence live on a public collection point: the interim value's «ונמחקים כמה ימים לאחר הביקור» (finding F4) would ship for another whole feature cycle, and so would the unservable «בכל הודעה» unsubscribe promise. Deferring a swap the shipped code explicitly assigns to F20 — *"F20 replaces both VALUES… and that is the whole swap"* — in order to avoid deciding one clause is trading a certain, live defect for a scheduling convenience. The resolution actually taken (strike the exception clause, add the `phone` arm) costs one `UPDATE` statement and closes both.

2. **"Add `AND marketing_opt_in_at IS NULL` to the `queue_tickets` retention predicate and give opted-in tickets their own longer or unbounded class."** *(Offered as option (a) under the F5 blocker, and described there as "the smallest diff and the only one that does not narrow what she was already told".)*

   **Rejected on the second half of that claim.** It is a small diff, but what it preserves is not a subject protection — it is a promise in the **boutique's** commercial favour to retain her contact detail indefinitely. Taking it literally means an opted-in walk-in's name and phone are held with **no clock at all**, in a store that (per plan DR-10 and R-A) no send path will ever read and that the spec's Out-of-scope guarantees has no consumer in v1. That is the "nothing is ever deleted" the Problem statement opens with, re-created inside the feature that exists to end it — and it would also need a seventh `Settings` key and a second policy for a store with no reader, which is exactly the un-lazy shape D8 declined elsewhere.

   What she is actually entitled to is the **ability to revoke**, and the first draft's design could not serve that at all. The resolution takes the revocation half seriously (the `phone` arm) and drops the retention half, which is the direction that is protective rather than merely faithful to a sentence nobody should have written.

---

## Approval checklist

- [ ] String 1 `PLATFORM_NOTICE_HE` — all 12 clauses, including the six sentences revised at review (opening deixis, purpose limitation, refusal channel, recipients pointer, rights channel, marketing box named to the form)
- [ ] String 2 — the §30A withdrawal sentence, and specifically that it says *ask the boutique* rather than naming a staff role (your Q4 ruling)
- [ ] String 3 `PLATFORM_DPA_HE` — including **naming MODRYN as the processor** (new at review), the narrowed audit-log claim, and the breach-notification clause, which depends on the incident-response procedure existing at merge
- [ ] String 4 `PLATFORM_SUBPROCESSORS_HE` — and the disclosure principle behind it (F2b): **Twilio named conditionally**, no payment processor, Railway outside Israel, AWS holding no data of hers
- [ ] String 5a — the manage disclaimer, and that it appears **only** in the console
- [ ] String 5b — the `reason` hint
- [ ] Strings 6–8 — the check-in and booking-form values the shipped code assigns to F20 (finding F3). **If these are not approved, `/checkin` keeps shipping interim Hebrew containing a false deletion promise (F4) and an unservable marketing exception (F5).**
- [ ] **Finding F5's resolution** — the walk-in marketing exception is struck from `checkin.notice`, and `marketing-withdraw` gains a `phone` arm so the §30A revocation sentence is true for a walk-in. This is a **spec-level change**, applied in the plan (DR-11, C5, R-H), not just a wording edit.
- [ ] The optional clause in String 1 clause 10 — keep or drop the explicit 30-day undertaking
- [ ] Acknowledged: this is drafting approval only; counsel review before pilot go-live remains open, and items 7, 8 and 9 of "does NOT cover" are open gaps with named owners
