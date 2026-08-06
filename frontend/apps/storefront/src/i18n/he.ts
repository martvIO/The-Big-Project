// Hebrew is the only locale in v1. Every visible string on the storefront lives
// here — no component may hardcode Hebrew. Interpolation uses i18next {{name}}
// placeholders.
//
// `hours.days` is a SEVEN-ITEM SUN-FIRST ARRAY feeding HoursTable.dayLabels.
// Read it with t("hours.days", { returnObjects: true }) as string[] — nothing in
// this repo declares CustomTypeOptions resource typing, so a bare t() is typed
// `string` and would fail the blocking `pnpm -r typecheck` CI step.
export const he = {
  translation: {
    // Per-route <title>. Set on every client navigation (WCAG 2.4.2, Level A).
    document: {
      catalog: "הקולקציה",
      dress: "פרטי השמלה",
      about: "על הבוטיק",
      accessibility: "הצהרת נגישות",
      // ONE title for all five booking steps — the flow is one page to the tab
      // strip, and it is the h1 of the two no-step degrade screens as well.
      book: "קביעת תור",
      // The tokenized manage page (F16). One title for all six of its states:
      // she arrived from a text message, and the tab strip is not where an
      // outcome should be announced.
      manageTitle: "התור שלך",
      // The walk-in queue (F33). The position page has ONE title for all of its
      // states and it NEVER carries the ticket id — the id is the capability,
      // and a tab strip is read over a shoulder in a shop.
      checkin: "רישום לתור",
      queuePosition: "מקומך בתור",
      // The wall board (F59). ONE title for every state, carrying no name and no
      // number — the same rule, and a board title is read over a shoulder by
      // more people than any other in the product. Not «התור עכשיו»: «עכשיו» is
      // a liveness claim the poll cannot keep, and a tab title has no freshness
      // line beside it to qualify it.
      queueBoard: "לוח התור",
      // F20's privacy page. WCAG 2.4.2 — the router writes the title on every
      // client navigation, and a statutory document that shares the catalogue's
      // title is one a screen-reader user cannot tell she reached.
      privacy: "הודעת פרטיות",
    },

    catalog: {
      // Shown only before the boutique's own name arrives from /storefront/boutique.
      essenceFallback: "חנות הכלות",
      // Occupies the same slot at the same height as a real price, so a mixed
      // grid never jumps.
      priceOnRequest: "מחיר בתיאום",
      reserved: "הוזמן",
      empty: "הקולקציה בדרך",
      emptyBody:
        "השמלות עולות לאתר בימים הקרובים. בינתיים אפשר לקבוע תור ולראות הכל מקרוב.",
      // The only path to dress 25 of ~60.
      more: "עוד שמלות",
      loading: "טוענת את הקולקציה",
      error: "לא הצלחנו לטעון את הקולקציה כרגע.",
      retry: "נסי שוב",
    },

    dress: {
      back: "חזרה לקולקציה",
      sizes: "מידות",
      available: "זמין",
      // A SIZE-level marker, not the dress-level out-of-stock badge, which the
      // storefront never renders — but "not available" still has to be readable
      // as words, since a dimmed chip alone is colour-only signalling.
      unavailable: "לא זמין",
      more: "עוד",
      less: "פחות",
      share: "שיתוף",
      shareCopied: "הקישור הועתק",
      // An archived dress is a 404 within the tenant — same copy as an unknown id.
      unavailableDress: "השמלה כבר לא זמינה",
      backToCatalog: "חזרה לקולקציה",
      error: "לא הצלחנו לטעון את השמלה כרגע.",
      reserved: "הוזמן",
    },

    about: {
      heading: "על הבוטיק",
      story: "הסיפור שלנו",
      hoursHeading: "שעות פעילות",
      closed: "סגור",
      closedToday: "סגור היום",
      opensTomorrow: "נפתח מחר ב-{{time}}",
      opensOn: "נפתח ביום {{day}} ב-{{time}}",
      today: "היום: {{hours}}",
      // A boutique with no weekly rules at all — the state every new tenant
      // ships in. Never blank, never "undefined", never yesterday's range.
      hoursUnavailable: "שעות הפעילות יתעדכנו בקרוב. אפשר להתקשר ולתאם.",
      exceptionsLabel: "שעות מיוחדות",
      exceptionClosed: "{{date}} סגור",
      exceptionHours: "{{date}} {{open}}–{{close}}",
      contactHeading: "יצירת קשר",
      error: "לא הצלחנו לטעון את פרטי הבוטיק כרגע.",
    },

    hours: {
      // Sun-first, matching the Israeli week and lib/hours.ts day indices.
      days: ["א׳", "ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "שבת"],
      closed: "סגור",
    },

    // The code, never the server's English message, selects one of these.
    errors: {
      tenantNotFound: "הבוטיק הזה לא זמין כרגע.",
      notFound: "הפריט המבוקש לא נמצא.",
      tooManyAttempts: "יותר מדי בקשות. נסי שוב בעוד רגע.",
      validation: "הבקשה לא תקינה.",
      unknown: "אירעה שגיאה בלתי צפויה. נסי שוב.",
      // Booking mid-flow conflicts and dead ends — copy.md §3.7, all APPROVED.
      slotUnavailable:
        "המועד הזה נתפס בינתיים. אלה המועדים הפנויים המעודכנים — אפשר לבחור מועד אחר.",
      termsStale:
        "מדיניות הביטולים התעדכנה בזמן שמילאת את הפרטים. זו הגרסה המעודכנת — נשמח שתקראי ותאשרי אותה שוב.",
      otpInvalid: "הקוד שהוזן אינו נכון. אפשר להקליד אותו שוב, או לבקש קוד חדש.",
      otpExpired: "תוקף הקוד פג. אפשר לבקש קוד חדש.",
      phoneNotVerified:
        "האימות פג תוקף. אפשר לבקש קוד חדש ולהמשיך מכאן — הפרטים שמילאת נשמרו.",
      // One string for both 503 codes — SMS_NOT_CONFIGURED and SMS_UNAVAILABLE.
      smsUnavailable:
        "אימות הטלפון אינו זמין כרגע, ולכן אי אפשר להשלים כאן את קביעת התור. נשמח שתתקשרי אלינו ונקבע יחד מועד.",
      // A spent /otp/send budget. The wait is real, so it offers the phone
      // rather than a retry — which is what tooManyAttempts would say.
      //
      // Attributes NOTHING. OtpService raises OtpThrottledError only on the
      // per-TENANT ceiling and answers a spent personal budget with a silent
      // 204, so "you asked for several codes" accused a bride who asked for one
      // on a busy boutique — while the bride who really spent hers saw "code
      // sent" four more times, falsely. One string covers both faces honestly.
      otpSendBudget:
        "אימות הטלפון עמוס כרגע. אפשר לנסות שוב בעוד זמן מה, ואפשר פשוט להתקשר אלינו ונקבע יחד מועד.",
      // A 429 on POST /bookings. Its own key, not tooManyAttempts: the window
      // is about an hour, so "try again in a moment" would be a lie.
      bookingBudget:
        "ניסית לקבוע כמה תורים בזמן קצר. אפשר לנסות שוב עוד כשעה, ואפשר פשוט להתקשר אלינו ונקבע יחד מועד.",
      // A 409 on confirm-attendance or cancel against an unpaid hold (F19 A2).
      // Its OWN code on the wire rather than a reuse of BOOKING_CANCELLED, and
      // its own string here for the same reason: an unpaid hold is neither
      // cancelled nor standing, and the cancelled copy would tell a bride
      // mid-checkout that her appointment is gone. The manage page suppresses
      // both controls, so this is the belt for a screen that was already open.
      bookingAwaitingPayment: "התור הזה ממתין לתשלום המקדמה, ולכן אי אפשר לעדכן אותו כרגע.",
    },

    gallery: {
      previous: "התמונה הקודמת",
      next: "התמונה הבאה",
      imageOf: "תמונה {{n}} מתוך {{total}}",
    },

    // The /book flow — copy.md rev 3, all 61 rows APPROVED 2026-07-29.
    booking: {
      cta: "קביעת תור למדידה",

      // Step labels. Each is also its step's h1, so they are static strings by
      // design: an h1 built from fetched data has a state where it is missing.
      // stepOtp is named for what the step asks for, not for its /verify slug.
      stepsLabel: "שלבי קביעת התור",
      stepSlot: "מועד",
      stepDetails: "פרטים",
      stepTerms: "מדיניות ביטולים",
      stepOtp: "אימות טלפון",
      // Steps 1–3 advance; step 4 commits, and uses booking.submit.
      continue: "המשך",
      backStep: "חזרה לשלב הקודם",
      backToCatalog: "חזרה לקולקציה",

      typeHeading: "סוג הפגישה",
      // The forward button is never disabled (R7), so the two unfilled groups
      // have to say so themselves. Same shape as sizeRequired.
      typeRequired: "צריך לבחור סוג פגישה כדי להמשיך",
      timeRequired: "צריך לבחור מועד כדי להמשיך",
      // R19: the value leads here, so this key is the lead-less UNIT and the
      // call site renders <bdi dir="ltr">{minutes}</bdi> before it. The RLM the
      // interpolated form carried was an ad-hoc stand-in for that isolation.
      typeDuration: "דקות",
      // A label on a brides-only type, not a lock: the type stays selectable.
      audienceBrides: "פגישת כלה",
      // Sits above a ContactPanel, which is why it carries no phone invitation
      // of its own.
      noTypes: "בשלב זה אין כאן סוגי פגישות לקביעה מקוונת.",
      pickDate: "תאריך",
      pickTime: "שעה",
      // R19 lead; the call site follows it with <bdi>{dress name}</bdi>. A bare
      // bdi, not dir="ltr" — forcing LTR on a Hebrew dress name is itself a
      // bidi defect.
      forDress: "עבור",
      // The VisuallyHidden role="status" while a step's reads are in flight.
      // catalog.loading says "the collection" on a screen that loads times.
      loading: "טוענות את המועדים",
      noSlots:
        "אין מועדים פנויים בתאריך הזה. אפשר לבחור תאריך אחר, ואפשר גם להתקשר ונמצא לך מועד.",
      slotsError: "לא הצלחנו לטעון את המועדים כרגע.",
      // Not an error and not an apology: a deposit appointment is arranged by
      // phone by design.
      depositByPhone:
        "את הפגישה הזאת אנחנו קובעות בטלפון, כדי לסגור יחד גם את המקדמה. נשמח שתתקשרי — זה לוקח רגע.",

      name: "שם מלא",
      nameRequired: "צריך למלא שם כדי שנוכל לרשום את התור.",
      // 80 and 500 mirror MAX_CUSTOMER_NAME_LENGTH and MAX_BOOKING_NOTES_LENGTH.
      nameTooLong: "השם ארוך מדי. עד 80 תווים.",
      phone: "טלפון נייד",
      // The only place the format is taught, so it must match validatePhone.
      phoneHint: "לשליחת קוד אימות חד-פעמי. אפשר להזין עשר ספרות, למשל 0501234567.",
      phoneInvalid: "המספר לא נראה כמו מספר נייד ישראלי. אפשר להזין עשר ספרות שמתחילות ב-05.",
      notes: "משהו שנשמח לדעת מראש",
      notesHint: "לא חובה. למשל: מגיעה עם אמא, צריך שולחן נגיש, או דגם שראית ואהבת.",

      // F20's collection notice, rendered ABOVE the card on the `details`
      // step — the moment she types her name, which is what §11(b) means by
      // «בעת הפנייה». The BODY is not here and may never be: it is
      // `boutique.privacy_notice_text` off the storefront fetch, the SAME
      // string `/privacy` renders, so a boutique that edited her notice
      // cannot end up with two versions of it. These two keys are the block's
      // only chrome.
      collectionNoticeHeading: "המידע שאת מוסרת לנו",
      collectionNoticeLink: "לעמוד הפרטיות המלא",

      // copy.md String 8a. BYTE-IDENTICAL to `checkin.optIn` BY DESIGN — same
      // consent, same channel, same person, and two differently-worded consent
      // labels in one product is how a §30A defence gets argued over.
      //
      // ⚠ Communications Law §30A wants the consent SEPARATE, AFFIRMATIVE,
      // DEFAULT-OFF and UNBUNDLED, and all four are structural here rather
      // than promised: the box lives on `details` and the required terms
      // checkbox lives two steps later on `terms`, nothing in `create_booking`
      // conditions on it, and a NULL `marketing_consent_at` is the absence of
      // consent — there is no boolean whose default a later migration could
      // flip.
      marketingOptIn:
        "אני מאשרת קבלת הודעות SMS מ{{boutique}} על מבצעים, קולקציות חדשות ואירועים. אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת.",
      // The anti-detriment statement, placed where the decision is made and
      // not only in the long notice.
      marketingOptInHint: "לא חובה. קביעת התור אינה תלויה בסימון התיבה.",
      notesTooLong: "ההערה ארוכה מדי. עד 500 תווים.",
      // Serves the name AND the notes field. The cause is almost always a paste
      // out of a word processor, which carries invisible C0 characters the
      // backend refuses — so the string names the paste rather than the byte,
      // which is the only part of it she can see or act on.
      invalidCharacters:
        "יש כאן תו שאי אפשר לשמור. אם הדבקת את הטקסט, אפשר להקליד אותו מחדש.",
      // Rendered INSIDE the unavailable chip's own label, so it becomes part of
      // that radio's accessible name — which is why it is ≤24 characters and
      // why the longer invitation is a separate key under the group.
      sizeUnavailable: "אפשר להזמין במיוחד",
      sizeRequired: "צריך לבחור מידה כדי להמשיך",
      sizeUnavailableNote: "מידה שאינה כרגע בבוטיק אפשר להזמין במיוחד לקראת המדידה.",

      termsHeading: "מדיניות ביטולים",
      // R19 splits both policy numbers mid-sentence: lead + <bdi dir="ltr">
      // value + tail. Same words in the same order as the approved sentences —
      // only the seam moved, because interpolation cannot carry the isolation.
      refundWindow: "ביטול עד",
      refundWindowSuffix: "שעות לפני המועד — ללא חיוב.",
      // Percent OF THE DEPOSIT — the base the manage console already states.
      // The % rides inside the bdi with its number: "50%" is one LTR run.
      forfeit: "ביטול מאוחר יותר, או אי-הגעה — חיוב של",
      forfeitSuffix: "מהמקדמה.",
      acceptTerms: "קראתי את מדיניות הביטולים ואני מסכימה לה.",
      acceptRequired: "כדי להמשיך צריך לאשר את מדיניות הביטולים.",
      noTermsByPhone:
        "קביעת תור מקוונת תיפתח כאן בקרוב. בינתיים נשמח שתתקשרי אלינו ונקבע יחד מועד.",

      // Conditional, never a delivery claim: /storefront/otp/send always answers
      // 204 and reveals nothing.
      otpSent: "שלחנו קוד בן שש ספרות למספר שהזנת. הוא תקף לחמש דקות.",
      otpCode: "קוד האימות",
      // One label for the first send AND the resend — it may not say "again".
      otpResend: "שליחת קוד אימות",
      // No interpolated countdown: Hebrew has no correct singular/dual here
      // without plural resources, and a ticking number reads as urgency.
      otpResendWait: "אפשר לבקש קוד חדש בעוד רגע",
      submit: "אישור וקביעת התור",
      submitting: "קובעות את התור",

      confirmTitle: "התור נקבע",
      // R19 lead, and the highest-risk one in the flow: the boutique's own
      // free-text name lands in the h1 of her only record. Bare <bdi> at the
      // call site, and NO trailing space — the "ב" prefix attaches to the name.
      confirmTitleNamed: "התור נקבע ב",
      // Bare labels, not sentences: the date, time and type beside them are
      // wrapped in <bdi dir="ltr"> at the call site, which interpolation cannot
      // do.
      confirmWhen: "מתי",
      confirmWhat: "מה",
      // R19: value-first and two-valued, so this is the lead-less unit between
      // them. Both values are owner text and take a bare <bdi>.
      confirmDress: "מידה",
      // REWRITTEN at the F16 design gate (booking.md:1823, Interview
      // pre-decided #3). The screen stops claiming to be her ONLY record,
      // because a confirmation SMS now exists — but the save-the-screen nudge
      // STAYS, and may not become a delivery promise in any tense: at F16 ship
      // time no provider is configured so zero confirmations send, and
      // kosher-phone customers never receive one at any time. Dropping the
      // nudge would re-open F-C7's dead end for exactly the people the SMS
      // cannot reach.
      confirmKeepScreen:
        "פרטי התור נשמרו אצלנו, וכדאי בכל זאת לצלם את המסך. אנחנו נחכה לך.",
      // CONDITIONAL, per R14 and copy.md rev 4: /book/confirm is guard-exempt,
      // so a hand-typed URL or a stale bookmark reaches this screen with no
      // booking behind it. It may not assert one it has no evidence for.
      confirmCold: "אם השלמת את קביעת התור, הוא קיים — ואפשר להתקשר ונאשר לך את הפרטים.",

      // --- the deposit hand-off (F19). Five states on one step. -------------
      //
      // ONE static h1 over all five: the poll's answer changes what the page
      // SAYS, and an h1 that changed with it would rewrite the page's own name
      // under a screen reader mid-wait.
      payTitle: "תשלום מקדמה",
      // State A. The automatic redirect fires beside it, and the two keys below
      // are the fallback for a browser that blocks it — on this surface a
      // blocked redirect with no visible link is a dead end on her money.
      payHandoff: "מעבירים אותך לתשלום",
      payManualHint: "אם הדף לא נפתח מעצמו, אפשר לעבור אליו מכאן.",
      // Serves the hand-off AND the decline: it is the SAME hold and the SAME
      // link (D8/D11b), so a second label promising a second attempt would be
      // describing something the product does not do.
      payManualCta: "מעבר לתשלום",
      // State B. Deliberately present-tense and unfinished: the webhook is what
      // makes a payment true, and coming back from the hosted page proves only
      // that she pressed a button.
      payAwaiting: "מאשרים את התשלום",
      // State D. Not "the payment failed" as an accusation, and no sum: the hold
      // already fixed the amount and this screen may not restate it.
      payDeclined: "התשלום לא הושלם",
      payDeclinedBody: "אפשר להשלים את התשלום על אותה קביעת תור ובאותו סכום.",
      // State E. The seat was freed by the sweeper, so the way forward is the
      // ordinary slot picker and NOT the old checkout link.
      payExpired: "הזמן שמור לך פג",
      // The state that gets forgotten: the bounded poll ran out with no terminal
      // answer. It may not say the payment failed — her card may well have been
      // charged — and it must say "do not pay again" before anything else.
      payUnresolved:
        "עדיין לא קיבלנו אישור על התשלום. אין צורך לשלם שוב — נשמח שתתקשרי אלינו ונבדוק יחד.",

      typeGoneRepick: "סוג הפגישה שבחרת כבר אינו זמין. אפשר לבחור סוג אחר מהרשימה המעודכנת.",
      dressGoneGeneric:
        "השמלה שבחרת כבר אינה זמינה. אפשר להמשיך ולקבוע פגישת מדידה רגילה — נשמח למצוא איתך דגמים דומים.",
      sizeGoneRepick: "המידה שבחרת כבר אינה מופיעה ברשימה. אפשר לבחור מידה אחרת מהרשימה המעודכנת.",
      // Replaces the ContactPanel in all four of its branches when the boutique
      // fetch failed. Name-free by construction: that fetch carried the name.
      contactUnavailable:
        "לא הצלחנו לטעון כאן את פרטי הקשר של הבוטיק. אפשר לנסות לרענן את העמוד בעוד רגע.",
    },

    // The tokenized manage page `/b/{token}` — copy.md APPROVED 2026-07-30
    // (Interview Q5, with pre-decided #3/#4/#5 folded in).
    //
    // The facts card deliberately reuses `booking.confirmWhen` /
    // `confirmWhat` / `confirmDress` instead of minting `manage.*` duplicates
    // (design P2): one label, one Hebrew, no drift between the two screens that
    // show the same appointment.
    manage: {
      title: "התור שלך",
      // The VisuallyHidden role="status" while the lookup is in flight (R30):
      // aria-busy on a plain div is announced by neither VoiceOver nor NVDA.
      loading: "טוענות את פרטי התור",

      attendanceCta: "אישור הגעה",
      // Replaces the primary button after confirmation, and is what the status
      // region announces. No exclamation mark (pre-decided #5): the whole
      // storefront bundle contains zero, and one here would be the single string
      // that breaks the product's punctuation register.
      attendanceDone: "ההגעה אושרה. נתראה.",

      // The reveal TRIGGER, not the cancellation. One tap must never cancel a
      // wedding-dress appointment.
      cancelCta: "ביטול התור",
      cancelQuestion: "לבטל את התור?",
      // R19 split: the number is isolated in a <bdi dir="ltr"> between these two,
      // because i18next interpolation cannot carry the isolation a numeral needs.
      cancelPolicyLead: "לפי המדיניות שאישרת, אפשר לבטל עד",
      cancelPolicySuffix: "שעות לפני המועד.",
      // The pre-E4 truth, rendered on BOTH sides of the window (pre-decided #4):
      // every F16-era booking is deposit-free, so a forfeit warning about a
      // deposit that was never taken would be a lie. The in/out-of-window split
      // ships as structure and E4 swaps the out-of-window key.
      cancelConsequenceFree: "לא נגבה תשלום על התור, כך שהביטול אינו כרוך בעלות.",
      // MD3, and the edit F19 cannot merge without. The sentence above becomes
      // FALSE the day a deposit exists — for a bride who has already read it —
      // so this one replaces it on ANY booking that took a deposit, branching on
      // the wire's `deposit_taken` and NOT on status: a confirmed booking paid
      // weeks ago has a deposit too.
      //
      // Neutral by design and INTERIM. The two window-specific sentences — the
      // deposit comes back, the boutique keeps some of it — are the one item
      // parked for the user, because they tell a bride who paid a deposit what she is
      // entitled to be repaid, and no engineer may invent that. This one is true
      // under either answer, names no sum and no window, and becomes a string
      // swap when they land.
      cancelConsequenceDeposit: "המקדמה מטופלת בהתאם למדיניות הביטולים של הבוטיק.",
      // The screen's only `danger` control — the click that destroys.
      cancelConfirm: "אישור הביטול",
      cancelKeep: "השארת התור",

      // An unpaid deposit hold (F19 A2). Its own state beside the cancelled one:
      // the seat IS claimed and the appointment is neither cancelled nor
      // standing, so both actions are absent rather than disabled — the server
      // 409s on either regardless, and there is nothing to word on a control
      // that cannot act. `invalidHint` is reused beneath it: the payload carries
      // no checkout link, so the phone is the whole of the way forward.
      awaitingPayment: "התור שמור עבורך וממתין לתשלום המקדמה.",

      // The cancelled state's line, and what the status region announces. Plain
      // fact, no guilt.
      cancelled: "התור בוטל.",
      // The seat she freed is bookable again, and she is the likeliest person to
      // want it (design P4).
      rebookCta: "קביעת תור חדש",
      // The link still answers after the appointment — an honest "this has
      // passed" beats a dead link for someone re-opening her SMS.
      past: "המועד הזה כבר עבר.",

      // Unknown or rotated token. No blame, no technical words, and never the
      // word "token".
      invalid: "הקישור הזה כבר לא תקף.",
      invalidHint: "לכל שאלה על התור, אפשר להתקשר לבוטיק.",
      // 429 / network / 5xx on the lookup — recoverable and unblaming, the F14
      // honest-throttle shape (finding F-M1). Its own rows rather than borrowing
      // errors.slotsError, whose wording is about times that did not load.
      loadFailed: "לא הצלחנו להציג את פרטי התור כרגע.",
      retry: "ניסיון נוסף",
    },

    // F22's booking-waitlist reveal on the /book slot step. SEVEN keys — the
    // OTP-mechanics rows (phone label, hint, code label, otpSent, every error)
    // are REUSED from `booking.*` (design P1: one label, one Hebrew, no drift),
    // and the privacy-notice line is `boutique.privacy_notice_text` — owner
    // data, never an i18n key. `send`/`sendWait` duplicate the booking resend
    // pair's VALUES by design-table decree: one Hebrew, two keys, so a later
    // rewording of the booking flow cannot silently reword this one.
    //
    // ⚠ The MANAGE app's `waitlist.*` is F58's walk-in queue — an unrelated
    // block one app over (F-W2). Check the import app, not just the key name.
    waitlist: {
      cta: "הצטרפות לרשימת ההמתנה",
      send: "שליחת קוד אימות",
      sendWait: "אפשר לבקש קוד חדש בעוד רגע",
      sending: "שולחות את הקוד",
      join: "אישור והצטרפות לרשימה",
      joining: "רושמות אותך לרשימת ההמתנה",
      // No when-promise: the SMS claim is F23's to make true. No exclamation
      // mark — the register rule.
      confirmed: "נרשמת לרשימת ההמתנה ליום {{date}}. אם יתפנה תור, נשלח לך הודעה.",
    },

    // The walk-in queue (F33) — /checkin and /q/{ticket_id}.
    //
    // ⚠ `notice` and `optIn` are COUNSEL-GATED (spec D13; the in-run gate on F33
    // is open and stays open). The values below are the spec's INTERIM Hebrew,
    // shipped rather than left blank because Amendment 13 requires notice AT THE
    // MOMENT OF COLLECTION and this form is that moment — collecting a name and
    // a phone from a member of the public behind silence is the one thing this
    // feature may not do. F20 replaces both VALUES, here and in ar.ts, and that
    // is the whole swap: no component may hardcode any part of either sentence,
    // and no second copy may exist anywhere.
    //
    // Both interpolate {{boutique}} from the layout's single fetch, and neither
    // may ever render without a name in it — which is why /checkin withholds the
    // entire form while that fetch is loading or has failed.
    checkin: {
      heading: "רישום לתור",
      // The tab-scoped courtesy pointer's link, labelled as what it IS. On a
      // shared phone or a door tablet the slot holds SOMEONE ELSE'S ticket, and
      // "your place in the queue" would hand a stranger a live capability while
      // claiming it was hers.
      lastFromDevice: "הרישום האחרון שנעשה מהמכשיר הזה",

      // F60's disclosure, in the existing `checkin` section rather than a new
      // top-level `guide` one (DL21): both strings render on this page and
      // nowhere else, and `checkin` is already in i18n-keys.test.ts's SECTIONS,
      // so the dotted-literal source scan covers them with no edit to the
      // scanner.
      //
      // ⚠ THE CONTENT FENCE IS POSITIVE AND IT IS LOAD-BEARING ON GATE 1. The
      // hint names THE QUEUE and only the queue: what checking in puts her into,
      // what she gets back, and that a staffer calls her by name. It states no
      // data-handling fact of any kind. `checkin.notice` below is the notice AT
      // THE MOMENT OF COLLECTION and is never behind a disclosure — a collapsed
      // «מה קורה עם הפרטים שלי?» beside a legally-mandated always-visible notice
      // would be a second, unapproved notice at the same collection point.
      //
      // The label is the READER'S QUESTION, not the product's heading: she is
      // standing in a doorway with a phone, deciding whether to fill in a form
      // for strangers. A question mark is fine; only «!» is banned.
      guideTrigger: "מה קורה אחרי הרישום?",
      // Three facts and no fourth. It avoids «שליחה» entirely so nothing here can
      // read as a message going anywhere, and it does NOT mention the public
      // queue board — that is `checkin.notice`'s counsel-gated clause, and
      // repeating it here would be the second notice.
      guideHint:
        "הרישום מכניס אותך לתור ההמתנה של הבוטיק — בסיום נפתח עמוד עם מקומך בתור שאפשר להשאיר פתוח בטלפון, ואשת צוות תקרא לך בשם כשיגיע תורך.",

      name: "שם מלא",
      phone: "טלפון נייד",
      // The only place the format is taught on this surface, so it must keep
      // matching validatePhone — a rejection here happens to a member of the
      // public standing in a doorway.
      phoneHint: "כדי שנוכל לקרוא לך כשיגיע תורך. אפשר להזין עשר ספרות, למשל 0501234567.",
      visitType: "סוג הביקור",
      visitBride: "מדידת כלה",
      visitEvening: "שמלת ערב",
      visitTypeRequired: "צריך לבחור סוג ביקור כדי להמשיך",

      // F20's APPROVED REPLACEMENT (copy.md String 6). No longer interim: this
      // is the counsel deck's text, and the swap the comment below promised has
      // happened. It names the boutique, the purpose, the queue board, the
      // voluntariness and its consequence, the §30A revocation method and the
      // §13/§14 rights.
      //
      // ⚠ TWO PROMISES WERE STRUCK, and neither may come back without the code
      // that would make it true:
      //
      // «ונמחקים כמה ימים לאחר הביקור» — *deleted a few days after the visit*.
      // Nothing in this system is hard-deleted, and F20's retention job ships
      // with `retention_enabled=False` (Gate 1 Q2), so the sentence was an
      // express representation to the public that no code kept. Replaced by
      // «את הפרטים אנחנו שומרות רק כל עוד הם דרושים לניהול התור», which is a
      // purpose limitation: true today, and still true after F21 turns the
      // seven-day scrub on.
      //
      // «אם סימנת אותה, השם ומספר הטלפון יישמרו לצורך זה עד שתבקשי להסיר את
      // ההסכמה» — *if you ticked it, the name and phone are kept until you ask
      // to remove the consent*. F20's `queue_tickets` SCRUB blanks both at seven
      // days REGARDLESS of the box, so the sentence promised the opposite of
      // what the feature does. What replaces it is not a weaker promise but a
      // control that did not exist: `POST /manage/privacy/marketing-withdraw`
      // grew a `phone` arm for exactly the women who have no `customers` row,
      // which is the only reason «אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת» is
      // true here at all.
      //
      // ⚠ THREE §11 ELEMENTS WERE ADDED because the interim value simply had
      // none of them: voluntariness with the consequence of refusing (§11(b)(3)),
      // the §30A revocation method, and the §13/§14 access-correction-deletion
      // rights. The value is 42% longer than the interim one and that is not a
      // regression — a notice cannot be shortened by omitting the law.
      //
      // ⚠ THREE BLANK-LINE-SEPARATED PARAGRAPHS. `CheckinPage` renders this in a
      // `whitespace-pre-line` block; without that class the three collapse into
      // one wall of text (copy.md R1).
      //
      // The board clause and «מספר הטלפון שלך לא מוצג שם» are KEPT VERBATIM —
      // F59 argued both correctly, `PUBLIC_PAGE_CLAUSE` survives, and
      // `i18n-keys.test.ts:132-143` therefore passes unedited.
      //
      // ⚠ THE BOARD CLAUSE IS THE ONE PRIVACY-LAW CHANGE F59 FORCES, and the
      // wording is load-bearing three times over.
      //
      // It names A PUBLIC WEB PAGE, not "a screen in the boutique". The board is
      // served by an anonymous, unauthenticated route on the boutique's own
      // address and refreshed every five seconds, so a notice describing in-shop
      // display would be affirmatively NARROWER than the processing — which at
      // the moment of collection is worse than the current silence, because it
      // becomes an express representation she can rely on.
      //
      // It says THE FIRST WORD OF THE NAME SHE ENTERED, never "her first name
      // and not her surname". The derivation is the first whitespace-delimited
      // token of whatever she typed, and «כהן נועה» is ordinary Israeli
      // form-filling — so the promise the comfortable wording makes is one the
      // code cannot keep.
      //
      // And «הם» became «הפרטים» in the marketing sentence, which is a REQUIRED
      // collateral edit rather than a tidy: the insertion puts «מספר הטלפון
      // שלך» between the subject and its pronoun, so «הם» would read as *the
      // phone number will not be used*.
      //
      // The fifth counsel item F59 left open — what the notice must say about
      // a first name published on a public, unauthenticated web page — is
      // ANSWERED by the second paragraph, which names the page and states that
      // the phone number is not published there. That is drafting, not legal
      // clearance; the question stays open for counsel.
      notice:
        "הפרטים שאת מוסרת כאן נשמרים אצל {{boutique}} לצורך ניהול התור בלבד — לשמור את מקומך ולקרוא לך כשיגיע תורך. מסירתם היא מרצון; בלי שם ובלי מספר נייד לא נוכל לרשום אותך לתור, ותמיד אפשר לפנות לאחת מאיתנו כאן.\n\nמקומך בתור והמילה הראשונה בשם שהזנת מוצגים בלוח התור של הבוטיק — עמוד אינטרנט ציבורי שכל מי שיודע את כתובת האתר של הבוטיק יכול לפתוח, ולא רק מסך שנמצא בתוך החנות. מספר הטלפון שלך לא מוצג שם.\n\nהפרטים לא ישמשו לפניות שיווקיות אלא אם סימנת את התיבה שלמטה, ואפשר לבקש מאיתנו להסיר את ההסכמה בכל עת. את הפרטים אנחנו שומרות רק כל עוד הם דרושים לניהול התור, ואפשר לבקש מאיתנו לעיין במידע שנשמר עלייך, לתקן אותו או למחוק אותו. פירוט מלא בעמוד הפרטיות של האתר.",
      // F20's APPROVED REPLACEMENT (copy.md String 7). BYTE-IDENTICAL to
      // `booking.marketingOptIn` BY DESIGN: it is the same consent, to the
      // same channel, from the same person, and two differently-worded consent
      // labels in one product is how a §30A defence gets argued over.
      //
      // ⚠ «אפשר להסיר את ההסכמה בכל הודעה» IS GONE. The in-message unsubscribe
      // is F46's and does not exist, so the interim label promised a path that
      // is not built. «אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת» is true only
      // because of the `phone` arm on `marketing-withdraw`; when F46 ships, the
      // in-message clause can come back and it will be true.
      //
      // ⚠ «אני מאשרת ש{{boutique}} תשלח לי…» → «אני מאשרת קבלת הודעות SMS
      // מ{{boutique}}…». `תשלח` is feminine singular and forced that agreement
      // on an ARBITRARY boutique name — «סטודיו כלות», «מרכז השמלות» and any
      // Latin-script name all break it. The nominalised form takes no verb
      // agreement on the name at all, and drops the «ש»+name juncture that was
      // the hardest place in the deck to thread a bidi isolate.
      optIn:
        "אני מאשרת קבלת הודעות SMS מ{{boutique}} על מבצעים, קולקציות חדשות ואירועים. אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת.",

      submit: "הצטרפות לתור",
      submitting: "רושמות אותך לתור",
      // A spent create budget. Names NO duration — the shared 429 body carries
      // none and F33 adds no Retry-After — and never auto-retries.
      budgetSpent:
        "יש כרגע הרבה רישומים לתור. אפשר לנסות שוב בעוד זמן מה, ואפשר פשוט לפנות אלינו כאן בבוטיק.",
      createFailed: "לא הצלחנו לרשום אותך לתור כרגע.",
      // The two arms that WITHHOLD the form. Degrading to a nameless notice is
      // the one failure mode that decision exists to prevent.
      boutiqueUnavailable: "לא הצלחנו לטעון את פרטי הבוטיק כרגע.",
      loading: "טוענות את פרטי הבוטיק",

      // /q/{ticket_id}
      positionLoading: "טוענות את מקומך בתור",
      positionLabel: "מקומך בתור",
      statusWaiting: "ממתינה",
      statusInService: "התור שלך התחיל",
      // called_at set: the most valuable thing this screen can say, and the only
      // reason called_at is read in F33 at all.
      called: "אפשר לגשת לדלפק",
      closed: "הביקור הזה הסתיים.",
      backToCheckin: "רישום לתור חדש",
      // An unknown, swept or mistyped ticket. No blame, no technical words.
      notFound: "הקישור הזה כבר לא תקף.",
      notFoundHint: "אפשר להירשם לתור מחדש, ואפשר פשוט לפנות אלינו כאן בבוטיק.",
      loadFailed: "לא הצלחנו להציג את מקומך בתור כרגע.",
      retry: "ניסיון נוסף",

      // SC 2.2.2 (Level A), which axe has no rule for: ONE button whose
      // accessible NAME flips. No aria-pressed, and deliberately no aria-label
      // variant — an aria-label would override the visible text and break the
      // rule that the name IS the label.
      pause: "השהיית העדכון",
      resume: "חידוש העדכון",
      // Announced through the one role="status" region, because a screen reader
      // does not reliably re-announce the name of an already-focused control
      // that renamed itself under the press. User-initiated, so D12 admits them.
      pausedCue: "העדכון האוטומטי הושהה",
      resumedCue: "העדכון האוטומטי חודש",
      // Three freshness states that read differently AS TEXT — a class-only
      // difference is exactly the colour-alone defect this is meant to catch.
      // All past tense: «עודכן 14:07» says this was true at 14:07, never
      // «בזמן אמת», which a poll cannot keep even for one interval. Each is a
      // lead; the call site follows it with the time in its own <bdi dir="ltr">.
      updatedAt: "עודכן",
      staleAt: "העדכון האחרון היה",
      pausedAt: "העדכון מושהה. עודכן",
    },

    // F59's wall board, /queue. EIGHT keys and no more: the freshness leads, the
    // pause pair, the two cues and the retry label all RESOLVE from checkin.*
    // above rather than being re-declared here. The two screens hang in the same
    // shop and their vocabulary must not diverge — and a second spelling of
    // «השהיית העדכון» is a second string to keep right forever.
    //
    // Read on a television from three to five metres by a room of strangers, so
    // every string states and none reassures. Nothing here claims the board is
    // live: it polls, and «בזמן אמת» is a claim it cannot keep for one interval.
    queueBoard: {
      // The page's single h1, and a fact that stays true before AND after F58
      // starts stamping called_at. Not «הבאות בתור», which implies an order of
      // service the product cannot promise while every row is `waiting`.
      heading: "ממתינות בתור",
      // The state the screen is in for most of the day. A fact, not a fault:
      // «אין מה להציג» describes the software and «התור ריק» reads as a fault on
      // a wall in a shop with customers in it. «כרגע» is qualified by the
      // freshness line beside it, which is why the empty state renders one —
      // without it an empty board is indistinguishable from a crashed board.
      empty: "אין כרגע ממתינות",
      // The one genuinely useful thing an empty board can say. It names no
      // physical location: the QR sign is a printed artefact the boutique places
      // wherever it likes, so «בכניסה» would be a claim about the world.
      emptyHint: "אפשר להצטרף לתור בסריקת הקוד שבבוטיק.",
      // Rendered only when waiting_total exceeds the rows on screen, with the
      // count COMPUTED as the difference and never echoed.
      //
      // «בתור» rather than «ממתינות», for two independent reasons. Grammar: the
      // count is 1 the moment a sixth ticket exists, «ועוד 1 ממתינות» needs the
      // singular, and «בתור» is a prepositional phrase that does not inflect for
      // number — so every value is grammatical without four Hebrew plural forms.
      // Truth: under F33's Ruling 3 one woman can hold two tickets, so the
      // quantity counts PLACES rather than women, which is exactly what
      // waiting_total is. The product cannot count women without a read keyed on
      // phone, and the queue repository forbids one by design.
      //
      // No <bdi> around the count and none needed: a digit run between two
      // Hebrew runs resolves as it should with no isolation, and the storefront
      // ships no isolateLtr helper to reach for.
      overflow: "ועוד {{count}} בתור",
      // Beside the name on a called row — THE WORD that keeps the highlight out
      // of SC 1.4.1, because a background alone is invisible to a woman with a
      // colour-vision difference sitting four metres away, which is the entire
      // audience. Its own key rather than a reuse of checkin.called
      // («אפשר לגשת לדלפק»): that string is permission granted to the holder on
      // her own phone, and at this size it is roughly 590px of type in a row
      // that fits about nine characters.
      //
      // ⚠ Unreachable until F58 ships — nothing in the product writes called_at
      // — so it renders only against a stubbed API client.
      called: "גשי לדלפק",
      // The first load only; the region carrying it unmounts on the first
      // settled response. Feminine plural, matching the two shipped storefront
      // loading strings it sits beside.
      loading: "טוענות את לוח התור",
      // The first request failed and nothing ever loaded. At the name scale,
      // because the room must be able to tell a broken board from an empty one:
      // a blank screen reads as «אין ממתינות» and a woman acts on it. The loop
      // keeps running underneath, so nothing here promises a retry.
      loadFailed: "לא הצלחנו להציג את לוח התור כרגע.",
    },

    contact: {
      call: "חיוג",
      whatsapp: "וואטסאפ",
      waze: "ניווט ב-Waze",
      maps: "פתיחה ב-Google Maps",
      instagram: "אינסטגרם",
    },

    footer: {
      contactHeading: "יצירת קשר",
      about: "על הבוטיק",
      // F20. The footer is a sibling of <main> in StorefrontLayout, so this one
      // link puts the notice one tap from the catalogue, a dress page,
      // /b/{token}, /checkin and /q/{id} alike — every route renders inside this
      // shell. §11 wants the document reachable, not merely published.
      privacy: "הודעת פרטיות",
    },

    a11y: {
      skipLink: "דלג לתוכן",
      statementLink: "הצהרת נגישות",
      menuTrigger: "תפריט נגישות",
      contrast: "ניגודיות גבוהה",
      textSize: "הגדלת טקסט",
      readableFont: "גופן קריא",
      underlineLinks: "הדגשת קישורים",
      stopMotion: "עצירת אנימציות",
    },

    // הצהרת נגישות — the /accessibility page. IS 5568 §35 makes this page and a
    // named, reachable contact inside it a legal obligation, not a nicety.
    //
    // The responsible party is THE BOUTIQUE: it is the service provider, and its
    // own phone and Instagram come from the layout-level getBoutique(). There is
    // deliberately no platform-operator coordinator layer — the spec's design
    // gate names the boutique, and a statement that declares conformance while
    // showing «fill this in» is itself the non-conformance it declares against.
    statement: {
      title: "הצהרת נגישות",
      intro:
        "אנחנו מאמינות שכל אחת ואחד צריכים להיות מסוגלים לגלוש כאן, לראות את השמלות ולקבוע תור — בלי מחסומים. השקענו מאמץ כדי שהאתר יהיה נגיש, ואנחנו ממשיכות לשפר אותו.",

      conformanceHeading: "רמת הנגישות של האתר",
      conformanceBody:
        "האתר נבנה בהתאם לתקן הישראלי ת״י 5568 ברמת AA, המבוסס על הנחיות WCAG 2.0 של ארגון התקינה W3C.",

      doneHeading: "מה עשינו כדי להנגיש את האתר",
      doneFonts:
        "הגופנים העבריים מתארחים בשרת שלנו ואינם נטענים משירות חיצוני, כדי שהטקסט יופיע מיד ובצורה קריאה גם בחיבור איטי.",
      doneKeyboard:
        "אפשר להפעיל את כל האתר במקלדת בלבד. סדר המעבר בין הרכיבים תואם לסדר שרואים על המסך, ולכל רכיב פעיל יש סימון מיקוד ברור. בראש כל עמוד יש קישור דילוג ישירות אל התוכן.",
      doneContrast:
        "כל צירופי הצבעים באתר נבדקו ועומדים ביחס ניגודיות של 4.5:1 לפחות בטקסט רגיל.",
      doneRtl:
        "האתר כולו בעברית ובכיוון מימין לשמאל, כולל האזורים שמכילים ספרות, מספרי טלפון וכתובות אינטרנט באנגלית.",
      doneImages:
        "לכל תצלום שמלה יש טקסט חלופי, וקישוטים גרפיים מוסתרים מקוראי מסך כדי לא להעמיס.",
      doneMenu:
        "באתר תפריט נגישות משלנו — לא הרחבה חיצונית — הזמין בכל עמוד בפינה התחתונה.",

      menuHeading: "מה עושה כל אפשרות בתפריט הנגישות",
      menuContrast: "ניגודיות גבוהה — מחזקת את הניגוד בין הטקסט לרקע.",
      menuTextSize: "הגדלת טקסט — מגדילה את כל הטקסטים באתר.",
      menuReadableFont: "גופן קריא — מחליף את הגופן העיצובי בגופן פשוט וברור יותר.",
      menuUnderlineLinks: "הדגשת קישורים — מוסיפה קו תחתון לכל הקישורים כדי שיבלטו בתוך הטקסט.",
      menuStopMotion: "עצירת אנימציות — מבטלת מעברים ותנועה באתר.",
      menuNote:
        "ההעדפות חלות על הגלישה הנוכחית בלבד ואינן נשמרות במכשיר, מפני שאיננו שומרים מידע על הגולשים.",

      limitsHeading: "מגבלות שאנחנו מודעות להן",
      limitsZoom:
        "בשלב זה אין באתר אפשרות להגדלת תצלומי שמלות. אפשר להיעזר בהגדלת התצוגה של הדפדפן.",
      // Must keep describing what the site ACTUALLY does: the card alt is the
      // dress name, and the dress page's main photo announces its position in
      // the gallery, not the garment. A statement that misdescribes the site is
      // itself a non-conformance.
      limitsAlt:
        "בעמוד הקולקציה הטקסט החלופי של כל תצלום הוא שם השמלה בלבד, ואינו מתאר את הגזרה, הבד או הפרטים. בעמוד השמלה התצלומים מוקראים לפי מיקומם בגלריה, למשל: תמונה 1 מתוך 3, ושם השמלה מופיע בכותרת העמוד. נשמח לתאר כל שמלה בטלפון.",
      limitsNote: "אנחנו פועלות לתקן את המגבלות האלה בגרסאות הבאות של האתר.",

      coordinatorHeading: "פניות בנושא נגישות",
      coordinatorIntro: "לכל פנייה בנושא נגישות אפשר ליצור קשר ישירות עם הבוטיק:",
      coordinatorPhoneLabel: "טלפון",
      coordinatorInstagramLabel: "אינסטגרם",
      // A tenant that published neither a phone nor an Instagram — and any
      // tenant whose boutique fetch failed. §35 wants a reachable channel, so
      // the statement says plainly that none is published here and sends the
      // visitor to the boutique itself, instead of an empty contact list.
      coordinatorNoChannel:
        "בשלב זה לא פורסמו כאן מספר טלפון או חשבון אינסטגרם. אפשר לפנות בנושא נגישות ישירות אל {{name}}, בבוטיק עצמו, וכל פנייה תטופל.",

      reportHeading: "נתקלתם בבעיית נגישות?",
      reportBody:
        "אם משהו כאן לא עבד עבורכם, נשמח שתספרו לנו — עם תיאור הבעיה, כתובת העמוד וסוג המכשיר או הדפדפן שבו גלשתם. אנחנו מתחייבות לחזור אליכם ולטפל בפנייה.",

      updated: "עודכן לאחרונה: 28.7.2026",
    },

    // F20's /privacy page. ⚠ THE DOCUMENTS ARE NOT HERE AND MAY NEVER BE. All
    // three bodies ride `GET /storefront/boutique` — `privacy_notice_text` is
    // the boutique's own, overridable through the console, and
    // `privacy_subprocessors_text` is platform-owned and structurally
    // un-overridable (D14). A copy of any of them in this bundle would be a
    // second place for a legal string to drift, which is the failure F33's
    // `checkin.notice` comment already names.
    //
    // What lives here is the page's CHROME, and copy.md R7 is why it has to:
    // the strings deliberately contain no headings, so each document gets an
    // <h2> from a key. Baked into the strings they would render as <p> — visual
    // headings with no semantics, a WCAG 1.3.1 failure on the twin of the
    // accessibility statement.
    privacy: {
      title: "הודעת פרטיות",
      noticeHeading: "המידע שאנחנו אוספות ומה אנחנו עושות בו",
      dpaHeading: "מי מעבד את המידע ואיך הוא נשמר",
      // The list beneath the DPA clause, which points at it («ספקי התשתית
      // שרשומים בהמשך») — so this section must render AFTER that one.
      subprocessorsHeading: "ספקי התשתית",
      updated: "עודכן לאחרונה: 4.8.2026",
    },
  },
} as const;
