// Hebrew is the only locale in v1. Section copy is extracted into this catalog
// per component as the F9 console restyle touches it.
export const he = {
  translation: {
    document: {
      title: "MODRYN — ניהול הבוטיק",
    },
    console: {
      title: "MODRYN — ניהול הבוטיק",
      logout: "יציאה",
      skipLink: "דלג לתוכן",
      loading: "טוען…",
    },
    nav: {
      profile: "פרופיל והגדרות",
      hours: "שעות פעילות",
      types: "סוגי תורים",
      terms: "מדיניות ביטולים",
      catalog: "שמלות",
    },
    common: {
      loading: "טוען…",
      saved: "נשמר לפני רגע",
    },
    login: {
      title: "MODRYN — כניסה לניהול הבוטיק",
      email: "אימייל",
      password: "סיסמה",
      submit: "כניסה",
    },
    profile: {
      heading: "פרופיל הבוטיק",
      publicNotice: "השדות האלה מופיעים בדף הפומבי של הבוטיק",
      essence: "משפט פתיחה",
      phone: "טלפון",
      address: "כתובת",
      mapsUrl: "קישור למפות (http/https)",
      instagram: "אינסטגרם",
      instagramHint: "שם המשתמש בלבד, ללא @",
      description: "תיאור",
      settingsHeading: "הגדרות",
      depositsEnabled: "גביית מקדמות מופעלת",
      bridesOnly: "בוטיק לכלות בלבד",
      bridesOnlyHint: "כל סוגי התורים יוצגו לכלות בלבד",
      save: "שמירת פרופיל והגדרות",
    },

    // --- F15 owner bookings ---
    //
    // Transcribed row-for-row from .planning/design/screens/owner-bookings/copy.md
    // as DOTTED LITERAL keys, so the deck and this block diff against each other
    // line by line. i18next resolves them through `ignoreJSONStructure` (default
    // true), which falls back to a flat lookup when the nested path misses —
    // __tests__/i18n.test.ts proves every one of them resolves.
    //
    // Two rules from the deck's §0 are mechanical, and that same suite enforces
    // them: no exclamation mark, and no string that claims, promises or hedges
    // that an SMS went out. `_deliver` swallows both send errors, so the platform
    // has no evidence a message was delivered; every string states the state
    // change and stops. `booking.deliveryNotice` says the limit out loud, once.
    "nav.bookings": "תורים",
    "booking.heading": "תורים",

    // The day list.
    "booking.dateLabel": "תאריך",
    "booking.listLoading": "טוען תורים…",
    // Label-then-number, so it is grammatical at every count without four
    // Hebrew plural forms. {{count}} renders inside <bdi dir="ltr">.
    "booking.dayCount": "תורים ביום זה: {{count}}",
    "booking.loadFailed": "לא הצלחנו לטעון את התורים כרגע.",
    "booking.emptyDayTitle": "אין תורים בתאריך הזה",
    "booking.emptyDayBody": "אפשר לבחור תאריך אחר.",
    "booking.attendanceConfirmed": "אישרה הגעה",

    // Status — the word inside the Badge carries the state, never colour alone.
    "booking.statusConfirmed": "מאושר",
    "booking.statusCompleted": "התקיים",
    "booking.statusNoShow": "לא הגיעה",
    "booking.statusCancelled": "בוטל",
    // F19 D14: the fifth status. Without it the badge Map's fallback rendered
    // the literal LTR «pending_payment» inside this RTL console.
    "booking.statusPendingPayment": "ממתין לתשלום",
    // The fallback itself, now that it can only mean a status this build has
    // never heard of. Hebrew, so a future sixth value degrades into a chip the
    // owner can read rather than a wire token she cannot.
    "booking.statusOther": "מצב לא מוכר",

    // F19 D18 — the ONLY owner-facing payment surface in the product. All seven
    // values of 0012's CHECK carry a label, not just the four F19 writes.
    "booking.payment": "תשלום",
    "booking.paymentPending": "בהמתנה",
    "booking.paymentPaid": "שולם",
    "booking.paymentFailed": "נכשל",
    "booking.paymentExpired": "פג תוקף",
    "booking.paymentRefundDue": "זיכוי לביצוע",
    "booking.paymentRefunded": "זוכה",
    "booking.paymentForfeited": "חולט",
    "booking.paymentOther": "מצב תשלום לא מוכר",
    // A1/D16: computed by the server, never stored, rendered through <Price>.
    "booking.refundDue": "סכום להחזר",
    // The two combinations that need a human. Both open with «דרושה פעולה» so
    // the marker never depends on colour to be read.
    "booking.paymentActionCancelledPaid":
      "דרושה פעולה: התור בוטל והפיקדון עדיין מוחזק בבוטיק.",
    "booking.paymentActionNoDeposit":
      "דרושה פעולה: התור נקבע ללא פיקדון, משום שספק הסליקה לא היה זמין בעת ההזמנה.",

    // The detail — chrome and facts.
    "booking.back": "חזרה לרשימה",
    "booking.detailTitle": "פרטי התור",
    "booking.detailLoading": "טוען את פרטי התור…",
    "booking.notFound": "התור הזה לא נמצא.",
    "booking.customerHeading": "הלקוחה",
    "booking.customerName": "שם",
    "booking.customerPhone": "טלפון",
    "booking.appointmentHeading": "הפגישה",
    "booking.when": "מועד",
    "booking.type": "סוג הפגישה",
    "booking.dress": "שמלה",
    "booking.dressSize": "מידה",
    "booking.seat": "עמדה",
    "booking.createdAt": "נקבע בתאריך",
    "booking.terms": "מדיניות שאושרה",
    "booking.termsVersion": "גרסה {{version}}",
    "booking.manageLink": "קישור ניהול",
    "booking.manageLinkIssued": "קישור ניהול פעיל",
    "booking.manageLinkMissing": "לא הונפק קישור ניהול",
    // F34's one addition to this namespace: the arrival FACT's label on the
    // detail. The board's copy deck covers the board screen and carries no key
    // for this row, so the wording follows the deck's own «נרשמה הגעה» — a
    // record that was made — rather than inventing a third spelling.
    "booking.checkedInAt": "נרשמה הגעה",
    "booking.cancelledAt": "בוטל בתאריך",
    "booking.cancelledBy": "בוטל על ידי",
    "booking.cancelledByOwner": "הבוטיק",
    "booking.cancelledByCustomer": "הלקוחה",
    "booking.notesHeading": "הערות הלקוחה",
    "booking.notesEmpty": "הלקוחה לא הוסיפה הערות.",

    // Actions — the group heading, the standing limit, the cancelled dead end.
    "booking.actionsHeading": "פעולות",
    "booking.deliveryNotice":
      "אין באפשרותנו לאמת שהודעות נמסרו ללקוחה. אם חשוב לוודא, אפשר להתקשר אליה.",
    // Survives on every cancelled booking with NO deposit held. On the one row
    // where a deposit IS held it is false the day MD1 merges, and
    // `booking.cancelledPaidActions` below takes its place there.
    "booking.cancelledNoActions":
      "תור שבוטל אינו ניתן לשחזור. לקביעת מועד חדש, הלקוחה מזמינה מחדש דרך אתר הבוטיק.",
    // F19 MD1. The row the sentence above would lie about: her money is here and
    // her time is gone, and the owner can give her a new one.
    "booking.cancelledPaidActions":
      "התור בוטל והפיקדון עדיין מוחזק בבוטיק. אפשר לקבוע ללקוחה מועד חדש, והתור יחזור לסטטוס מאושר.",
    // F19 D14 — the sixth branch. No owner action exists here: every one of them
    // answers 409 on an unpaid hold, and the seat frees itself on the sweeper's
    // clock, so the honest screen offers nothing and says why.
    "booking.awaitingPaymentNoActions":
      "התור ממתין לתשלום הפיקדון. עד להשלמת התשלום אין פעולות זמינות, ואם התשלום לא יושלם המועד יתפנה מעצמו.",

    // Cancel — the only irreversible act.
    "booking.cancelCta": "ביטול התור",
    "booking.cancelModalTitle": "לבטל את התור?",
    "booking.cancelModalBody":
      "הביטול סופי ואי אפשר לשחזר אותו. המועד יתפנה להזמנה, ולקביעת מועד חדש הלקוחה מזמינה מחדש דרך אתר הבוטיק.",
    "booking.cancelConfirm": "אישור הביטול",
    // Shared dismiss for both confirm Modals. Deliberately not «ביטול» — a
    // cancel button on a cancellation dialog is the worst word in the deck.
    "booking.modalKeep": "חזרה",
    "booking.cancelDone": "התור בוטל.",

    // Attendance outcomes — no SMS exists for these and none is added (D13),
    // so none of these strings mentions the customer being told.
    "booking.noShowCta": "סימון: לא הגיעה",
    "booking.noShowDone": "התור סומן: לא הגיעה.",
    "booking.completeCta": "סימון: התקיים",
    "booking.completeDone": "התור סומן: התקיים.",
    "booking.reopenCta": "החזרה לסטטוס מאושר",
    "booking.reopenDone": "הסטטוס הוחזר למאושר.",

    // Reschedule.
    "booking.rescheduleCta": "שינוי מועד",
    "booking.rescheduleTitle": "שינוי מועד התור",
    "booking.rescheduleCurrent": "המועד הנוכחי:",
    // Says the link will point at the new time; deliberately does NOT say the
    // old link dies, because reschedule only rotates the token when no pending
    // reminder exists to inherit from (D11).
    "booking.rescheduleConsequence": "המועד יתעדכן, והקישור של הלקוחה יצביע על המועד החדש.",
    // F19 MD1: on a cancelled booking the same click ALSO un-cancels, and an
    // owner must be told she is un-cancelling before she taps.
    "booking.rescheduleConsequenceRestore":
      "המועד יתעדכן, התור יחזור לסטטוס מאושר, והקישור של הלקוחה יצביע על המועד החדש.",
    "booking.rescheduleRestoreCta": "קביעת מועד חדש ושחזור התור",
    "booking.rescheduleConfirm": "עדכון המועד",
    "booking.rescheduleDone": "המועד עודכן.",
    // MD1: one sentence for both restores — with a new time and with the
    // same one — because it names what changed (the status) and where the
    // booking landed, and is true either way.
    "booking.rescheduleRestoreDone": "התור הוחזר לסטטוס מאושר במועד שנבחר.",
    // The dialog's slot-read failure REPLACES the picker, and the picker owns
    // the date control that would otherwise refetch — so this branch needs its
    // own way out. The list's own outage does not: its date control is above
    // the alert and stays mounted.
    "booking.retry": "ניסיון נוסף",
    "booking.pickDate": "תאריך",
    "booking.pickTime": "שעה",
    "booking.noSlots":
      "אין מועדים פנויים בתאריך הזה. אפשר לבחור תאריך אחר, או לפתוח שעות נוספות במסך «שעות פעילות».",

    // Resend is a ROTATION, and the Hebrew says the old link stops working (D9).
    "booking.resendCta": "הנפקת קישור ניהול חדש",
    "booking.resendHint": "הנפקת קישור חדש מבטלת את הקישור הקודם של הלקוחה.",
    "booking.resendDone": "הונפק קישור חדש. הקישור הקודם בוטל.",

    // Phone correction — owner-attested, and the copy never claims the number
    // was verified (D8).
    "booking.phoneEditCta": "תיקון מספר הטלפון",
    "booking.phoneFieldLabel": "מספר טלפון חדש",
    "booking.phoneEditCancel": "ביטול העריכה",
    "booking.phoneSaveCta": "שמירת המספר",
    "booking.phoneModalTitle": "לעדכן את מספר הטלפון?",
    // {{phone}} echoes the number AS TYPED, inside <bdi dir="ltr">, so the Modal
    // is a proofreading step.
    "booking.phoneModalBody":
      "המספר שהוזן: {{phone}}. המערכת אינה מאמתת שהמספר שייך ללקוחה — העדכון נרשם על אחריות הבוטיק. הקישור הקיים של הלקוחה יפסיק לעבוד, ובמקומו יונפק קישור חדש.",
    "booking.phoneModalConfirm": "עדכון המספר",
    "booking.phoneDone": "מספר הטלפון עודכן. הקישור הקודם בוטל.",

    // The four error codes F15 owns. NOT a client-side validator and mirroring
    // no server bound — a code→string map, pinned by SPEC_ERROR_CODES in
    // test_booking_owner_api.py. Every other code, VALIDATION_ERROR included,
    // falls through to errorMessage(error) and shows the server's own text.
    "booking.error.BOOKING_TRANSITION_INVALID":
      "לא ניתן לבצע את הפעולה במצב הנוכחי של התור. כדאי לחזור לרשימה ולפתוח את התור מחדש.",
    "booking.error.SLOT_UNAVAILABLE": "המועד הזה נתפס הרגע. אפשר לבחור מועד אחר.",
    "booking.error.CUSTOMER_ALREADY_BOOKED": "ללקוחה כבר יש תור פעיל במועד הזה.",
    "booking.error.TOO_MANY_ATTEMPTS": "בוצעו יותר מדי פעולות בזמן קצר. כדאי להמתין מעט ולנסות שוב.",
    // --- F51 owner-only staff section ---
    //
    // Transcribed row-for-row from .planning/design/screens/manage-staff/copy.md
    // as DOTTED LITERAL keys, so the deck and this block diff against each other
    // line by line. __tests__/i18n.test.ts proves every one of them resolves and
    // enforces the deck's two mechanical rules — no exclamation mark, and no
    // string that claims, implies or hedges that anything was sent.
    //
    // That second rule is not inherited boilerplate here: there is NO channel.
    // No mailer exists anywhere in Backend/app, app/notifications is SMS-only
    // with no registered sender ID, and SMC ruling 1 removed SMS from the staff
    // auth path. So the owner types the password and tells the staffer what it
    // is, and `staff.passwordNotice` says exactly that — phrased «יש למסור…»
    // rather than «אינה נשלחת…» because the latter contains נשלח and would trip
    // the guard, and copy that has to dodge its own guard is one edit from lying.
    "nav.staff": "צוות",
    "staff.heading": "צוות",
    "staff.loadFailed": "לא הצלחנו לטעון את רשימת הצוות כרגע.",
    // The WORD carries the role; the Badge's colour never does.
    "staff.roleOwner": "בעלת הבוטיק",
    "staff.roleShiftManager": "אחראית משמרת",
    "staff.selfMarker": "זו את",
    "staff.editCta": "עריכה",
    // «השבתה», never «מחיקה»: the row is soft-deleted and its audit trail lives.
    "staff.deactivateCta": "השבתה",
    // ⚠ ADDED LATE, and their absence was the defect: both row controls had a
    // null aria-label, so seven staff rendered seven identical «עריכה» and six
    // identical «השבתה» in one list — one of which ends a colleague's access.
    // The «{action} — {name}» shape is the console's own, copied from
    // `atelier.editAria` / `floor.breakStartAria` / `rooms.releaseAria` rather
    // than invented, and WCAG 2.5.3 is why the visible word comes FIRST: speech
    // input has to be able to say what it reads.
    //
    // No bidi treatment — an aria-label takes no markup, the same exemption the
    // atelier and floor arias record.
    "staff.editAria": "עריכה — {{name}}",
    "staff.deactivateAria": "השבתה — {{name}}",
    "staff.displayNameLabel": "שם לתצוגה",
    "staff.emailLabel": "אימייל",
    "staff.roleLabel": "תפקיד",
    "staff.newPasswordLabel": "סיסמה חדשה",
    "staff.newPasswordHelp": "אפשר להשאיר ריק כדי לא לשנות את הסיסמה.",
    "staff.currentPasswordLabel": "הסיסמה הנוכחית שלך",
    "staff.currentPasswordHelp": "נדרשת כדי לשנות את הסיסמה של עצמך.",
    // Plan C6: the server answers this one 400 with an English VALIDATION_ERROR
    // message, so the field renders its own Hebrew instead of the code map.
    "staff.currentPasswordWrong":
      "הסיסמה הנוכחית שגויה. יש להזין את הסיסמה הנוכחית כדי לשנות אותה.",
    "staff.saveCta": "שמירה",
    "staff.cancelCta": "ביטול",
    "staff.createHeading": "הוספת אשת צוות",
    "staff.passwordLabel": "סיסמה",
    "staff.passwordNotice": "יש למסור את הסיסמה לעובדת בעצמך. המערכת אינה מעבירה אותה לאיש.",
    "staff.createCta": "הוספה לצוות",
    "staff.deactivateTitle": "להשבית את הגישה?",
    // The <bdi> is load-bearing, not markup for its own sake: the name is a
    // Latin run inside an RTL sentence and reorders without an isolate.
    // Rendered through <Trans components={{ bdi: <bdi /> }}>.
    "staff.deactivateBody":
      "הגישה של <bdi>{{name}}</bdi> לניהול הבוטיק תיפסק בפעולה הבאה שלה. אפשר להוסיף אותה מחדש בכל עת.",
    "staff.deactivateConfirm": "השבתה",

    // The four error codes F51 owns — a code→string map kept by hand, NOT
    // pinned by anything (see MAPPED_CODES in StaffSection.tsx). Everything
    // else, VALIDATION_ERROR included, falls through to errorMessage(error).
    "staff.error.DUPLICATE_EMAIL": "כתובת האימייל הזו כבר משויכת לאשת צוות פעילה.",
    "staff.error.LAST_OWNER_REQUIRED": "לבוטיק חייבת להיות בעלת בוטיק אחת לפחות.",
    "staff.error.STAFF_SELF_MANAGE": "אי אפשר לשנות את התפקיד של עצמך או להשבית את עצמך.",
    // The server's generic 403 body is ENGLISH and errorMessage() surfaces it
    // verbatim; this is the section's own Hebrew for a mid-session demotion.
    "staff.error.NOT_AUTHORIZED": "הפעולה הזו זמינה לבעלת הבוטיק בלבד.",

    // --- F52, the KPI dashboard ---
    //
    // Transcribed row-for-row from
    // .planning/design/screens/manage-dashboard/copy.md as DOTTED LITERAL keys,
    // so the deck and this block diff against each other line by line.
    // __tests__/i18n.test.ts proves every one of them resolves and enforces the
    // deck's two mechanical rules — no exclamation mark, and no string that
    // claims, implies or hedges that anything was sent.
    //
    // That second rule bites HERE for a reason F15 and F51 did not have: F52
    // sends nothing at all, but «בדרך» is a natural Hebrew word for a rising
    // trend and would trip a guard whose message is about SMS. The deck is
    // written around it (§0 rule 2) — that is why §5 says «נספרים תורים…» and
    // why no string anywhere describes a direction of travel.
    //
    // The section is READ-ONLY: no success message, no confirmation, no
    // validation string, no destructive-action copy, and no error-code→Hebrew
    // map. One sentence covers every ApiError (§2).
    "nav.dashboard": "סקירה",
    "dashboard.heading": "סקירה",
    // Labels a value that came off the wire — the console renders no "as of" it
    // computed itself (spec D8).
    "dashboard.generatedOnLabel": "נכון לתאריך:",

    // Section states.
    "dashboard.loading": "טוענים את הנתונים.",
    // {{count}} renders inside <bdi dir="ltr"> via isolateLtr. States the
    // predicate again so the ANNOUNCED number cannot be heard as attendance.
    "dashboard.summary": "סך התורים שלא בוטלו בתקופה: {{count}}",
    // The outage register: recoverable, unblaming, no technical words and no
    // retry control. A 403 from an out-of-enum role lands here too.
    "dashboard.loadFailed": "לא הצלחנו לטעון את הנתונים כרגע.",
    // Day one, as one muted line under the heading — never an EmptyState, which
    // would hide the forward panel (spec D10, Risk 1).
    "dashboard.firstRunNote":
      "המסך הזה מתמלא מעצמו ככל שנקבעים תורים. עד אז המספרים כאן הם אפס.",

    // Zero, unknown and too-small-to-show are THREE facts and get three
    // strings (§0 rule 3). `0.0%` is rendered arithmetic and has no key.
    // «עדיין» is load-bearing: the number is missing, not impossible.
    "dashboard.notEnoughData": "אין עדיין מספיק נתונים לחישוב.",
    // Spelled in words, NOT as `<0.1%`: a bare `<` inside an RTL paragraph
    // mirrors and reads as a bracket, and this string sits unisolated in
    // running Hebrew text.
    "dashboard.rateUnderFloor": "פחות מ־0.1%",

    // The forward panel — first on the screen, and the only one with a real
    // number on a boutique's first day.
    "dashboard.forwardHeading": "תפוסה בשבעת הימים הקרובים",
    // «הטווח» deliberately differs from the weeks panel's «התקופה», so the two
    // spans cannot read as one (§0 rule 6 / Risk 13).
    "dashboard.forwardRange": "הטווח:",
    "dashboard.forwardValueLabel": "אחוז התפוסה",
    // «מקומות» — a seat-slot, which is what capacity means here. Never «שעות»:
    // the grid has no duration (Risk 7).
    "dashboard.forwardCapacityLabel": "סך המקומות בטווח",
    "dashboard.forwardBookedLabel": "מקומות שנתפסו",
    // Closes Risk 6 in copy: the number moves through the day with no booking
    // changing, because the engine drops every start time that has passed.
    "dashboard.forwardHelp":
      "הספירה כוללת רק מועדים שאפשר עדיין להציע מהרגע הזה. מועדים שכבר חלפו היום אינם נכללים בה.",
    // capacity == 0. Names CLOSED HOURS, not zero demand — the remedy is a
    // different console section and the sentence has to point at it.
    "dashboard.forwardNoHours": "אין שעות פעילות פתוחות בטווח הזה, ולכן אין כאן מה לחשב.",

    // The weekly table.
    "dashboard.weeksHeading": "תורים לפי שבוע",
    "dashboard.weeksRange": "התקופה:",
    // The §0 rule 4 line. States the predicate, then says out loud that
    // no-shows are counted in it — without the second half the bar and the
    // no-show tile on the same screen contradict each other.
    "dashboard.weeksHelp": "נספרים תורים שנקבעו ולא בוטלו, כולל תורים שהלקוחה לא הגיעה אליהם.",
    "dashboard.weeksTableCaption": "תורים שלא בוטלו, לפי שבוע",
    // The cell shows a START date, and the header has to say so.
    "dashboard.weekColumn": "תחילת שבוע",
    // REUSED as the appointment-types table's count header: the two counts
    // state the same predicate, or the screen carries two meanings of one word.
    "dashboard.bookingsColumn": "תורים שלא בוטלו",

    // Cancellations and no-shows. The two attribution counts are independent
    // labelled values, NEVER a partition — a row cancelled before migration
    // 0010 carries NULL and is in neither (Risk 11).
    "dashboard.ratesHeading": "ביטולים ואי־הגעה",
    "dashboard.cancellationRateLabel": "שיעור הביטולים",
    // «בכל סטטוס» is the exact fact: this rate is over all four statuses,
    // unlike the one below it.
    "dashboard.cancellationHelp": "מתוך כל התורים שנקבעו בתקופה, בכל סטטוס.",
    "dashboard.cancelledByCustomerLabel": "ביטולים ביוזמת הלקוחה",
    // Without this pair a boutique that closed for a week and cancelled twenty
    // appointments itself reads its own closure as customer flakiness.
    "dashboard.cancelledByOwnerLabel": "ביטולים ביוזמת הבוטיק",
    "dashboard.noShowRateLabel": "שיעור אי־ההגעה",
    // The sharp denominator, in words (§0 rule 5). «בלבד» is the sentence's
    // whole job: the rate is not over all her appointments.
    "dashboard.noShowHelp": "מתוך התורים שסומנו כהתקיימו או כאי־הגעה בלבד.",
    "dashboard.unclassifiedLabel": "תורים שעברו ולא סומנו",
    // The Risk 5 bound, made visible: an owner who marks three no-shows and
    // nothing else reads 100%, and this line is what tells her the denominator
    // was three.
    "dashboard.unclassifiedHelp":
      "תורים שכבר עברו ולא סומנו כהתקיימו או כאי־הגעה. הם אינם נכללים בשיעור אי־ההגעה.",

    // Customers.
    "dashboard.customersHeading": "לקוחות בתקופה",
    // The cohort definition (spec D6). Without the predicate «סך הלקוחות»
    // reads as everyone in the address book.
    "dashboard.customersHelp": "נספרות לקוחות עם תור אחד לפחות בתקופה שלא בוטל.",
    "dashboard.customersTotalLabel": "סך הלקוחות",
    "dashboard.customersNewLabel": "לקוחות חדשות",
    "dashboard.customersReturningLabel": "לקוחות חוזרות",
    "dashboard.repeatRateLabel": "שיעור החזרה",
    // «אי פעם» is the lifetime scope, and it is what makes a bride who booked
    // twice inside the window both NEW and part of this rate.
    "dashboard.repeatRateHelp": "חלקן של הלקוחות בתקופה שקבעו בבוטיק יותר מתור אחד אי פעם.",

    // Appointment types.
    "dashboard.typesHeading": "סוגי התורים המבוקשים",
    // Honest at any list length (Risk 14): says the list is the most-booked
    // types, never claims completeness, and names no number, so it mirrors no
    // server constant.
    "dashboard.typesHelp": "מוצגים סוגי התורים שנקבעו הכי הרבה פעמים בתקופה.",
    "dashboard.typesTableCaption": "סוגי תורים לפי מספר התורים בתקופה",
    // The count column reuses dashboard.bookingsColumn.
    "dashboard.typeColumn": "סוג תור",
    // One muted line replacing the table. The day-one explanation is
    // dashboard.firstRunNote's job and it is already on screen.
    "dashboard.typesEmpty": "לא נקבעו תורים בתקופה הזו.",
    // --- F17 payment gateway (owner-only) ---
    //
    // FLAT dotted literals, appended, exactly like F15's and F51's blocks. The
    // nested `nav:` object above is deliberately untouched: it is the file's
    // merge-conflict zone while sibling features land, and i18next resolves
    // "nav.gateway" through `ignoreJSONStructure` either way — proven by
    // __tests__/i18n.test.ts.
    "nav.gateway": "סליקה ותשלומים",

    "gateway.heading": "חיבור לסליקה",
    "gateway.loadError": "לא הצלחנו לטעון את מצב הסליקה. אפשר לרענן ולנסות שוב.",

    // The PLATFORM has no gateway. No form, no buttons — nothing the owner can
    // do about it, and offering her a form would be a lie.
    "gateway.notConfigured": "גביית מקדמות אינה זמינה כרגע בפלטפורמה.",
    "gateway.notConfiguredHelp": "אין מה לעשות מצדך. נעדכן כשהאפשרות תיפתח.",

    "gateway.notConnected": "עדיין לא חובר חשבון סליקה.",
    "gateway.connected": "חשבון הסליקה מחובר.",
    "gateway.statusValid": "פעיל",
    "gateway.statusInvalid": "נדחה",
    "gateway.lastValidated": "נבדק לאחרונה",

    // Staging runs the fake secret box, so a real merchant credential typed in
    // here would be stored as base64 of plaintext. Both production boot guards
    // key on APP_ENV=production and 0012's CHECK admits 'fake' everywhere, so
    // this notice is the only thing standing between a helpful operator and a
    // real key on a staging disk.
    "gateway.testEnvNotice": "סביבת בדיקות — אין להזין פרטי סליקה אמיתיים",

    "gateway.formHeading": "פרטי חשבון הסליקה",
    "gateway.writeOnlyNotice": "מטעמי אבטחה הפרטים אינם ניתנים לצפייה לאחר השמירה. שמירה מחליפה את כל הפרטים.",
    "gateway.saveCta": "שמירת פרטי הסליקה",
    "gateway.validateCta": "בדיקה עכשיו",
    "gateway.disconnectCta": "ניתוק חשבון הסליקה",
    "gateway.disconnectConfirmTitle": "לנתק את חשבון הסליקה?",
    "gateway.disconnectConfirmBody": "גביית מקדמות תיפסק לכל הבוטיק עד לחיבור מחדש.",
    "gateway.disconnectConfirm": "ניתוק",
    "gateway.cancelCta": "ביטול",

    // The one cross-section fact the owner must see, composed from the two
    // calls the console already makes rather than a derived field on the API.
    "gateway.depositsWithoutGateway": "גביית מקדמות מופעלת בהגדרות, אבל אין חשבון סליקה מחובר.",
    "gateway.depositsWithoutGatewayCta": "חיבור חשבון סליקה",

    // Field labels for the fake adapter's declared shape. A field with no key
    // here falls back to its raw name in <bdi dir="ltr" lang="en"> — asserted by
    // __tests__/GatewaySection.test.tsx, not by the i18n suite, which cannot see
    // a key it never renders.
    "gateway.field.merchant_id": "מזהה סוחר",
    "gateway.field.api_key": "מפתח API",
    "gateway.field.webhook_secret": "סוד אימות התראות",

    // The server's generic bodies are ENGLISH and errorMessage() surfaces them
    // verbatim into a Hebrew console; these five are the section's own copy.
    // Never a provider message — the API does not return one.
    "gateway.error.GATEWAY_CREDENTIALS_REJECTED": "פרטי הסליקה נדחו. כדאי לבדוק אותם מול חשבון הסליקה ולנסות שוב.",
    "gateway.error.GATEWAY_NOT_CONFIGURED": "גביית מקדמות אינה זמינה כרגע.",
    "gateway.error.GATEWAY_NOT_CONNECTED": "צריך לחבר חשבון סליקה קודם.",
    "gateway.error.GATEWAY_UNAVAILABLE": "ספק הסליקה אינו זמין כרגע. אפשר לנסות שוב בעוד כמה דקות.",
    "gateway.error.TOO_MANY_ATTEMPTS": "יותר מדי ניסיונות. אפשר לנסות שוב מאוחר יותר.",

    // --- F34, the live shift board ---
    //
    // 34 rows transcribed from .planning/design/screens/shift-board/copy.md as
    // DOTTED LITERAL keys, so the deck and this block diff line by line.
    //
    // Two of the deck's §0 rules bite harder here than anywhere before, and both
    // are asserted in __tests__/i18n.test.ts rather than trusted:
    //
    // §0 rule 9 — NO string names or implies a retry interval. D4(6) backs the
    // poll off 5s -> ~60s on consecutive failures, so «הלוח יתעדכן מיד» is true
    // at tick 1 and a lie by tick 5, on a screen nobody is watching change. The
    // stale copy states what is UNKNOWN, never when it will be known.
    //
    // §0 rule 10 — the 403 body is generic BY DESIGN. The server ships one body
    // for every unadmitted role (auth/dependencies.py:17-21) so a probe cannot
    // learn which roles exist; naming a role here would be an invention the
    // server never made, and on the demotion path it would be the product
    // telling a staffer she was demoted, which is her manager's sentence.
    //
    // The four status words and «אישרה הגעה» are REUSED via statusBadge, never
    // re-declared: a second spelling of «בוטל» in one console is a defect.
    "nav.board": "לוח היום",
    "board.heading": "לוח היום",
    // A board with no date picker must still say which day it shows. The moment
    // it matters is a counter tablet at 00:01 (D12), where the date rolling
    // under an unattended screen would otherwise be invisible.
    "board.dayLine": "היום · {{date}}",

    // The freshness row — the whole live-ness contract, and never announced.
    // Past tense on purpose: «עודכן 14:07» says THIS WAS TRUE AT 14:07, never
    // «בזמן אמת», which the poll cannot keep even for one interval.
    "board.summary": "הגיעו {{ratio}}",
    "board.updatedAt": "עודכן {{time}}",
    "board.staleAt": "אין עדכון מאז {{time}}",
    "board.staleBody": "ייתכן שהמידע אינו עדכני.",
    "board.refresh": "רענון",

    // WCAG 2.0 SC 2.2.2 Pause, Stop, Hide — Level A, inside AA, and AA is a
    // LEGAL bar here (pre-decided #38). axe has no rule for it, so these eight
    // rows are the difference between green-in-CI and conformant-in-law.
    // One button whose NAME changes, never two buttons and never aria-pressed.
    // Each Aria string starts with its visible label so 2.5.3 label-in-name
    // holds.
    "board.pause": "השהיה",
    "board.pauseAria": "השהיה — עדכון הלוח",
    "board.resume": "חידוש",
    "board.resumeAria": "חידוש — עדכון הלוח",
    "board.pausedAt": "מושהה · עודכן {{time}}",
    "board.paused": "העדכון מושהה. הלוח לא יתעדכן עד לחידוש.",
    // Names the cause: the difference between "I paused this" and "this paused
    // itself" is the whole difference between a control and a bug.
    "board.idleStopped": "העדכון הופסק אחרי {{minutes}} דקות ללא פעילות.",
    // Not symmetry — a screen reader does not reliably re-announce the name of
    // an already-focused control that renamed itself, so without this the one
    // confirmation a sighted user gets free is denied to the user 2.2.2 is for.
    "board.resumed": "העדכון חודש.",

    // The row. «הגיעה» is the exact positive of the shipped «לא הגיעה», and the
    // recorded fact is spelled DIFFERENTLY on purpose: a booking marked no_show
    // after a check-in (D5 permits it — a status transition never clears
    // checked_in_at) then reads as two true facts, not a contradiction.
    "board.checkIn": "הגיעה",
    "board.checkInAria": "הגיעה — {{name}}, {{time}}",
    "board.checkedInAt": "נרשמה הגעה · {{time}}",
    "board.undo": "ביטול הרישום",
    "board.undoAria": "ביטול הרישום — {{name}}, {{time}}",
    "board.now": "עכשיו {{time}}",
    "board.movedAway": "התור הועבר לתאריך אחר",

    // The announced cues — user-initiated only, and they name the bride: after
    // tapping one of forty rows, «נרשמה הגעה.» cannot confirm WHICH one, which
    // makes it useless exactly when the board is busy. (F15 keeps the name out
    // of the detail h2 for the opposite reason: that is a persistent landmark.)
    "board.checkedInCue": "נרשמה הגעה עבור {{name}}.",
    "board.undoneCue": "הרישום בוטל עבור {{name}}.",

    // States.
    "board.loading": "טוען את לוח היום…",
    "board.loadFailed": "לא הצלחנו לטעון את הלוח כרגע.",
    "board.emptyTitle": "אין תורים היום",
    "board.emptyBody":
      "תורים שייקבעו להיום יופיעו כאן. לתאריכים אחרים אפשר לעבור למסך «תורים».",
    // Stated, never absorbed — a hidden bride is the one failure a board may
    // not have (D3).
    "board.truncated":
      "מוצגים {{count}} התורים הראשונים של היום. לרשימה המלאה אפשר לעבור למסך «תורים».",
    "board.sessionEnded": "תוקף החיבור פג. צריך להתחבר מחדש.",
    // The mid-shift demotion. Generic by design (§0 rule 10). «כרגע» is doing
    // real work: a re-promotion restores the board, so a sentence implying the
    // door is shut for good would be a guess the server never made. It points
    // at a person because there is nothing here she can fix from this screen.
    "board.accessEnded": "אין הרשאה לצפות בלוח כרגע. לבירור אפשר לפנות לבעלת הבוטיק.",
    "board.reload": "רענון הדף",

    // The ONE error string the board owns. F15's Hebrew for this code says
    // «כדאי לחזור לרשימה ולפתוח את התור מחדש» — advice for a detail screen you
    // can back out of. The board has no list to go back to and repairs itself on
    // the next tick. It names the EVENT, not a duration: «בעדכון הבא» is true at
    // 5s, at 60s and at whatever constant F29 lands on (§0 rule 9). Every other
    // code falls through to bookingErrorText unchanged.
    "board.error.transitionInvalid": "מצב התור השתנה. השורה תתוקן בעדכון הבא.",

    // --- F57: the floor's staff cards -------------------------------------
    //
    // Transcribed VERBATIM from .planning/design/screens/floor-staff-roles/
    // copy.md — that table is the canonical key list, not this file and not the
    // plan's prose: 32 keys invented here, 4 REUSED and deliberately not
    // re-declared (staff.roleOwner, staff.roleShiftManager, staff.selfMarker
    // above, and staff.loadFailed for the outage — copy.md drops the proposed
    // `floor.outage` under its §0 rule 8, because a second spelling of one
    // sentence in one console is a defect).
    //
    // Two spec strings were REVISED by the deck and the deck won both times:
    // floor.pauseAria is «השהיה — …» and not «השהיית …» (the visible label is
    // «השהיה», so the other form fails WCAG 2.5.3 label-in-name and a
    // speech-input user saying the visible word matches nothing), and
    // floor.breakSince drops «בהפסקה» because the Badge directly above already
    // says it.
    //
    // No string names or implies a retry interval (§0 rule 9) — the backoff
    // falsifies any number the moment it doubles — and floor.accessEnded names
    // no role (§0 rule 10).
    "nav.floor": "הצוות בקומה",
    "floor.heading": "צוות בקומה",

    "floor.loading": "טוען את רשימת הצוות…",
    "floor.empty": "אין נשות צוות פעילות",

    // The freshness row. `updatedAt` changes ONLY on a success, which is what
    // makes it a claim the panel can keep.
    "floor.updatedAt": "עודכן {{time}}",
    "floor.staleAt": "אין עדכון מאז {{time}}",
    "floor.staleBody": "ייתכן שהמידע אינו עדכני.",
    "floor.refresh": "רענון",

    // SC 2.2.2. ONE button whose name changes — never two, never aria-pressed.
    "floor.pause": "השהיה",
    "floor.pauseAria": "השהיה — עדכון הצוות",
    "floor.resume": "חידוש",
    "floor.resumeAria": "חידוש — עדכון הצוות",
    "floor.pausedAt": "מושהה · עודכן {{time}}",
    "floor.paused": "העדכון מושהה. רשימת הצוות לא תתעדכן עד לחידוש.",
    // Names the REGION, not just the act: board.idleStopped (:488) is otherwise
    // byte-identical, both write into a role="status" region, and both idle
    // windows are reset by the same global interactions — so on the board screen
    // a screen-reader user would hear one sentence twice with nothing saying
    // which surface stopped (design.md §9 F-4).
    "floor.idleStopped": "עדכון הצוות הופסק אחרי {{minutes}} דקות ללא פעילות.",
    "floor.resumed": "העדכון חודש.",

    // The card. The WORD carries the status; the colour never does.
    "floor.statusAvailable": "פנויה",
    "floor.statusBreak": "בהפסקה",
    // F36's ONE addition to this namespace, and it sits here rather than under
    // `rooms.` because the namespace names the payload and not the feature that
    // added the key. FEMININE, matching its two neighbours — and a DIFFERENT
    // word from the tile's masculine «תפוס», because the subject is a woman and
    // not a room. Without it, `status: "occupied"` falls through the binary
    // ternary this pair used to feed and the card prints «פנויה» about a
    // staffer standing in room 2.
    "floor.statusOccupied": "תפוסה",
    // ⚠ F36 makes this reachable on an OCCUPIED card for the first time, which
    // is the only place a screen can tell a shift manager that a break was
    // never closed. It needs no new string.
    "floor.breakSince": "מאז {{time}}",
    "floor.breakStart": "להפסקה",
    "floor.breakStartAria": "להפסקה — {{name}}",
    "floor.breakEnd": "חזרה",
    "floor.breakEndAria": "חזרה — {{name}}",

    // The cue region. A no-op 200 announces the SAME sentence as a write: the
    // outcome she wanted is the outcome that holds, and telling her she lost a
    // race would be telling her she was wrong when she was right.
    "floor.breakStartedCue": "נרשמה הפסקה עבור {{name}}.",
    "floor.breakEndedCue": "ההפסקה הסתיימה עבור {{name}}.",

    "floor.sessionEnded": "תוקף החיבור פג. צריך להתחבר מחדש.",
    "floor.accessEnded": "אין הרשאה לצפות ברשימת הצוות כרגע. לבירור אפשר לפנות לבעלת הבוטיק.",
    "floor.reload": "רענון הדף",
    // Inside the card, because a panel-level error names no colleague. Names the
    // EVENT that repairs it and never a duration.
    "floor.error.notFound": "אשת הצוות הזו כבר לא פעילה. הרשימה תתוקן בעדכון הבא.",

    // The three role words F57 adds. The two shipped ones are NOT re-declared.
    "staff.roleReception": "קבלה",
    "staff.roleSalesAssistant": "יועצת מכירות",
    "staff.roleSeamstress": "תופרת",

    // --- F53, customers CRM ---
    //
    // The SMS-log heading is «יומן הודעות» — "message log" — and NEVER
    // «הודעות שנשלחו». Two reasons and the second is the one that matters:
    // «נשלחו» trips the register guard below, and the log renders
    // status = 'failed' rows, so a heading saying "messages that were sent"
    // over messages that were not sent is exactly the lie that guard exists to
    // prevent. Same for the status word: 'sent' means the PROVIDER accepted the
    // message and returned an id, not that a handset received it — so
    // «הועברה לספק», which is true and promises no delivery this product
    // cannot observe.
    "nav.customers": "לקוחות",
    "customers.heading": "לקוחות",
    "customers.searchLabel": "חיפוש לפי שם או טלפון",
    "customers.searchPlaceholder": "שם או מספר טלפון",
    "customers.listLoading": "טוען את רשימת הלקוחות…",
    // Base key only, no _one/_other — the booking.dayCount shape.
    "customers.count": "לקוחות ברשימה: {{count}}",
    // `offset` is pinned to 0 and there is no pager, so `customers.count` above
    // announces the count under the SEARCH PREDICATE, which is not the length
    // of the list beneath it. Without this line a boutique with 60 customers
    // reads «לקוחות ברשימה: 60» over 50 rows and nothing says the rest exist.
    // Two numbers, mid-sentence with Hebrew on both sides — the
    // customers.messagesTruncated shape, so neither run needs isolating.
    "customers.listTruncated": "מוצגות {{count}} מתוך {{total}} לקוחות.",
    "customers.loadFailed":
      "לא ניתן לטעון את רשימת הלקוחות כרגע. אפשר לנסות שוב בעוד רגע.",
    // Two empty states, never one: telling a boutique with 200 customers that
    // it has none is a different (and wrong) sentence.
    "customers.emptyTitle": "אין עדיין לקוחות",
    "customers.emptyBody":
      "לקוחה נוספת לרשימה אחרי שהיא מאמתת את מספר הטלפון שלה וקובעת תור.",
    "customers.noResultsTitle": "אין תוצאות לחיפוש הזה",
    "customers.noResultsBody": "אפשר לנסות שם חלקי או ספרות מתוך מספר הטלפון.",
    "customers.back": "חזרה לרשימה",
    "customers.detailLoading": "טוען את פרטי הלקוחה…",
    "customers.detailFailed": "לא ניתן לטעון את פרטי הלקוחה כרגע.",
    // Also the NOT_FOUND map target: a 404 and another tenant's id are
    // indistinguishable by design, so they read the same.
    "customers.notFound": "הלקוחה הזו לא נמצאה. ייתכן שהכרטיס הוסר.",
    "customers.phoneLabel": "טלפון",
    "customers.notesLabel": "הערות",
    // The one honest thing to say about who reads them.
    "customers.notesHelp": "ההערות נשמרות בכרטיס ונראות לצוות הבוטיק בלבד.",
    "customers.notesPlaceholder": "מה כדאי לזכור לפעם הבאה",
    // The numbers in this line and the three below sit mid-sentence with Hebrew
    // on both sides, which the bidi algorithm already handles — and `help` is
    // typed string, so isolateLtr (a ReactNode) could not be used there anyway.
    "customers.notesTooLong": "ההערות יכולות להכיל עד {{length}} תווים.",
    "customers.notesInvalid": "ההערות מכילות תווים שאי אפשר לשמור.",
    "customers.tagsLabel": "תגיות",
    "customers.tagsHelp": "עד {{max}} תגיות, עד {{length}} תווים לתגית.",
    "customers.tagAddLabel": "תגית חדשה",
    "customers.tagAdd": "הוספה",
    "customers.tagRemove": "הסרה",
    // Starts with customers.tagRemove — WCAG 2.5.3, asserted in i18n.test.ts.
    "customers.tagRemoveAria": "הסרה של התגית {{tag}}",
    "customers.tagsEmpty": "אין תגיות בכרטיס הזה.",
    // Names the remedy rather than only the wall.
    "customers.tagsFull": "אי אפשר להוסיף עוד תגיות. אפשר להסיר תגית קיימת ולנסות שוב.",
    "customers.tagTooLong": "תגית יכולה להכיל עד {{length}} תווים.",
    "customers.tagDuplicate": "התגית הזו כבר קיימת בכרטיס.",
    "customers.tagInvalid": "התגית מכילה תווים שאי אפשר לשמור.",
    "customers.save": "שמירה",
    "customers.saved": "השינויים נשמרו",
    "customers.saveFailed": "לא ניתן לשמור את השינויים כרגע.",
    "customers.bookingsHeading": "היסטוריית תורים",
    "customers.bookingsEmpty": "אין עדיין תורים בכרטיס הזה.",
    "customers.bookingsTruncated": "מוצגים {{count}} התורים האחרונים.",
    "customers.messagesHeading": "יומן הודעות",
    "customers.messagesHelp": "יומן לקריאה בלבד. אי אפשר לערוך או למחוק רשומה.",
    "customers.messagesEmpty": "אין עדיין רשומות ביומן ההודעות.",
    // Two numbers. {{total}} is messages_total — the send volume the fifty-row
    // window cannot show, because OTP rows are always the newest.
    "customers.messagesTruncated": "מוצגות {{count}} מתוך {{total}} רשומות ביומן.",
    "customers.messageKindOtp": "קוד אימות",
    "customers.messageKindConfirmation": "אישור תור",
    "customers.messageKindReminder": "תזכורת",
    "customers.messageKindOwnerCancel": "ביטול מטעם הבוטיק",
    "customers.messageKindOwnerReschedule": "שינוי מועד מטעם הבוטיק",
    "customers.messageStatusQueued": "בהמתנה",
    "customers.messageStatusSent": "הועברה לספק",
    // The row the log exists to be able to show.
    "customers.messageStatusFailed": "נכשלה",
    // Names no role and nothing that changed — the server ships ONE 403 body so
    // a probe cannot learn which roles exist. «כרגע» is load-bearing: a
    // re-promotion restores access, so a sentence implying a permanent door
    // would be a guess the server never made.
    "customers.error.NOT_AUTHORIZED":
      "אין הרשאה לצפות בכרטיסי הלקוחות כרגע. לבירור אפשר לפנות לבעלת הבוטיק.",

    // --- F36: the fitting rooms ---------------------------------------------
    //
    // Transcribed from .planning/design/screens/fitting-rooms/copy.md, which is
    // the CANONICAL key list — spec D17's table is superseded by it and is
    // missing fourteen keys the components require.
    //
    // ⚠ NO `nav.rooms`, and that is a decision: the rooms are content of the
    // floor, not a twelfth console section.
    //
    // ⚠ NO string places a Hebrew preposition, article or agreeing verb against
    // {{room}} or {{dress}}. Those are USER-TYPED NOUNS that carry their own
    // noun and their own gender — the boutique types «חדר 1 / חדר 2 / הבמה» —
    // so «בחדר {{room}}» renders «בחדר חדר 2» and «{{room}} נתפס» renders
    // «הבמה נתפס». The four shapes that survive it are an em-dash with the
    // value last, a colon appositive with the value last, and the value
    // rendered as its own element. {{name}} is exempt: every persona word in
    // this product is feminine, so a feminine verb against a staffer's name
    // agrees by construction.
    //
    // The panel is inside FloorPanel's poll and inherits every freshness,
    // pause, idle, stale, outage and terminal state from it. Seventeen `floor.*`
    // and `staff.*` keys are REUSED unchanged and none of them is respelled
    // here.
    "rooms.heading": "חדרי מדידה",
    "rooms.manage": "ניהול חדרים",
    // «עדיין» does real work: it says NOT YET, which is a setup step, rather
    // than NONE, which reads as a fault.
    "rooms.empty": "עדיין לא הוגדרו חדרי מדידה",
    "rooms.emptyCta": "הוספת חדר",

    // The tile's state WORDS. «פנוי» is masculine, agreeing with «חדר», and is
    // deliberately not the staff card's «פנויה»: a room and a staffer are
    // different subjects and the two words on one screen must not look like one
    // word inflected by accident.
    "rooms.free": "פנוי",
    "rooms.occupied": "תפוס",
    // A condition of the ROOM. «לא פעיל» would read as a switch somebody
    // flipped, which is true and is not what she needs to know in a corridor.
    "rooms.inactive": "מחוץ לשירות",
    // A LABEL, so the client's name can be its own element rather than being
    // interpolated into a sentence that could mis-agree with it.
    "rooms.clientLabel": "לקוחה",
    // The DEFAULT render for any claim made without a booking, and also what a
    // swept booking or an erased customer renders as. «מקושרת» is load-bearing:
    // the room has a bride in it; what it has no link to is a booking record.
    "rooms.anonymous": "ללא לקוחה מקושרת",
    // «דק'» is invariant in Hebrew, so ONE key covers 1 and 95 — there is no
    // hours branch and no plural, and this must not become the console's first
    // i18next plural rule.
    "rooms.elapsed": "כבר {{minutes}} דק'",
    // The first minute of every fitting, and the representable-but-odd
    // negative: `created_at` comes from the database clock while `server_now`
    // comes from the service's, so assignedAt > serverNow is representable.
    "rooms.elapsedJustNow": "זה עתה",
    // D11's ghost holder. Says what is true and does not speculate about why.
    "rooms.holderGone": "אשת הצוות שתפסה את החדר כבר לא ברשימה.",
    "rooms.dresses": "שמלות בחדר",

    // The tile's controls. Every *Aria opens with its visible label so WCAG
    // 2.5.3 label-in-name holds, then names the room after an em-dash — five
    // tiles all offering a button called «שחרור» is a screen-reader dead end.
    // An aria-label takes no markup, so an interpolated value in one needs no
    // bidi treatment at all.
    "rooms.claim": "תפיסת החדר",
    "rooms.claimAria": "תפיסת החדר — {{room}}",
    "rooms.release": "שחרור",
    "rooms.releaseAria": "שחרור — {{room}}",
    "rooms.handover": "העברה לעמיתה",
    "rooms.handoverAria": "העברה לעמיתה — {{room}}",
    "rooms.addDress": "הוספת שמלה",
    "rooms.addDressAria": "הוספת שמלה — {{room}}",
    // A text button, not a chip with an ×: this console ships no icon
    // vocabulary, and a glyph's target ends up the size of the glyph.
    "rooms.removeDress": "הסרה",
    "rooms.removeDressAria": "הסרה — {{dress}}",

    // F58's dispatch control, on each FREE + ACTIVE tile and only while the
    // queue is non-empty. `rooms.*` and not `waitlist.*`: it renders in a
    // component that draws eighteen `rooms.` strings and would otherwise be the
    // only foreigner among them — and it puts the new accessible name under the
    // SHIPPED 2.5.3 loop above by adding one word to an array.
    //
    // ⚠ «— {{room}}» and never «לחדר {{room}}». A room label is a user-typed
    // noun that carries its own noun, so the boutique's «חדר 2» renders «לחדר
    // חדר 2»; the em-dash puts the value last, where it agrees with nothing.
    "rooms.takeNext": "קחי את הבאה",
    "rooms.takeNextAria": "קחי את הבאה בתור — {{room}}",

    // The inline client picker. ⚠ A Select's `label` prop is typed `string`, so
    // it CANNOT be bidi-isolated — which is exactly why the value goes last,
    // where a direction flip has nothing after it to reorder past.
    "rooms.clientPick": "לקוחה — {{room}}",
    // Always first, always selected on mount. This is the one-tap path.
    "rooms.clientNone": "ללא לקוחה",
    // Names no count and no limit — both are the server's to change without a
    // copy edit — and names the ORDERING instead, which is a fact she can act
    // on.
    "rooms.clientsTruncated": "הרשימה חלקית. לקוחות עם שעת תור מאוחרת יותר אינן מופיעות כאן.",

    // The registry dialog.
    "rooms.manageTitle": "חדרי המדידה של הבוטיק",
    "rooms.label": "שם החדר",
    // Reorder is this labelled number field and never drag-and-drop: drag's
    // most common implementation is a WCAG 2.1.1 keyboard failure that axe
    // cannot see. Negatives are legal and are how a row moves to the front
    // without renumbering the rest.
    "rooms.order": "סדר תצוגה",
    "rooms.active": "פעיל",
    // Reused unchanged as the dress dialog's confirm — one word for one act.
    "rooms.add": "הוספה",
    "rooms.save": "שמירה",
    "rooms.delete": "מחיקה",
    "rooms.cancel": "ביטול",
    // Distinct from «ביטול» on purpose: the registry has no pending transaction
    // to abandon, so «ביטול» would imply an undo the dialog does not perform.
    "rooms.close": "סגירה",
    // ⚠ Generic, with the room label rendered in the dialog's children as its
    // own <bdi>. Modal.title is typed `string`, so a label interpolated here
    // could not be isolated — and it would sit MID-string, the one position
    // where a Latin-script room label reorders visibly.
    "rooms.deleteConfirm": "למחוק את החדר מרשימת החדרים?",
    "rooms.deleteConfirmBody": "אי אפשר למחוק חדר שיש בו לקוחה עכשיו.",
    // Field-local, --color-danger from Input — the one place `danger` is
    // correct on this surface, because it is a thing she must fix in the field
    // she must fix it in. Neither names a number: both bounds are mirrored
    // constants the server owns.
    "rooms.labelRequired": "צריך למלא שם לחדר.",
    "rooms.labelTooLong": "השם ארוך מדי.",
    "rooms.orderRange": "סדר התצוגה מחוץ לטווח.",
    // The dialog's OWN role="status", not the panel's: a live region outside an
    // open modal is not reliably announced. The save cue is the shipped
    // `common.saved`, reused rather than declared a fourth time.
    "rooms.addedCue": "החדר נוסף.",
    "rooms.deletedCue": "החדר נמחק.",

    // The dress dialog.
    "rooms.dressTitle": "הוספת שמלה — {{room}}",
    // Client-side filtering only — no ?q=, no debounce, no second request.
    "rooms.dressFilter": "חיפוש שמלה",
    "rooms.dressPick": "שמלה",
    "rooms.sizePick": "מידה",
    "rooms.sizeNone": "ללא מידה",
    "rooms.dressNoMatch": "אין שמלה שמתאימה לחיפוש.",
    // No CTA: three of the five roles cannot reach «שמלות» at all, and pointing
    // them at a door that answers 403 is the trap this surface avoids.
    "rooms.dressEmpty": "אין עדיין שמלות בקטלוג.",
    // Points at the remedy that is in the dialog with her, rather than at a
    // section three of the five roles cannot open.
    "rooms.dressTruncated": "הרשימה חלקית. אפשר לצמצם אותה עם החיפוש.",

    // The handover dialog.
    "rooms.handoverTitle": "העברת החדר",
    "rooms.handoverPick": "העברה אל",
    // She is NOT excluded from the list: the server accepts the handover and
    // the indexes do not forbid it, so hiding her would be the client asserting
    // a rule the server does not have.
    "rooms.handoverOnBreak": "{{name}} — בהפסקה",
    // `secondary` and never `danger`: a handover destroys nothing.
    "rooms.handoverConfirm": "העברה",
    "rooms.handoverNobody": "אין עכשיו עמיתה פנויה לקבל את החדר.",

    // The errors. NONE of these is red. A 409 is two staffers reaching for one
    // curtain at the same second and a 404 is a screen one tick behind —
    // nothing that can go wrong on this surface is her fault, so all of them
    // are the NOTICE register. The only `danger` in the feature is the
    // registry's delete trigger and the field-local messages above.
    //
    // ⚠ Each 409 needs TWO strings, because `details` is optional: the occupant
    // can release between the index violation and the occupant read, and an
    // empty interpolation on a legally binding surface is worse than a sentence
    // that admits it does not know.
    "rooms.error.ROOM_OCCUPIED": "{{name}} כבר בחדר הזה.",
    "rooms.error.roomOccupiedUnknown": "החדר נתפס זה עתה. נסי שוב.",
    // A DIFFERENT sentence with a different remedy, which is why it is a
    // different code: the fix is to release the other room, not to take another
    // one. Colon appositive, so the unknown form below is a strict PREFIX of
    // this one and the two can never read as two different facts.
    "rooms.error.STAFF_OCCUPIED": "היא כבר בחדר אחר: {{room}}.",
    "rooms.error.staffOccupiedUnknown": "היא כבר בחדר אחר.",
    // ⚠ F58's SELF forms of the same 409, and two NEW keys rather than a
    // two-line edit of the pair above. The third-person value is asserted
    // verbatim in RoomsPanel.test.tsx, RoomHandoverDialog.test.tsx and
    // i18n.test.ts, so editing it reds four shipped assertions on the PR whose
    // acceptance rule is that every shipped suite passes unedited. A take-next
    // and a row's push-assign carry NO target staffer, so the refusal is about
    // the caller herself and «היא» would name nobody on the screen. Rendered on
    // the two dispatch verbs only; handover keeps the shipped pair.
    "rooms.error.staffOccupiedSelf": "את כבר בחדר אחר: {{room}}.",
    "rooms.error.staffOccupiedSelfUnknown": "את כבר בחדר אחר.",
    // F58, 409: the last woman left the queue between the render and the tap —
    // «an ordinary five-second race». Without its own branch it takes
    // `describe()`'s fall-through and tells a manager whose queue is simply
    // empty that a load failed, in the muted OUTAGE register on top. It is
    // `waitlist.empty` plus a full stop, deliberately: the alert answers her
    // tap, the EmptyState one panel below answers the screen.
    "rooms.error.QUEUE_EMPTY": "אין ממתינות בתור.",
    // THREE 404 sentences, not one: «החדר כבר לא זמין» is actively misleading
    // when the room is fine and the fitting simply ended — and equally
    // misleading when the room is fine and the BOOKING she picked is the thing
    // the server could not find. The envelope is the same `NOT_FOUND` body for
    // all three, so the caller decides from what it sent.
    "rooms.error.notFound": "החדר כבר לא זמין. הרשימה תתוקן בעדכון הבא.",
    "rooms.error.assignmentGone": "הלקוחה כבר לא בחדר. הרשימה תתוקן בעדכון הבא.",
    // ⚠ NO «בעדכון הבא» and therefore NO paused twin: the panel does not
    // promise a repair here, it PERFORMS one — the pick is dropped and the
    // arrivals list re-read before this sentence renders — so the next tap is
    // the anonymous claim and the picker is already back to «ללא לקוחה».
    "rooms.error.clientGone":
      "הלקוחה שנבחרה כבר לא ברשימת ההגעות של היום. אפשר לבחור לקוחה אחרת או לתפוס את החדר ללא לקוחה.",
    // ⚠ The PAUSED forms. `pause()` stops the loop and nothing else — a claim
    // stays fully available while paused — so «בעדכון הבא» is a promise the
    // screen will not keep. Same failure as a named duration, in the event
    // form. These point at «חידוש», which is the control actually on screen.
    "rooms.error.notFoundPaused": "החדר כבר לא זמין. הרשימה תתוקן עם חידוש העדכון.",
    "rooms.error.assignmentGonePaused": "הלקוחה כבר לא בחדר. הרשימה תתוקן עם חידוש העדכון.",
    // The registry delete's 409. `rooms.error.ROOM_OCCUPIED` is written for a
    // claim («כבר בחדר הזה» = already in THIS room) and reads as a non-sequitur
    // as a reason a delete failed, so it gets its own sentence naming the
    // occupant AND the remedy.
    "rooms.error.deleteOccupied": "{{name}} נמצאת בחדר עכשיו. אפשר למחוק אותו אחרי שהיא תצא.",
    "rooms.error.deleteOccupiedUnknown": "החדר תפוס עכשיו. אפשר למחוק אותו אחרי שיתפנה.",

    // The cues. USER-INITIATED ONLY — the poll never writes here, and a room
    // claimed, released or handed over by a colleague repaints its tile
    // silently.
    //
    // ⚠ THE CLIENT'S NAME IS NEVER IN A CUE. The region is persistent (nothing
    // clears it on a timer), so a bride's name in it would sit on a five-role
    // screen for an arbitrary length of time. The tile one line away carries
    // her name for the duration of the fitting and not one second longer.
    "rooms.claimedCue": "החדר נתפס: {{room}}.",
    "rooms.releasedCue": "החדר שוחרר: {{room}}.",
    // Names the RECEIVING colleague rather than the room: what she needs
    // confirmed is who has it now, and the room is not in doubt.
    "rooms.handedOverCue": "החדר הועבר אל {{name}}.",
    "rooms.dressAddedCue": "השמלה נוספה לחדר: {{dress}}.",
    "rooms.dressRemovedCue": "השמלה הוסרה מהחדר: {{dress}}.",

    // F58 — the waitlist panel, the THIRD child of the floor screen. 37 keys,
    // transcribed from copy.md, which is canonical: spec D16's table is a
    // proposal and this block corrects fourteen of its rows.
    //
    // The panel's chrome. The heading is an h3 peer of «חדרי מדידה» and carries
    // tabIndex={-1} because it is the focus-rescue target for three of the six
    // moves. Plural and indefinite: it names a group of people, not a
    // destination, and there is no nav row for it to match.
    "waitlist.heading": "ממתינות בתור",
    // The state this panel is in for most of a boutique's day. It must read as
    // QUIET, never as broken and never as unconfigured — there is nothing to set
    // up and nobody to call, so no body and no CTA ship with it. No «עדיין»,
    // which would promise arrivals the shop cannot promise.
    "waitlist.empty": "אין ממתינות בתור",
    // >100 waiting is a griefing flood inside F33's tenant ceiling, not a
    // boutique. Names no count and no limit — both are the server's to change
    // without a copy edit — and names WHAT FALLS OFF instead: the list is
    // arrival-ordered, so the missing rows are the later arrivals.
    "waitlist.truncated": "הרשימה חלקית. הממתינות שהגיעו מאוחר יותר אינן מופיעות כאן.",
    // ⚠ PANEL-LEVEL and rendered ONCE, under the heading. Forty identical
    // sentences is not a design, and the fact is about the rooms rather than
    // about any entry. It is the only surface that explains why «שבצי לחדר»
    // vanished from every row and «קחי את הבאה» from every tile at one moment.
    // «כרגע» is load-bearing: a release two minutes later restores both.
    "waitlist.noFreeRoom": "אין חדר פנוי כרגע.",

    // The row's facts, and every one of them is a WORD. ⚠ «מדידת כלה» and not
    // «שמלת כלה»: the storefront check-in form — the form she filled in —
    // spells the bride arm that way, and a manager reading a different word
    // beside a customer who ticked that one cannot know they are the same fact.
    "waitlist.visitBride": "מדידת כלה",
    "waitlist.visitEvening": "שמלת ערב",
    // Computed at render against the envelope's server_now through the shipped
    // `elapsedMinutes`, and frozen exactly when the panel freezes. «ממתינה» and
    // not «כבר»: the room's word says this has been going on INSIDE a room, the
    // queue's says she is still standing there. No hours branch and no plural —
    // «דק'» is invariant in Hebrew, so one key covers 1 and 95, and this must
    // not become the console's first i18next plural rule.
    "waitlist.waiting": "ממתינה {{minutes}} דק'",
    // The first minute of every arrival, and the clamped negative: `arrived_at`
    // is created_at, whose DEFAULT now() is the DATABASE host's clock while
    // server_now comes from the service's Python one, so arrived_at > serverNow
    // is representable.
    "waitlist.waitingJustNow": "הגיעה זה עתה",
    // The row's ONE Badge, `warning`. It is her QUEUE STATE — summoned and still
    // waiting — and it is the fact F59's public board reads the same column for.
    "waitlist.called": "נקראה",
    // ⚠ A LINE and not a second Badge. Two pills in 295px teaches the reader to
    // scan colours instead of words; and a chip names a CATEGORY, while the
    // manager's actual question is which of these two Noas do I remove — whose
    // answer is a fact she can check by asking the woman in front of her. A chip
    // also cannot say LIVE, and the twin may already be in a room, which is the
    // most valuable case on this panel to remove.
    "waitlist.duplicate": "יש עוד כניסה פעילה היום עם אותו מספר טלפון.",
    // Muted, so the second press's meaning is legible BEFORE it is pressed —
    // which is the whole reason skip_count is on the wire. Impersonal: who
    // skipped her is an audit question and not a floor one.
    "waitlist.skippedOnce": "דילגו עליה פעם אחת",

    // The row's four controls. WHICH ONE EXISTS is the rendered form of the
    // authorization axes — a 403 is terminal for the whole floor screen, so
    // there is no «אין לך הרשאה» string here and there cannot be. Every *Aria
    // is «<visible label> — {{name}}»: forty rows all offering a button named
    // «דלגי» is a screen-reader dead end, and four of spec D16's five proposals
    // failed WCAG 2.5.3, «הסרת {{name}} מהתור» on a different WORD FORM.
    "waitlist.call": "קראי",
    "waitlist.callAria": "קראי — {{name}}",
    // The row's one `secondary` — the act that ends its state. «שבצי לחדר» and
    // not «שבצי»: the bare verb is ambiguous on a floor where a staffer is also
    // assigned to things.
    "waitlist.assign": "שבצי לחדר",
    "waitlist.assignAria": "שבצי לחדר — {{name}}",
    "waitlist.skip": "דלגי",
    "waitlist.skipAria": "דלגי — {{name}}",
    // «הסרה» and not «מחיקה»: nothing is deleted — the row goes to `removed` and
    // the audit trail keeps it.
    "waitlist.remove": "הסרה",
    "waitlist.removeAria": "הסרה — {{name}}",

    // The three inline reveals. No <dialog> anywhere in this feature: one would
    // need three focus mechanisms axe cannot see, and a row a tick can unmount
    // underneath it is exactly where that cost is highest.
    //
    // ⚠ A Select's `label` prop is typed `string`, so isolation is IMPOSSIBLE
    // rather than merely omitted — hence the value last, again.
    "waitlist.assignRoom": "שיבוץ לחדר — {{name}}",
    // The act, not «אישור» — the same root as the trigger, so the two read as
    // one gesture.
    "waitlist.assignConfirm": "שיבוץ",
    // Shown only once the rendered skip_count is >= 1. Focus lands on this
    // paragraph, so a screen reader hears what is being asked.
    "waitlist.confirmSkip": "דילוג נוסף יסיר את {{name}} מהתור. להמשיך?",
    "waitlist.confirmRemove": "להסיר את {{name}} מהתור?",
    // ⚠ A second line inside the remove reveal, rendered ONLY when the entry is
    // flagged duplicate, and the only mitigation Risk 2 has that the manager can
    // act on: whichever of her two tickets is removed, if it is the one her tab
    // polls, her phone renders «הביקור הזה הסתיים.» and stops the loop while she
    // is still in the queue on the other one. Hedged with «אם», because the
    // panel genuinely cannot know which ticket that phone holds.
    "waitlist.confirmRemoveDuplicate":
      "אם הטלפון שלה מציג את הכניסה הזו, המסך שלה יראה שהביקור הסתיים. אפשר לומר לה שהמקום שלה נשמר.",
    // ONE key for BOTH destructive reveals, because the removing second skip IS
    // a removal. A bare «אישור» is the button a hurried reader presses without
    // having read the question, on the one press in this feature with no undo.
    "waitlist.confirmRemoveYes": "אישור ההסרה",
    // Names what happens if she declines. «ביטול» on a REMOVAL confirm is two
    // cancellations in one control pair.
    "waitlist.confirmKeep": "השארה בתור",

    // The refusals. NONE of these is red: a 409 is two managers reaching for one
    // customer and a 404 is a screen one tick behind, so both are the NOTICE
    // register. The only `danger` in this feature is the confirm button above.
    "waitlist.error.notFound": "הכניסה הזו כבר לא קיימת. הרשימה תתוקן בעדכון הבא.",
    "waitlist.error.notFoundPaused": "הכניסה הזו כבר לא קיימת. הרשימה תתוקן עם חידוש העדכון.",
    // ⚠ ONE code, THREE sentences, chosen on `details.status`, because the
    // remedies differ: go and find her in a fitting room / there is nothing to
    // do and the next tick drops the row / this one admits it does not know.
    // `details` is optional on the wire, which is what makes the third a
    // requirement rather than a nicety.
    "waitlist.error.QUEUE_TICKET_NOT_WAITING": "היא כבר בטיפול.",
    "waitlist.error.ticketClosed": "הכניסה הזו נסגרה.",
    "waitlist.error.ticketNotWaitingUnknown": "הכניסה הזו כבר לא ממתינה.",
    // ⚠ THIS SENTENCE EXISTS BECAUSE OF THE SERVER'S `AND skip_count =
    // :seen_skip_count`. Without the conjunct behind it, two managers each
    // tapping «דלגי» ONCE on a woman at skip_count == 0 would REMOVE her with
    // the confirm never shown on either device. She is NOT removed; the press is
    // refused — and the same tick that clears this alert raises the rendered
    // count to 1, so her next press correctly opens the confirm.
    "waitlist.error.QUEUE_TICKET_CHANGED": "מצב הכניסה השתנה. הרשימה תתוקן בעדכון הבא.",
    "waitlist.error.queueTicketChangedPaused":
      "מצב הכניסה השתנה. הרשימה תתוקן עם חידוש העדכון.",

    // The cues. USER-INITIATED ONLY, and ⚠ NOT ONE OF THEM NAMES A CUSTOMER.
    // FloorPanel's region is PERSISTENT — nothing clears it, not a timer, not a
    // tick, not an unmount — so «נועה הוסרה מהתור.» would sit in a five-role
    // screen's DOM after her row has left the payload and after she has left the
    // shop, making the cue the only place her name survives. So the cues name
    // the ACT, and the row one line away carries her name for exactly as long as
    // she is on the floor.
    //
    // One cue for take-next AND push-assign: they differ only in who chose the
    // customer. «שובצה» shares the root of «שבצי לחדר», so the control and its
    // confirmation read as one vocabulary, and the colon puts the room label
    // last where it agrees with nothing.
    "waitlist.dispatchedCue": "הלקוחה שובצה: {{room}}.",
    // ⚠ «נרשמה» and never «נשלחה». F58 SENDS NOTHING to anybody — no SMS, no
    // scheduled_messages row, no sender ID — `call` stamps a timestamp, and
    // that is what makes her page read «אפשר לגשת לדלפק» and F59's board
    // highlight her. «נשלחה» would also trip the register guard that filters
    // every value in HE for /נשלח|תישלח|בדרך/. Identical after the second call
    // that writes nothing, deliberately: telling her she lost a race would be
    // telling her she was wrong when she was right.
    "waitlist.calledCue": "הקריאה נרשמה.",
    "waitlist.skippedCue": "הועברה לסוף התור.",
    // After a removal AND after the second skip, which removes her. The client
    // chooses between this and the line above on the seen_skip_count it SENT, so
    // it needs nothing from a response that no longer carries her — and a row
    // that vanished under «הועברה לסוף התור» would be the screen reporting the
    // opposite of what it did.
    "waitlist.removedCue": "הוסרה מהתור.",

    // F33 — the printable check-in code. Two audiences in one block, which is
    // the only unusual thing about it: `heading`, `intro`, `printCta` and
    // `loadFailed` are read by the owner in the console; `posterLine`,
    // `urlLabel` and `urlHint` are read by a woman standing at the door, off a
    // sheet of paper, with no way to ask a follow-up question.
    //
    // Nothing here promises a message. F20 will add a queue SMS; until then a
    // string implying one would be a lie the product cannot keep — which is
    // also why the i18n suite's send guard covers this block.
    "nav.checkinQr": "קוד סריקה",
    "checkinQr.heading": "קוד סריקה לרישום לתור",
    "checkinQr.intro":
      "אפשר להדפיס את הדף הזה ולתלות אותו בכניסה. מי שסורקת את הקוד מגיעה ישירות לטופס הרישום לתור.",

    // The poster itself. Feminine plural imperative is the storefront's register
    // («טוענות את פרטי הבוטיק»), and the sentence names the OUTCOME rather than
    // the technology — «QR» appears only in the alt text, where it is the one
    // useful word.
    "checkinQr.posterLine": "לרישום לתור אפשר לסרוק את הקוד",
    "checkinQr.imageAlt": "קוד QR שמוביל לטופס הרישום לתור",
    // The address in legible text, because a camera that will not focus is the
    // ordinary failure of a printed code and the poster is the only copy she
    // holds.
    "checkinQr.urlLabel": "כתובת הרישום:",
    "checkinQr.urlHint": "אפשר גם להקליד את הכתובת בדפדפן.",

    "checkinQr.printCta": "הדפסה",
    "checkinQr.loadFailed": "לא הצלחנו לטעון את קוד הסריקה כרגע.",
    // The failure's own way out. Same wording as booking.retry — the console
    // says one thing for one action — and it names no interval (§0 rule 9),
    // because nothing here knows when the read will succeed.
    "checkinQr.retry": "ניסיון נוסף",

    // --- F41, the atelier. 95 keys, 0 reused. F42 adds 40 below, 7 reused. ----
    //
    // The board states, it does not reassure: every string is a fact, and the
    // ones about time have a time on them. A seamstress reads this screen fifty
    // times a shift and warmth at that frequency is noise.
    //
    // ⚠ TEN of the values below are BYTE-IDENTICAL to shipped `board.*` /
    // `floor.*` strings and are DECLARED, not reused. Lifting them into a shared
    // `poll.*` namespace would edit BoardSection's and FloorPanel's i18n, and
    // both components must pass unedited — which is the only thing separating a
    // faithful fourth usePoll consumer from a subtly different one. Named owner
    // rather than a deferred trigger: the team, at F37 or F59, as a standalone
    // i18n PR touching no component logic.
    //
    // ⚠ Once `atelier` exists as a section here, ANY quoted "atelier.…" literal
    // anywhere in apps/manage/src is scraped as an i18n key and must resolve to
    // a defined, non-empty Hebrew string. Do not name a data-testid
    // `atelier.submit`.
    "nav.atelier": "תפירה",
    // «תפירה» — the craft. Not «תיקונים» (repairs, which reads as fixing a
    // mistake) and not «אטלייה» (a transliteration the boutique does not say out
    // loud). The heading is definite where the nav row is bare: a heading names
    // the thing on screen, a nav row names a destination.
    "atelier.heading": "לוח התפירה",
    // The CTA above the columns AND the create dialog's title — one fact, one
    // key. Two byte-identical strings under two keys is how a console ends up
    // spelling one fact two ways the day somebody edits one of them.
    "atelier.newTicket": "כרטיס חדש",

    // The freshness row. «עודכן 14:07» says THIS WAS TRUE AT 14:07 — past tense
    // by construction, because the board polls and «בזמן אמת» is a claim it
    // cannot keep even for one interval.
    "atelier.updatedAt": "עודכן {{time}}",
    "atelier.staleAt": "אין עדכון מאז {{time}}",
    // Says what is UNKNOWN, not what is wrong: the board cannot tell a dead wifi
    // from a dead server. No apology, no «אנא», and no interval — the backoff
    // stretches 5s to ~60s, so «מיד» is true at tick 1 and false by tick 5.
    "atelier.staleBody": "ייתכן שהמידע אינו עדכני.",
    "atelier.refresh": "רענון",

    // WCAG 2.0 SC 2.2.2, and axe has no rule for it: at zero of these eight keys
    // the product ships green in CI and non-conformant in law. Third such
    // surface in this console.
    //
    // «השהיה» is identical to the board's and the floor panel's on purpose — one
    // product vocabulary, and a staffer must not have to learn that «השהיה» and
    // «עצירה» are the same act.
    "atelier.pause": "השהיה",
    // ⚠ «השהיה — …» and NOT «השהיית…»: the accessible name must START with the
    // visible label or a speech-input user saying «השהיה» matches nothing (WCAG
    // 2.5.3). The two word forms differ by one letter.
    "atelier.pauseAria": "השהיה — לוח התפירה",
    // ONE button whose name changes, never two buttons and never aria-pressed.
    // Not «רענון»: that word is the one-shot retry above, and the two acts
    // differ — one fetch now vs. start the beat again.
    "atelier.resume": "חידוש",
    "atelier.resumeAria": "חידוש — לוח התפירה",
    "atelier.pausedAt": "מושהה · עודכן {{time}}",
    "atelier.paused": "העדכון מושהה. לוח התפירה לא יתעדכן עד לחידוש.",
    // ⚠ May NOT be byte-identical to `board.idleStopped` or `floor.idleStopped`.
    // All three write into a role="status" region and all three idle windows are
    // reset by the same global listeners in usePoll. This console renders one
    // section at a time so the collision is rarer here — the string still names
    // its own region, because the reason is a rule and not a coincidence.
    "atelier.idleStopped": "עדכון לוח התפירה הופסק אחרי {{minutes}} דקות ללא פעילות.",
    // Not symmetry: on resume the button's own accessible name flips, and a
    // screen reader does not reliably re-announce the name of a control that is
    // already focused — so without this the one confirmation a sighted user gets
    // for free is denied to the user 2.2.2 exists for.
    "atelier.resumed": "העדכון חודש.",

    // A SECOND navigation landmark on a page that already has the shell's, so it
    // must be named or a screen-reader user cycling landmarks lands on two
    // things both called "navigation". Names the act, not the thing.
    "atelier.railAria": "מעבר לשלב",
    // ⚠ `{{total}}`, NEVER `{{count}}`. `count` is i18next's plural-resolution
    // trigger, and this string renders TEN times per paint (five headings, five
    // rail chips). ⚠ And it carries NO NOUN: «{{total}} כרטיסים» is wrong at 1
    // and wrong at 2 (Hebrew takes a dual), and doing it properly needs four
    // plural suffixes per string in two bundles — while the <ul>'s own list role
    // already announces the item count to the reader the noun was for.
    "atelier.stageCount": "{{stage}} · {{total}}",
    // The five stages ARE the state machine — five nullable timestamps, no
    // status column — and these are the words the whole product speaks about
    // them. `atelier.emptyBody` teaches all five in one sentence and must not
    // drift from these.
    "atelier.stage.intake": "התקבל",
    "atelier.stage.inProgress": "בעבודה",
    "atelier.stage.qc": "בקרה",
    "atelier.stage.ready": "מוכן",
    // ⚠ «נמסר» — handed over. Deliberately NOT «נשלח», which is both wrong
    // (nothing is shipped; she collects) and rejected outright by this suite's
    // register guard. Nothing in this product delivers anything to anybody.
    "atelier.stage.delivered": "נמסר",
    "atelier.emptyColumn": "אין כרטיסים בשלב זה",

    // Ten per-card controls, ten `*Aria` siblings. A 30-card board otherwise
    // exposes 30 controls all named «לשלב הבא», 30 more all named «העברה» and 30
    // more all named «שיוך», and a screen-reader user pulling up the control
    // list — or a speech-input user saying the label — cannot address a specific
    // ticket (WCAG 4.1.2, 2.4.6). Every `*Aria` value STARTS with its visible
    // label (2.5.3) and adds the bride's name.
    //
    // ⚠ An aria-label takes no markup, so `{{name}}` interpolates plainly in
    // every one of them — no <bdi>, no helper. There is nothing rendered to
    // reorder.
    "atelier.advance": "לשלב הבא",
    "atelier.advanceAria": "לשלב הבא — {{name}}",
    "atelier.skip": "העברה לשלב",
    "atelier.skipAria": "העברה לשלב — {{name}}",
    // ⚠ Selection and commit are SEPARATE controls because a closed native
    // <select> fires `change` on every arrow keypress — an onChange-mutating
    // skip would write three timestamps and three audit rows while a keyboard
    // user was still choosing (WCAG 3.2.2 On Input, Level A).
    "atelier.skipCommit": "העברה",
    "atelier.skipCommitAria": "העברה — {{name}}",
    // It cancels A STAGE, not the ticket, and that distinction is the whole
    // reason «מחיקה» is a different word. Absent on an intake card.
    "atelier.undo": "ביטול שלב",
    "atelier.undoAria": "ביטול שלב — {{name}}",
    // ⚠ NOT «שיוך»: the commit Button beside it is «שיוך», so two controls in
    // one card would carry one accessible name (WCAG 4.1.2). The Select names
    // WHAT is being chosen and the Button names the ACT, which is also how the
    // skip pair reads.
    "atelier.assignLabel": "תופרת",
    "atelier.assignAria": "תופרת — {{name}}",
    "atelier.assignCommit": "שיוך",
    "atelier.assignCommitAria": "שיוך — {{name}}",
    // A seamstress's single control on an unassigned ticket — she takes it. Two
    // syllables, because it lives under a thumb. Not «שייך לי», which is an
    // administrative act on a record.
    "atelier.claim": "לקחת",
    "atelier.claimAria": "לקחת — {{name}}",
    "atelier.release": "לשחרר",
    "atelier.releaseAria": "לשחרר — {{name}}",
    "atelier.edit": "עריכה",
    "atelier.editAria": "עריכה — {{name}}",
    // The card's destructive trigger AND the confirm dialog's confirm button.
    // There is no un-delete.
    "atelier.delete": "מחיקה",
    "atelier.deleteAria": "מחיקה — {{name}}",

    // On EVERY card — it is the priority key the whole epic subtracts from.
    // «יעד», the target date, not «תאריך» alone (which says nothing) and not
    // «למסירה» (which would put a delivery word on four columns that have
    // delivered nothing).
    "atelier.dueDate": "יעד {{date}}",
    // ⚠ THE WORD IS THE SIGNAL AND THE COLOUR IS REINFORCEMENT. Never rendered
    // on a delivered ticket: a garment delivered late is history, not a thing to
    // chase.
    "atelier.overdue": "באיחור",
    // Muted words, not a red flag — unassigned is the normal state of a ticket
    // ten seconds old, and it is what a seamstress is looking for when she
    // claims. Also the release option in the elevated assign Select.
    "atelier.unassigned": "לא משויך",
    // The `assignable: false` branch. THE FLAG IS ON THE WIRE, so this is a fact
    // and not an inference from absence: F51's staff CRUD can re-role or retire
    // a seamstress and knows nothing about this table.
    "atelier.assigneeInactive": "תופרת שאינה פעילה",
    "atelier.band.thirtyMin": "חצי שעה",
    // The intake form's default — the middle-low value, because a default of
    // «יום מלא» inflates every estimate in the boutique and «חצי שעה» deflates
    // it.
    "atelier.band.oneHour": "שעה",
    "atelier.band.twoHours": "שעתיים",
    // ⚠ The band whose tenant mapping is most likely to be wrong — "half-day" is
    // not 240 minutes in a boutique whose shifts are six hours — and F41 ships
    // no editor for the mapping. Which is what `bandOption` below is for.
    "atelier.band.halfDay": "חצי יום",
    "atelier.band.fullDay": "יום מלא",
    // The <option> label: the word AND its tenant-resolved minutes, so an owner
    // discovers on day one that the platform thinks her half-day is four hours
    // rather than in F42's load bars three weeks later.
    //
    // ⚠ An <option> takes no markup, so no isolation helper is available. The
    // string is built so the numeric run is BRACKETED BY HEBREW ON BOTH SIDES,
    // which is what makes the bidi resolution safe without markup — a string
    // ending in the number would put a neutral run at the paragraph edge.
    "atelier.bandOption": "{{band}} · {{minutes}} דק׳",
    // The CARD's effort word when a stored `effort_minutes` matches no current
    // band: a boutique re-tuned «חצי יום» after the ticket was estimated. The
    // visible consequence of "minutes persist, never the label" — a ticket
    // estimated under the old mapping must not be silently re-valued.
    "atelier.effortMinutes": "{{minutes}} דק׳",

    // The announced cues. USER-INITIATED ONLY — the poll produces nothing here.
    //
    // ⚠ THE NAMING RULE: a cue names the TICKET only when the ticket moved out
    // from under the user; when the card stays put, focus is the referent and
    // the cue names only the new value. What that buys mechanically is that
    // every cue carries AT MOST ONE interpolated user value, so the shipped
    // isolateBidi(text, value) and the shipped { text, name } state shape work
    // unmodified and no second helper is invented.
    "atelier.loading": "טוען את לוח התפירה…",
    // The dialog returns focus to «כרטיס חדש» and NOT to the new card, so this
    // is the only thing that says which ticket was opened.
    "atelier.cue.created": "{{name}} — נפתח כרטיס.",
    // ⚠ WRITTEN LATE, and its absence WAS the defect: `setCue` sat inside the
    // create branch, so editing a ticket was the one mutation on this board that
    // announced nothing at all. A sighted user sees the dialog close; without
    // this string a screen-reader user gets silence she cannot tell from a
    // failed save.
    //
    // It NAMES the ticket even though the card does not move, which is the one
    // place the naming rule above is deliberately not followed: an edit replaces
    // five fields at once, so there is no single «new value» to name in its
    // place — and native <dialog> hands focus back to «עריכה», a control whose
    // own accessible name is «עריכה — {{name}}», so the two agree.
    "atelier.cue.updated": "{{name}} — הכרטיס עודכן.",
    // ⚠ THE SINGLE MOST IMPORTANT STRING IN THIS BLOCK: for a sighted user the
    // move is self-evident because the card is visibly in another column, and
    // FOR A SCREEN-READER USER THIS SENTENCE IS THE MOVE.
    //
    // ⚠ Not «הועבר ל{{stage}}»: the five stage words are past-tense verbs and an
    // adjective, and «ל» does not prefix them — «הועבר לבעבודה» is
    // ungrammatical. The colon construction is word-agnostic, so a sixth stage
    // can never break it.
    "atelier.cue.advanced": "{{name}} — שלב חדש: {{stage}}.",
    // The half where the grammar actually breaks in production: undoing
    // `in_progress` returns the ticket to «התקבל», and «הוחזר להתקבל» is the
    // commonest undo there is.
    "atelier.cue.undone": "{{name}} — חזרה לשלב: {{stage}}.",
    // ⚠ ONE name, not two. The card does not move on an assign, so focus is
    // still on it and the ticket is already the referent — and naming both would
    // put TWO user-supplied names in one string, which isolateBidi(text, value)
    // cannot isolate without a second helper.
    "atelier.cue.assigned": "שויך ל{{seamstress}}.",
    // No interpolation at all — the card did not move, focus is on it, and there
    // is no new value to name.
    "atelier.cue.released": "השיוך בוטל.",
    // The card is gone and focus is on a column heading, so nothing else can say
    // which ticket left.
    "atelier.cue.deleted": "{{name}} — הכרטיס נמחק.",

    "atelier.form.editTitle": "עריכת כרטיס",
    // CREATE MODE ONLY. A ticket opened for the wrong bride is a delete, not an
    // edit, so in edit mode the customer renders as a static line and not a
    // field — which is also what the server's UpdateTicketRequest allows.
    "atelier.form.customerName": "שם הלקוחה",
    "atelier.form.customerPhone": "טלפון",
    // ⚠ Appears the moment the phone parses to a customer whose stored name
    // differs from what she typed. `upsert` rewrites `customers.name`
    // UNCONDITIONALLY and F53 renders that name on a screen of its own, so a
    // seamstress typing «מיכל» for a customer stored as «מיכל לוי» must not do
    // that invisibly. A notice, not an error: nothing is wrong, something is
    // about to change.
    // Defaults to EMPTY, never to today — a due date is the one field a hurried
    // user must not be able to accept by not looking at it.
    "atelier.form.dueDate": "תאריך יעד",
    // ⚠ A WARNING, NEVER A BLOCK, and the server agrees: there is no lower bound
    // and a past date is a 200 on create and on update. A dress that was due
    // yesterday is exactly the ticket a boutique most needs to open. The second
    // sentence is what stops it reading as an error.
    "atelier.form.pastDue": "התאריך שנבחר כבר עבר. אפשר להמשיך.",
    // «הערכה» is the honest word — the epic's central accepted risk is that
    // these estimates are wrong, and a label reading «זמן עבודה» would state as
    // fact what the whole epic treats as a guess.
    "atelier.form.effortBand": "הערכת זמן",
    // ⚠ The catalog dress Select is CUT from F41 (C3): the board payload carries
    // no dresses, the only source is a route gated to owner + shift manager
    // while this dialog admits a seamstress, and the card renders no image, so
    // `dress_id` has no reader on this surface. The free-text field ships alone
    // and unconditionally; `atelier.form.dress` and `atelier.form.dressNone` are
    // deliberately absent. F43 is the caller that will send a `dress_id`.
    "atelier.form.dressName": "שם השמלה",
    // Free text, never validated against `dress_variants` — a seamstress records
    // what she measured («38, מותן מוקטן»), not a stock bucket.
    "atelier.form.dressSize": "מידה",
    // ⚠ The field most likely to hold a bride's measurements, which is the most
    // intimate data this platform will ever carry — and it is why the label is a
    // neutral «הערות» rather than anything that invites them.
    "atelier.form.notes": "הערות",
    "atelier.form.notesHelp": "מה צריך לעשות בשמלה.",
    "atelier.form.submitCreate": "פתיחת כרטיס",
    "atelier.form.submitEdit": "שמירה",
    // The dismiss on BOTH dialogs. Esc and the backdrop do the same thing, and
    // never the confirm.
    "atelier.form.cancel": "ביטול",

    // Field validation, refused before the request. The register is fix-this, so
    // every one names what to do and none apologises.
    "atelier.form.error.customerName": "צריך שם לקוחה.",
    "atelier.form.error.customerPhone": "מספר הטלפון אינו תקין.",
    "atelier.form.error.dueDate": "צריך תאריך יעד.",
    "atelier.form.error.dressName": "שם השמלה ארוך מדי.",
    "atelier.form.error.dressSize": "המידה ארוכה מדי.",
    "atelier.form.error.notes": "ההערות ארוכות מדי.",
    // ⚠ The dialog-level alert, for a server refusal that maps to no field: an
    // unknown band key, a `dress_id` 404, a due date past the server's 730-day
    // typo fence. There is deliberately NO client string quoting that number —
    // it is a SERVER bound and no client constant may mirror one. This is also
    // what keeps main.py's ENGLISH 400 body out of a Hebrew dialog.
    "atelier.form.error.server": "הפעולה נדחתה. כדאי לבדוק את הפרטים ולנסות שוב.",

    // ⚠ The first thing every new boutique sees on this screen, so it is
    // designed rather than blank: the five columns and the rail are replaced
    // entirely, because five headings each reading «אין כרטיסים בשלב זה» is a
    // wall of nothing that looks broken. «עדיין» is doing real work — it says
    // NOT YET, not NOT EVER.
    "atelier.empty": "אין עדיין כרטיסי תפירה",
    // THE ONLY PLACE IN THE PRODUCT WHERE THE FIVE STAGES ARE TAUGHT IN ONE
    // SENTENCE — what the replaced columns would have taught, at the cost of
    // looking broken, delivered as a sentence instead. It must name all five, in
    // order, in the same words the columns use.
    "atelier.emptyBody":
      "כל כרטיס עובר חמישה שלבים: התקבל, בעבודה, בקרה, מוכן, נמסר. אפשר לפתוח את הכרטיס הראשון עכשיו.",
    // ⚠ The console never states the NUMBER: the limit is server-only and the
    // `truncated` flag is on the wire precisely so it stays that way — a client
    // that quoted 500 would be one constant away from lying. Ordering is
    // due_date ascending, so what is missing is the LEAST urgent, and the copy
    // says so rather than leaving her to wonder which end was cut.
    "atelier.truncated":
      "מוצגים הכרטיסים הדחופים ביותר. כרטיסים רחוקים יותר אינם מוצגים כאן.",
    // ⚠ DECLARED, not reused. F57's rule is «reuse a key whose NAMESPACE NAMES
    // ITS SUBJECT, never one whose namespace names a screen» — `staff.loadFailed`
    // is the staff list and `board.*` names a screen, so `atelier.*` being the
    // subject namespace here makes declaring it that rule OBEYED.
    "atelier.loadFailed": "לא הצלחנו לטעון את לוח התפירה כרגע.",
    // The session outlives a shift by design (12 hours, no sliding renewal), so
    // the realistic reader is a phone left on a bench overnight — a plain
    // instruction, not an alarm.
    "atelier.sessionEnded": "תוקף החיבור פג. צריך להתחבר מחדש.",
    // ⚠ DELIBERATELY GENERIC. The server ships ONE 403 body for every unadmitted
    // role so a probe cannot learn which roles exist; naming a role, or saying
    // what changed, would be an invention the server never made — and on the
    // demotion path it would be the product telling a staffer she was demoted,
    // which is her manager's sentence to say, not a screen's. «כרגע» is doing
    // real work: a re-promotion restores the board.
    "atelier.accessEnded":
      "אין הרשאה לצפות בלוח התפירה כרגע. לבירור אפשר לפנות לבעלת הבוטיק.",
    // On the 401 a reload lands on the login screen; on the 403 it lands on a
    // console whose board answers 403 again — the honest behaviour of "a
    // demotion bites on the very next request", inherited rather than papered
    // over.
    "atelier.reload": "רענון הדף",

    // Two error codes and not one, because the user's next move differs: a
    // garment moved on and she should look again; a person took it and the next
    // tick will name her. All four name the EVENT that repairs them and never a
    // duration.
    "atelier.error.stageConflict": "הכרטיס כבר התקדם. הלוח יתעדכן בעדכון הבא.",
    // Does NOT name the winner: the console does not have her name at the moment
    // of the refusal, and the next tick renders it on the card.
    "atelier.error.alreadyAssigned": "הכרטיס כבר משויך. הלוח יתעדכן בעדכון הבא.",
    // A mutation on a ticket deleted in the gap between the last tick and the
    // tap. NOT terminal — a ticket vanishing is a fact about the ticket, not
    // about her access.
    "atelier.error.notFound": "הכרטיס כבר לא קיים. הלוח יתעדכן בעדכון הבא.",
    // ⚠ THE DEFAULT BRANCH, and it is structural rather than cosmetic: it
    // guarantees no English body can reach this console from any code F41 or a
    // later feature adds. A per-code string would leave the next new code
    // uncovered.
    "atelier.error.rejected": "הפעולה נדחתה. הלוח יתעדכן בעדכון הבא.",

    "atelier.deleteConfirmTitle": "מחיקת כרטיס",
    // Two sentences, and the second is the whole reason this dialog exists:
    // there is no un-delete, so a ticket removed by mistake is recoverable only
    // through psql. It names the bride because the confirm is being read at the
    // moment the wrong card might be the focused one.
    "atelier.deleteConfirmBody": "הכרטיס של {{name}} יימחק מהלוח. לא ניתן לשחזר אותו.",

    // --- F37: the SOS page ---------------------------------------------------
    //
    // Transcribed from .planning/design/screens/sos-paging/copy.md, which is the
    // single source for BOTH this file and ar.ts. Flat dotted keys, the shipped
    // rooms.* / floor.* shape.
    //
    // ⚠ THE ONE RULE THAT COST THIS FEATURE ITS MOST NATURAL WORD: no string may
    // claim, promise or hedge that a message was sent, in any tense, and
    // i18n.test.ts enforces it as /נשלח|תישלח|בדרך/ over every value. «בדרך» is
    // the natural Hebrew for "on my way", i.e. for the single most important
    // button here. The guard is right and stays — it exists so no string in this
    // console ever promises a message the product did not send, and the product
    // sends none: this feature is in-app only, with no push, no SMS and no bell.
    // Resolved by wording and never by an exception.
    //
    // ⚠ AND NO VALUE BELOW CARRIES A LITERAL DIGIT. Escalation and stall are
    // named as STATES, never as durations: `escalated` is an unbounded boolean,
    // so «ללא מענה כבר 30 שניות» would state a flat thirty seconds to a shift
    // manager looking at a four-minute-old page, and in the SOS centre it would
    // sit beside the elapsed line's «זה עתה» at t=31s.

    // The card's first lines ARE the role="alert" region's children, so what is
    // written here is exactly what a screen reader announces, once, on mount, as
    // one atomic utterance. Nothing in this group may re-render with a different
    // value on the same card or the whole card is re-announced assertively.
    //
    // Present tense and continuous — she is calling NOW. «קוראת לעזרה» rather
    // than «צריכה עזרה»: the first is an act aimed at the reader, the second is
    // a condition.
    "sos.calling": "{{name}} קוראת לעזרה",
    // Substituted into {{name}} when the raiser's staff row was removed
    // mid-page. ⚠ FEMININE, which is why the ghost case needs no parallel key
    // anywhere: «אשת צוות שאינה ברשימה קוראת לעזרה» is grammatical. Indefinite
    // «אשת צוות», not F36's definite «אשת הצוות» — nothing on this card has
    // named her before.
    "sos.raiserGone": "אשת צוות שאינה ברשימה",
    // ⚠ A LABEL, not a copy of a value, rendered sr-only INSIDE the region
    // before the bare room label. The room label is unconstrained free text — a
    // boutique that types «2» is fully supported — so without it the atomic
    // utterance is «דנה כהן קוראת לעזרה 2 צריך סיכות». NOT an aria-label on the
    // paragraph: ARIA prohibits naming a generic element, so that would ship a
    // name nothing reads.
    "sos.roomA11yPrefix": "מיקום",
    // The room line when there is no room, which is ordinary rather than an
    // edge: a seamstress at her table. The room pointer is deliberately
    // permissive server-side so a stale or foreign id lands here rather than
    // sending a responder to a stranger's curtain.
    "sos.noRoom": "לא בחדר מדידה",
    // ⚠ A SIBLING, outside the announced region, and ABSOLUTE. No countdown and
    // no live counter anywhere in this feature: a ticking number inside a
    // role="alert" re-announces on some screen readers and would drag SC 2.2.2
    // onto a region whose whole argument is that it has nothing to pause.
    "sos.since": "מאז {{time}}",
    // ⚠ A SIBLING too, for the same reason. «ללא מענה» describes the alert's
    // current state, which is what a shift manager triages on; «לא נענתה» would
    // describe a completed non-event.
    "sos.escalated": "ללא מענה",
    // The second silence — accepted and unresolved — and the one thing between
    // «דנה מגיעה» and an emergency nobody is answering. «מאז שאושרה» names the
    // event, not a clock.
    "sos.stalled": "אין תזוזה מאז שאושרה",

    // ⚠ THE SINGLE MOST IMPORTANT BUTTON IN THIS FEATURE, and NOT «אני בדרך».
    // First-person and present-continuous, and it commits her: «בסדר» or
    // «קיבלתי» would acknowledge a MESSAGE; this acknowledges a PERSON, and the
    // raiser is told the same word back one line below.
    "sos.accept": "אני מגיעה",
    // Several cards can be up at once and «אני מגיעה» three times is a screen
    // reader dead end. Starts with the visible label (WCAG 2.5.3, Level A) and
    // takes no markup, so the interpolated name needs no bidi treatment.
    "sos.acceptAria": "אני מגיעה — הקריאה מ{{name}}",
    // Per-device and in-memory: the alert stays open, keeps escalating and comes
    // back on reload, because if it is still open it is still an emergency.
    // «הסתרה» and not «סגירה» or «ביטול», both of which would claim it closed.
    "sos.dismiss": "הסתרה",
    "sos.dismissAria": "הסתרה — הקריאה מ{{name}}",

    // The two app-level surfaces, which exist because on the eleven sections
    // with no SOS centre there is no other region that could say this.
    //
    // Rendered on a 403 on the poll (⚠ terminal access, NOT a logout) or on a
    // loop backed off beyond one tick. «Nothing renders» is not an acceptable
    // state for an emergency receiver that has stopped receiving. It states the
    // fact and nothing else: no apology, no guessed cause, no named interval.
    // «ערוץ הקריאות» rather than «המערכת» — what is dead is this channel, not
    // the console she is still using.
    "sos.channelDown": "ערוץ הקריאות אינו פעיל.",
    // ⚠ «רענון הדף» and NOT «רענון». The latter is floor.refresh, a different
    // act — refetch the list — offered by a different control; this strip's only
    // remedy is a page reload, and a button labelled «רענון» that reloads the
    // whole page is a promise the word does not make. Its own key rather than a
    // reuse of floor.reload because the strip renders on eleven sections where
    // no floor.* string otherwise appears.
    "sos.channelReload": "רענון הדף",
    // The persistent affordance that re-opens a dismissed but still LIVE alert.
    // Without it a dismissal on any of the eleven sections with no SOS centre is
    // total and permanent — and the role-targeted route is the raise dialog's
    // default, so that is the common path and not an edge.
    "sos.dismissedCount": "קריאות עזרה · {{count}}",

    // The SOS centre, on the two sections that have one.
    "sos.centreHeading": "קריאות עזרה",
    // ⚠ The state this panel is in almost always, which is why it is one muted
    // line and not an EmptyState: 140px announcing that there is no emergency
    // would make the absence of an emergency the visual centre of the floor
    // screen. «אין עכשיו» — not right now, a state — rather than «אין», which
    // reads like a fault or an empty registry.
    "sos.centreEmpty": "אין עכשיו קריאות פתוחות.",
    // The row's single Badge. The WORD carries the state; the colour never does
    // — and on a full-screen red field that is not a formality.
    "sos.statusOpen": "פתוחה",
    // «מטופלת» — being handled — rather than «התקבלה», which would say only that
    // somebody pressed a button.
    "sos.statusAccepted": "מטופלת",
    // ⚠ THE RAISER'S ANSWER, and the reason the tick drops to two seconds. The
    // SAME VERB as the button, deliberately: she pressed «אני מגיעה» and the
    // raiser reads «דנה כהן מגיעה.» — one word, two screens, no translation
    // between them.
    //
    // ⚠ AND THE CLAIM IS DELIBERATELY STRONGER THAN THE FACT. The product knows
    // an INTENTION — a button was pressed — and not a walk down a corridor. The
    // alternative «{{name}} אישרה את הקריאה.» is system register on the one
    // screen that must read like a person. What bounds the claim is the stall
    // predicate at two minutes: if nothing moves, the card re-rises.
    "sos.acceptedBy": "{{name}} מגיעה.",
    // The acceptor's staff row was removed between her accept and this read. A
    // sentence that admits it does not know beats «‎ כבר מגיעה.» with an empty
    // interpolation on a legally binding surface.
    "sos.acceptedByUnknown": "מישהי כבר מגיעה.",
    // «נפתר» — the EMERGENCY resolved, not "the task completed" — and it is
    // deliberately the same word the cancel refusal points at.
    "sos.resolve": "נפתר",
    "sos.resolveAria": "נפתר — הקריאה מ{{name}}",
    // Rendered for the raiser or an elevated caller and only while the alert is
    // open. «ביטול הקריאה» rather than a bare «ביטול», because on a row that
    // also offers «נפתר» the reader must be able to tell "never mind" from "it
    // is over".
    "sos.cancel": "ביטול הקריאה",
    // ⚠ The bare em-dash shape here and not «— הקריאה מ{{name}}»: the visible
    // label already ends in «הקריאה», and the accessible name would otherwise
    // read «ביטול הקריאה — הקריאה מדנה».
    "sos.cancelAria": "ביטול הקריאה — {{name}}",

    // BOTH raise triggers, one string — the room tile's fourth control and the
    // SOS centre's heading-row trigger. Two keys holding one value are two
    // things to keep true and twice the hand transcription into ar.ts. «קריאה
    // לעזרה» and not «SOS»: the console ships no Latin abbreviation and a screen
    // reader would spell it.
    "sos.raise": "קריאה לעזרה",
    // The TILE trigger's accessible name only — one tile per room and the
    // visible label repeats. ⚠ Em-dash, value LAST: the boutique's own label
    // carries its own noun, so «קריאה לעזרה מחדר {{room}}» would render «מחדר
    // חדר 2».
    "sos.raiseAria": "קריאה לעזרה — {{room}}",

    // The raise dialog.
    //
    // Same words as the trigger, its own key: a heading and a button label are
    // different roles and diverge the first time anybody edits one.
    "sos.title": "קריאה לעזרה",
    // The Select's LABEL, never a placeholder. A question, because that is what
    // she is answering under pressure. «למי לקרוא» and not «נמענת» or «יעד» —
    // system words on the one screen that must read like a person.
    "sos.targetPick": "למי לקרוא",
    // ⚠ The first option and the DEFAULT: the FALLBACK route, so it is the one
    // choice a staffer under pressure never has to think about. The role, not a
    // name, because that is what the column means. Its audience is not probed
    // and can be empty — spec Risk 3(a) — so "never has to think about" is about
    // the CHOICE and is not a delivery guarantee.
    "sos.targetManager": "מנהלת המשמרת",
    // The Input's LABEL. Four words is what a staffer holding a corset will
    // type, so it asks for a thing and not a sentence: «מה צריך» and not
    // «הערה», which invites prose.
    "sos.notePick": "מה צריך",
    // ⚠ It matters more here than anywhere else in the console: a staffer who
    // believes the field is required will type something rather than tap send,
    // and this is the one screen where two seconds is real.
    "sos.noteOptional": "לא חובה",
    // ⚠ «שליחת» is ש-ל-י-ח-ת and trips neither ban term. Checked, because it
    // LOOKS like it should. The verb is safe precisely because it describes the
    // act she is performing now, not a message the product claims to have
    // delivered.
    "sos.send": "שליחת הקריאה",

    // The five cues. ⚠ They render in TWO different regions and that is
    // deliberate: the SOS centre writes them into FloorPanel's single
    // role="status", the overlay passes them to the app-level toast — because on
    // the eleven sections with no centre there is no status region at all, and
    // an accept would otherwise produce nothing but a red field disappearing.
    //
    // ⚠ «נרשמה», NEVER «נשלחה», and the wording is honest as well as compliant:
    // what happened is that a ROW WAS WRITTEN, and whether a phone lights up
    // depends on a colleague having a console open, which the product cannot
    // promise.
    "sos.raisedCue": "הקריאה נרשמה.",
    "sos.acceptedCue": "הקריאה התקבלה.",
    "sos.resolvedCue": "הקריאה נסגרה.",
    "sos.cancelledCue": "הקריאה בוטלה.",
    // ⚠ «הוסתרה» and not «נסגרה»: the alert is untouched on the server. A cue
    // that said "closed" would be the one lie this feature cannot afford.
    "sos.dismissedCue": "ההתראה הוסתרה.",
    // ⚠ THE RAISE DIALOG'S BODY on a rerouted raise, not a transient cue — the
    // dialog stays open and she must acknowledge it. Delivering the one message
    // the ruling mandates as a polite cue, into a region the next cue
    // overwrites, at the exact moment a dialog closes and focus moves, is the
    // classic case AT drops — and it is unrecoverable, because `rerouted` is a
    // fact about the REQUEST, so no centre row can ever say it again. Two
    // sentences: what is not true, then what is. «לא מחוברת» rather than «לא
    // בעבודה» — the product knows about sessions, not shifts.
    "sos.rerouted": "{{name}} לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת.",
    // «הבנתי» is an acknowledgement rather than a dismissal, which is the right
    // interaction weight for a message the product needs her to have read.
    "sos.reroutedAck": "הבנתי",

    // The errors.
    //
    // The ruling's "a 409 NAMING THE OWNER", rendered. She has not lost
    // anything — somebody is going.
    "sos.error.SOS_ALREADY_ACCEPTED": "{{name}} כבר מגיעה.",
    // The same 409 with the details key absent.
    "sos.error.alreadyAcceptedUnknown": "מישהי אחרת כבר מגיעה.",
    // Two codes and not one with a discriminating details: two causes, two
    // sentences, TWO REMEDIES — go somewhere else, versus there is nothing to
    // do.
    "sos.error.SOS_CLOSED": "הקריאה כבר נסגרה.",
    // ⚠ The asymmetry with resolve is the point: a colleague is already walking
    // to that curtain, and silently cancelling would send her to an empty room
    // and teach her that accepting means nothing. So the sentence carries the
    // remedy, and the remedy is one word over.
    "sos.error.cancelAfterAccept": "{{name}} כבר מגיעה. אפשר לסמן «נפתר» במקום.",
    "sos.error.cancelAfterAcceptUnknown": "מישהי אחרת כבר מגיעה. אפשר לסמן «נפתר» במקום.",
    // The alert was swept or never existed. NOT terminal, and it names the
    // EVENT that repairs it rather than a duration.
    "sos.error.notFound": "הקריאה כבר לא פתוחה. הרשימה תתוקן בעדכון הבא.",
    // Unreachable client-side, because the note input caps at
    // MAX_SOS_NOTE_LENGTH. The string exists anyway: the server's rule is the
    // real one.
    "sos.error.noteTooLong": "ההודעה ארוכה מדי.",
    // Unreachable too — the dialog excludes her from the target list, which
    // PREVENTS the error rather than explaining it.
    "sos.error.selfTarget": "אי אפשר לקרוא לעצמך.",
    // ⚠ The send did not complete — a 5xx, a dropped connection, a wifi
    // blackspot inside a curtain, which is the single most likely real-world
    // failure of a phone held behind a closed fitting-room curtain. Without this
    // key the console falls through to the generic «נסי שוב» on the one screen
    // where that alone is the wrong instruction. THE ONLY STRING IN THIS CONSOLE
    // THAT NAMES THE MANUAL FALLBACK OUT LOUD.
    "sos.error.raiseFailed": "הקריאה לא נרשמה. נסי שוב — או קראי בקול.",
    // ⚠ Deliberately does NOT name the fallback, and the distinction is real: a
    // failed accept means only that SHE did not claim it — the alert is still
    // open, still rising on every other targeted device and still escalating —
    // so nothing has been dropped and «נסי שוב» is exactly right.
    "sos.error.actionFailed": "הפעולה לא הושלמה. נסי שוב.",
    // --- F42, the seamstress panel. 40 keys, 7 reused from F41 above. --------
    //
    // The reused seven are `form.cancel` (both dialogs' dismiss), the five
    // `band.*` words (one vocabulary for the five bands across the intake form,
    // the card, the picker AND the editor that sets them) and
    // `assigneeInactive`. They are NOT re-declared here: one act, one word.
    //
    // ⚠ THE PANEL STATES, IT DOES NOT REASSURE. A shift manager reads it fifty
    // times a shift, so there is no «הכל תקין» and no «מעולה» — and on an
    // overload row warmth would be worse than noise.
    //
    // ⚠ NO VALUE BELOW MAY CONTAIN «168» OR «1440». They are
    // MAX_WEEKLY_CAPACITY_HOURS and MAX_BAND_MINUTES — SERVER bounds — and a
    // Hebrew sentence quoting one is a mirror exactly as much as a TypeScript
    // constant is, with none of the protection:
    // test_frontend_constant_parity.py scrapes only the two validation.ts
    // files, so raising the DB CHECK to 200 would leave the sentences lying,
    // silently and greenly. F41 declared `form.error.dueDateHorizon` and cut it
    // at review for this exact rule. The copy states the SHAPE of the mistake;
    // the server's 400 states the range. The one numeral rendered anywhere here
    // is `capacity.hoursHelp`'s `{{hours}}`, and it is a TENANT's value read off
    // the board envelope.
    //
    // ⚠ Nothing in F42 sends, notifies, texts or delivers anything. There is no
    // SMS template, no scheduled message and no «נודיע לתופרת» — which is
    // exactly the sentence a well-meaning editor would add to an overload cue,
    // and it would be a lie before it was a red.

    // The <ul>'s aria-label, and it is the UNCOUNTED one on purpose: an
    // accessible name must not churn on a five-second tick, and this count CAN
    // change with no staff edit — `seamstresses` is a union, so a retired
    // assignee leaves it the moment her last undelivered ticket is delivered.
    // Never rendered as visible text.
    "atelier.capacity.heading": "תופרות",
    // The visible <h3>, and the COUNTED twin. The count is what tells a
    // screen-reader user the list is long BEFORE she enters it — F41's column
    // headings do the same job.
    //
    // ⚠ `{{total}}` is `seamstresses.length` — PEOPLE, not rows — which is why
    // the unassigned total below is a <p> OUTSIDE the list. ⚠ `{{total}}`, never
    // `{{count}}`: `count` is i18next's plural-resolution trigger. ⚠ And no noun
    // follows the number — «{{total}} תופרות» is wrong at 1 and wrong at 2
    // (Hebrew takes a dual), and doing it properly needs four plural suffixes
    // per string in two bundles. The noun leads, so no agreement question
    // arises. The « · » has shipped precedent in `atelier.stageCount`.
    "atelier.capacity.headingCount": "תופרות · {{total}}",
    // The whole list replaced, when the boutique has no seamstresses at all.
    // Read by a shift manager or a seamstress: a plain fact and no instruction,
    // because the only remedy is on a screen the gate refuses her.
    "atelier.capacity.empty": "אין תופרות רשומות.",
    // ⚠ TWO KEYS AND NOT ONE. The staff screen is owner-only, and a line telling
    // a shift manager to go somewhere the gate refuses is this console lying
    // about its own permissions. «במסך הצוות» names the destination in the word
    // the nav row uses.
    "atelier.capacity.emptyOwner": "אין תופרות רשומות. אפשר להוסיף במסך הצוות.",
    // The work nobody holds — a <p> AFTER </ul>, never an <li>, and carrying no
    // bar: nobody has capacity for it, so there is no denominator and a bar
    // would be a ratio to nothing. ⚠ `{{hours}}` is the WHOLE unassigned
    // backlog, not the seven-day slice — the row has no rate to compare
    // against, and «בתור» on the seamstress rows already means that quantity.
    // Rendered only above zero: a zero line is noise on every board that is
    // fully assigned.
    "atelier.capacity.unassignedRow": "לא משויך · {{hours}} שעות",

    // ⚠ THE BAR IS aria-hidden AND CARRIES NO ROLE, NO NAME AND NO VALUE.
    // Everything it shows is in the six strings below, more precisely. A
    // screen-reader user hears the row and loses nothing; a user in forced
    // colours or greyscale reads the row and loses nothing. That is what
    // "overload is never colour-only" means concretely.
    //
    // The clauses assemble in this order and no other, joined by « · »:
    //   {load | loadNoCapacity + notSet}  [· over]  [· backlog]  [· fromDefault]
    // The alarm as early as the grammar allows, the qualifier last.

    // The bar's own numbers, in words: X hours' worth due by {{date}}, out of Y.
    // ⚠ `{{date}}` comes from the WIRE and never from the device — the server
    // filtered on its own today_jerusalem + 7, lib/jerusalem.ts ships no date
    // arithmetic, and a device that has crossed Jerusalem midnight would print
    // a horizon the SQL did not use.
    "atelier.capacity.load": "{{hours}} שעות עד {{date}} מתוך {{capacity}}",
    // The load half for a seamstress with NO resolved capacity — no bar is
    // drawn, so there is no denominator to name and no horizon to divide into.
    // ⚠ `{{hours}}` is her whole backlog here, which is what makes an
    // unconfigured row comparable with a configured one's «בתור» clause.
    "atelier.capacity.loadNoCapacity": "{{hours}} שעות",
    // ⚠ THE SINGLE MOST LIKELY STATE IN WEEK ONE, AND IT MUST NOT READ AS AN
    // ERROR. No «חסר», no danger colour: it is a fact about configuration, in
    // the muted register, with the fix one tap away. «לא הוגדרה» agrees with
    // «קיבולת», feminine.
    "atelier.capacity.notSet": "לא הוגדרה קיבולת",
    // ⚠ THE SINGLE MOST IMPORTANT STRING IN THIS BLOCK. For a sighted user the
    // bar turning red is the signal; FOR A SCREEN-READER USER, AND FOR ANYONE IN
    // GREYSCALE OR FORCED COLOURS, THESE TWO WORDS ARE THE OVERLOAD. Rendered as
    // a <strong> inside the row's one <p> — never a second Badge, which would
    // split the sentence into two announced chunks and put a second badge
    // vocabulary above sixty of F41's cards.
    //
    // Not «עמוסה» (an adjective about her, and this is a fact about her queue)
    // and not «חריגה» (a violation, and nothing here is refused). The same two
    // words in all three renderings — the row, the option and the cue — because
    // a manager who reads it on a row and hears it on a cue must not have to
    // work out that they are the same fact.
    "atelier.capacity.over": "עומס יתר",
    // The queue clause: the sum of ALL her undelivered effort with no date
    // predicate, so the total is never hidden behind the bar's seven-day slice.
    // «סה״כ» marks it as the larger figure and «בתור» as waiting rather than due.
    "atelier.capacity.backlog": "סה״כ {{hours}} שעות בתור",
    // The last clause, when the resolved number came from the BOUTIQUE's default
    // rather than from her own row. The number is honest about whose it is — a
    // manager reallocating work must know whether 30 is a fact about this
    // seamstress or a fact about the shop. Never rendered when she has her own.
    "atelier.capacity.fromDefault": "ברירת מחדל של הבוטיק",

    // The row's trigger, ghost, ELEVATED ONLY and absent on an assignable:false
    // row — the server refuses her and a control that always 400s is a trap.
    // One word, because it lives under a thumb in a 295px row beside a name
    // that may wrap.
    "atelier.capacity.edit": "שעות",
    // Its per-row accessible name. A six-row panel otherwise exposes six buttons
    // all named «שעות» and a screen-reader user pulling up the control list
    // cannot address one. STARTS with the visible label so 2.5.3 holds and a
    // speech-input user saying «שעות» still matches. An aria-label takes no
    // markup, so {{name}} interpolates plainly.
    "atelier.capacity.editAria": "שעות — {{name}}",
    // Names the quantity, not the person: the row she came from is still on
    // screen behind the dialog, and the name here would change the title on
    // every open for no gain.
    "atelier.capacity.dialogTitle": "שעות שבועיות",
    "atelier.capacity.hoursLabel": "שעות בשבוע",
    // The help line when the boutique HAS a default. It states the one rule that
    // makes the dialog legible: an empty field means "use the boutique's
    // number", in both directions. `{{hours}}` is the TENANT's value off the
    // envelope, not a server bound.
    "atelier.capacity.hoursHelp": "ריק — חזרה לברירת המחדל של הבוטיק: {{hours}} שעות.",
    // ⚠ The same line on a boutique with NO default, which is every boutique on
    // day one. The string above would promise a fallback that does not exist —
    // two keys, because one of them would be a lie exactly when it is read most.
    "atelier.capacity.hoursHelpNoDefault": "ריק — לא תוגדר קיבולת.",
    // ⚠ A ghost Button in the dialog BODY, under the field, and it CLEARS the
    // field — it does not submit. Modal's footer is `flex justify-end gap-3`
    // with no wrap and no className seam, so a third footer button of five
    // Hebrew words overflows 295px at 375. Clearing rather than submitting keeps
    // one submit path, one confirm and one error path.
    "atelier.capacity.useDefault": "חזרה לברירת המחדל",
    // Byte-identical to `settings.submit` and to the shipped `form.submitEdit`,
    // and DECLARED SEPARATELY under the namespace that names its subject:
    // saving a person's hours, saving the boutique's ruler and saving a ticket
    // are three facts. F41's F-9 records this duplication pattern as deliberate.
    "atelier.capacity.submit": "שמירה",
    // Rides the field's own `error` prop, which wires aria-describedby +
    // role="alert". Names the SHAPE of the number, never its range — no numeral,
    // ever. «ולא שלילי» rather than «חיובי», because 0 is legal and is not a
    // typo: a shift manager setting 0 is saying she is not available this week,
    // which is a thing this product should be able to say.
    "atelier.capacity.error.hours": "צריך מספר שעות שלם ולא שלילי.",
    // ⚠ The Hebrew default: branch, and it is structural rather than cosmetic.
    // main.py's error bodies are ENGLISH and this console is Hebrew-only; the
    // concrete message this route produces is `_require_seamstress`'s literal
    // "staff_user_id must be a live seamstress". One alert inside the dialog,
    // above the footer — never a toast behind a modal, never error.message.
    "atelier.capacity.error.server": "לא ניתן לשמור את השעות. אפשר לנסות שוב.",
    // Announced in F41's shipped role="status" region after a successful set.
    // Names her, because the dialog has closed and focus has gone back to a
    // trigger that says only «שעות».
    "atelier.capacity.cue.saved": "{{name}} — עודכנו השעות.",
    // ⚠ A DIFFERENT SENTENCE AND NOT A PARAMETER: the outcome differs in a way
    // she must hear — her own number is gone and the boutique's applies.
    // «עודכנו השעות» on a clear would be true and useless.
    "atelier.capacity.cue.cleared": "{{name}} — חזרה לברירת המחדל.",

    // ⚠ EVERY PART OF AN ASSIGN OPTION IS A KEY, INCLUDING THE SEPARATOR. F41
    // renders {row.display_name} alone in that <option> and declares no key of
    // this shape, so all three strings would otherwise ship as bare Hebrew
    // literals in TSX — outside the `ar` parity guard, outside the prefix fold,
    // untranslated. ⚠ An <option> takes no markup, so no bidi helper is
    // available anyway: every option string ENDS in a Hebrew word, which is what
    // makes the numeral resolve in place.
    "atelier.capacity.optionRow": "{{name}} · {{detail}}",
    // Group 1 — capacity set, real headroom. The number is WHY the list is in
    // this order: a reordered control with no explanation is a control that
    // shuffles for no reason a user can see.
    "atelier.capacity.optionRemaining": "נותרו {{hours}} שעות",
    // Group 2 — no capacity set, so there is no headroom to state and the only
    // honest number is what she is already holding. ⚠ «משויכות» names
    // `assigned_minutes`, and that is what fixes the sort key for this group: a
    // group ordered by a number none of its options displays is the invisible
    // rule this section exists to avoid.
    "atelier.capacity.optionAssigned": "{{hours}} שעות משויכות",

    // ⚠ THE ONLY THING A SCREEN-READER USER EVER HEARS ABOUT AN OVERLOAD SHE
    // JUST CAUSED. F41's D17 forbids the poll from writing into the announced
    // region, so without this clause a sighted user watches the bar turn red on
    // the next tick and a screen-reader user gets NOTHING AT ALL — on the one
    // action that causes it, on a screen where a11y is a legal bar.
    //
    // Chosen at the moment of the write by wouldOverload(target, effort_minutes)
    // and GATED ON AN ACTUAL MOVE, so re-committing the ticket's current
    // assignee announces the ordinary `atelier.cue.assigned` and never this.
    // Sits beside that key and names ONE user value, which is what keeps the
    // shipped isolateBidi(text, value) and { text, name } cue state working
    // unmodified.
    "atelier.cue.assignedOverload": "שויך ל{{seamstress}} — עומס יתר.",

    // The panel-level trigger, ghost, ELEVATED ONLY, at the panel's FOOT — a
    // boutique-wide configuration used once a quarter must not sit above the
    // rows a manager opens the panel to read.
    "atelier.settings.open": "הגדרות",
    // It must say WHICH settings: «הגדרות» is a word this console uses in more
    // than one place. The `—` shape is the shipped one (`atelier.pauseAria`) and
    // it starts with the visible label so 2.5.3 holds.
    "atelier.settings.openAria": "הגדרות — לוח התפירה",
    // «התפירה» rather than «הלוח», so the dialog names the craft it configures
    // rather than the screen it was opened from — the bands and the default
    // outlive any one board.
    "atelier.settings.title": "הגדרות התפירה",
    // «הערכה» is the honest word: the epic's central accepted risk is that these
    // estimates are wrong, and «זמן עבודה» would state as fact what the whole
    // epic treats as a guess. Same word F41 already uses on the intake form.
    "atelier.settings.bandsLabel": "הערכות זמן",
    // ⚠ A re-tune re-values nothing AND an old card can therefore SILENTLY
    // RELABEL — flattening «יום מלא» onto 240 makes every «חצי יום» garment read
    // «יום מלא», with no fallback and no visible act. This dialog is the only
    // place a human causes that, and without this line an owner correcting one
    // band gets an unexplained change across her board and no way to connect the
    // two. The sentence is true: the minutes on existing tickets do not move.
    "atelier.settings.bandsHelp": "שינוי ההערכות משפיע רק על כרטיסים חדשים.",
    // The <label> of each of the five number fields. `{{band}}` is one of the
    // SHIPPED `atelier.band.*` words — one vocabulary for the five bands. The
    // unit is in the label, so each field holds a bare number.
    "atelier.settings.bandMinutes": "{{band}} — דקות",
    // Named as a DEFAULT rather than as a capacity, because it is not anybody's
    // hours.
    "atelier.settings.defaultCapacity": "ברירת מחדל: שעות בשבוע",
    // States exactly who it applies to, because the alternative reading — "this
    // is everyone's capacity" — would make a manager think editing one row here
    // changes the shop. «שלא הוגדרו לה שעות משלה» is the resolution rule in
    // words.
    "atelier.settings.defaultCapacityHelp": "חלה על תופרת שלא הוגדרו לה שעות משלה.",
    "atelier.settings.submit": "שמירה",
    // ⚠ «חיובי» here and «ולא שלילי» on the capacity field, and the difference
    // is real: a band of 0 minutes is meaningless, a capacity of 0 hours is not.
    "atelier.settings.error.minutes": "צריך מספר דקות שלם וחיובי.",
    // «או ריק» is the third state and it is a VALUE, not an omission — clearing
    // the boutique default is a thing an owner may deliberately do.
    "atelier.settings.error.default": "צריך מספר שעות שלם ולא שלילי, או ריק.",
    // Names the settings, so a manager with both dialogs open in one minute can
    // tell which save failed.
    "atelier.settings.error.server": "לא ניתן לשמור את ההגדרות. אפשר לנסות שוב.",
    // No interpolation at all — the subject is the boutique, not a person, and
    // there is no new value worth naming that the dialog she just closed did not
    // show her. ⚠ This is the sentence BOTH of two shift managers see when one
    // of them has just silently reverted the other's work; the recovery path is
    // the audit trail, and there is deliberately no UI for it.
    "atelier.settings.cue.saved": "ההגדרות נשמרו.",

    // --- F60 guided walkthrough (the «מדריך» header button) ---
    //
    // FLAT dotted literals, appended, exactly like every block above. The nested
    // `nav:` object at the top of this file is deliberately untouched: it is the
    // file's merge-conflict zone while sibling features land.
    //
    // ⚠ NO `nav.guide` KEY, and that is an assertion rather than an omission.
    // F60 adds no console section and no nav row — `SectionKey` stays fourteen,
    // `NAV` stays fourteen — and the trigger is a header control beside
    // «יציאה». ⚠ And no `guide.triggerAria` (DL20): the trigger's accessible
    // name IS its visible «מדריך», which makes WCAG 2.5.3 true here by
    // construction, since an aria-label over visible text is the one shape 2.5.3
    // can fail.
    //
    // ⚠ EVERY GUILLEMET-QUOTED LABEL BELOW IS BYTE-IDENTICAL TO THE SHIPPED
    // CONTROL IT NAMES, and for `hours`, `types`, `terms` and `catalog` the
    // component is the only place those words exist (`grep -c useTranslation` is
    // 0 for all four). A quoted label that drifts from its control is this
    // deck's failure mode and no test in this repo can see it.
    "guide.trigger": "מדריך",
    // «מדריך» and not «עזרה»: help is what you want when something is broken,
    // and nothing here is broken — this is the manual, opened deliberately.
    "guide.title": "מדריך — {{section}}",
    // {{section}} is the ALREADY-TRANSLATED nav label, derived by GuideOverlay as
    // `t(`nav.${section}`)`, so no section name is transcribed twice and a nav
    // label edit never desynchronises the guide. No <bdi> and no isolate: all
    // fourteen labels are pure Hebrew, so there is no run to reorder.
    "guide.progress": "שלב {{step}} מתוך {{total}} במדריך",
    // ⚠ The trailing «במדריך» is load-bearing twice (copy.md C-1): it keeps both
    // digits between Hebrew words — D5's bidi rule, which is unsatisfiable for a
    // two-number Hebrew counter without a trailing noun — and it names which of
    // the console's role="status" regions is speaking when the live region utters
    // this line alone. `isolateLtr` is NOT the alternative: it splits on
    // `indexOf` (lib/booking.tsx:76), so on «שלב 3 מתוך 3» it isolates the FIRST
    // 3 and leaves the trailing one bare.
    "guide.next": "הבא",
    "guide.prev": "הקודם",
    // Replaces «הבא» on the last step, in the same position. «סיום» and not
    // «סגירה»: it says YOU HAVE REACHED THE END, which «סגירה» does not — and the
    // two must differ, because they sit side by side in the same footer.
    "guide.done": "סיום",
    // The persistent ghost dismiss, on EVERY step (DL19). A new key rather than a
    // reuse of «ביטול», and the reason is register: `SosRaiseDialog` dismisses an
    // ACTION IN PROGRESS, and a walkthrough has none, so «ביטול» reads as «cancel
    // what?». ⚠ THIS IS THE ONLY POINTER ROUTE OUT of the dialog — `Modal` binds
    // no backdrop click and the chrome has no X — so on a boutique tablet with no
    // Esc key it is the whole exit.
    "guide.close": "סגירה",

    // Steps, in NAV order. One sentence each, and the em-dash carries the
    // subordinate clause: longer and the live region reads two utterances for one
    // step change; shorter and the step is a label rather than help.
    "guide.dashboard.1":
      "המסך מציג שני טווחים נפרדים — תפוסה בשבעת הימים הקרובים, ומתחתיו סיכום של שבועות שכבר הסתיימו — ומתחת לכל מספר יש שורה שמסבירה מה בדיוק נספר בו.",
    // DashboardSection:10-13 states it outright — «It has NO interactive control
    // of any kind» — so the step says so instead of letting her hunt for one.
    "guide.dashboard.2":
      "אין כאן מה לשנות ואין על מה ללחוץ — מספר שנראה לא נכון נבדק במסך שממנו הוא הגיע, למשל «תורים» או «שעות פעילות».",

    // F10 made phone/address/description/maps_url world-readable, and a
    // home-based owner had typed her home address into a field that had only ever
    // been private. That is the one thing this step exists for.
    "guide.profile.1":
      "החלק העליון, «פרופיל הבוטיק», הוא מה שהלקוחות רואות בדף הפומבי — טלפון, כתובת, קישור למפות ותיאור — ולכן כתובת שאינה מיועדת לפרסום לא נכתבת כאן.",
    "guide.profile.2":
      "המתג «בוטיק לכלות בלבד» מסמן את כל סוגי התורים כמיועדים לכלות, ומשנה את מה שהלקוחה רואה כשהיא בוחרת סוג תור.",
    // ⚠ Names no unreachable section: it does NOT say «סליקה ותשלומים», which is
    // an owner-only nav row a shift manager reading this step cannot open.
    "guide.profile.3":
      "המתג «גביית מקדמות מופעלת» נשמר כאן, אבל מקדמה תיגבה בפועל רק אחרי שחשבון הסליקה של הבוטיק יחובר.",

    "guide.hours.1":
      "הטבלה העליונה היא השבוע הקבוע — לכל יום שעת «פתיחה», שעת «סגירה» ומספר תורים מקבילים בעמודת «קיבולת» — והיא זו שמייצרת את המועדים שהלקוחה רואה.",
    "guide.hours.2":
      "תאריך חריג הוא חריגה חד־פעמית מהשבוע הקבוע — יום «סגור כל היום», או יום עם שעות אחרות — ומוסיפים אותו למטה, בנפרד מהטבלה.",
    "guide.hours.3":
      "שינוי כאן משפיע על מועדים שעדיין אפשר להזמין ולא על תור שכבר נקבע — תור קיים נשאר במקומו עד שמישהי מזיזה אותו במסך «תורים».",

    "guide.types.1":
      "סוג תור קובע כמה זמן הפגישה נמשכת ולמי היא מוצעת — «כלות בלבד» או «כולם» — וזה מה שהלקוחה בוחרת כשהיא מזמינה.",
    // «מקדמה» throughout, never «פיקדון»: the console ships both words for one
    // thing and this deck picks the one on the two switches an owner touches.
    // F60 repairs neither payments block (copy.md C-2).
    "guide.types.2":
      "אם מסומן «נדרשת מקדמה», הסכום בשדה «מקדמה (₪)» הוא הסכום לסוג הזה בלבד, ולכל סוג יכול להיות סכום אחר.",
    "guide.types.3":
      "השדה «סדר תצוגה» קובע את הסדר שבו הסוגים מופיעים בפני הלקוחה, וסוג שכבר לא בשימוש עובר «העברה לארכיון» ולא נמחק.",

    "guide.terms.1":
      "מדיניות הביטולים נשמרת בגרסאות — כל גרסה נשמרת עם התאריך שבו נוצרה, ואף גרסה אינה נערכת ואינה נמחקת אחרי שנוצרה.",
    // ⚠ TermsSection:21 (`const isOwner = role === "owner"`) hides the publish
    // form from a shift manager, so this step describes versioning and names the
    // act as the OWNER'S rather than promising a control the reader may not have
    // (DL7). Consistent with the section's own shift-manager line.
    "guide.terms.2":
      "לקוחה שהזמינה תור מחויבת לגרסה שהייתה בתוקף באותו רגע, ולכן גרסה חדשה חלה על הזמנות חדשות בלבד — ויצירת גרסה חדשה היא פעולה של בעלת הבוטיק.",

    "guide.catalog.1":
      "כל שמלה נפתחת בכפתור «עריכה», ובתוכה נמצאים השם, התיאור, המחיר והמתג שקובע אם המחיר מוצג ללקוחה או שמופיע במקומו «מחיר בתיאום».",
    // Describes what the CONSOLE list shows and makes no claim about the
    // storefront — the earlier draft asserted a sold-out size stays visible on the
    // public site, which this deck did not verify.
    "guide.catalog.2":
      "טבלת המידות שבתוך השמלה קובעת אילו מידות קיימות וכמה יחידות יש מכל אחת, ושמלה שכל מידותיה אזלו מסומנת ברשימה כ«אזל מהמלאי».",
    "guide.catalog.3":
      "התמונות מועלות בתוך השמלה ואפשר לשנות את סדרן, ושמלה בלי תמונות מסומנת ברשימה כ«אין תמונות».",

    "guide.bookings.1":
      "הרשימה מציגה את התורים של תאריך אחד בכל פעם — התאריך נבחר למעלה בשדה «תאריך» — ומצב כל תור («מאושר», «התקיים», «לא הגיעה», «בוטל») מופיע בשורה שלו.",
    "guide.bookings.2":
      "לחיצה על שורה פותחת את «פרטי התור» — הלקוחה, המועד, השמלה ומצב התשלום — ו«חזרה לרשימה» מחזירה לאותו תאריך.",
    // ⚠ THE ONE STRING IN THIS BLOCK THE /נשלח|תישלח|בדרך/ GUARD IS AIMED AT.
    // Resolved by wording rather than by dodging, and the wording is also the true
    // statement: `booking.deliveryNotice` exists because the platform swallows
    // send errors and therefore has NO evidence a message was delivered. The step
    // says what the console records, then says what it is not.
    "guide.bookings.3":
      "שינוי מועד וביטול נעשים מתוך «פרטי התור», והמסך רושם את מה שהשתנה בבוטיק — הוא אינו עדות למה שהגיע ללקוחה בטלפון שלה.",

    "guide.customers.1":
      "כרטיס לקוחה מרכז את היסטוריית התורים שלה, הערות פנימיות שנראות לצוות הבוטיק בלבד, ותגיות לסימון.",
    // Writes «יומן ההודעות» (definite) where the shipped heading is «יומן הודעות»
    // (indefinite) — a heading names a thing, a sentence refers back to one. The
    // one intentional inflection in this block. Never «הודעות שנשלחו», which the
    // register guard forbids and which would be false over failed rows.
    "guide.customers.2":
      "החיפוש למעלה עובד לפי שם או לפי מספר טלפון, ו«יומן ההודעות» שבתוך הכרטיס הוא לקריאה בלבד — אי אפשר לערוך או למחוק בו שורה.",

    "guide.board.1":
      "הלוח מציג את תורי היום הנוכחי בלבד, לפי שעה, והשורה «עכשיו» מסמנת בתוכם את הרגע הזה — לתאריך אחר עוברים למסך «תורים».",
    "guide.board.2":
      "כשלקוחה מגיעה לוחצים «הגיעה» בשורה שלה והפעולה נרשמת עם השעה, ו«ביטול הרישום» מבטל את הרישום הזה בלבד ולא את התור.",
    // ⚠ Names the PANEL (App.tsx:258-263 renders it beneath the board for these
    // two roles), never the nav row «הצוות בקומה», which is FLOOR_ONLY and which
    // neither reader of this step can see. ⚠ And it names the EVENT «עודכן», never
    // a refresh rate: usePoll's backoff stretches 5s → ~60s, so any number is true
    // at tick 1 and false by tick 5.
    "guide.board.3":
      "מתחת ללוח מופיע פאנל הקומה — מי מהצוות נמצאת בקומה, מצב חדרי המדידה והממתינות בתור — והשורה «עודכן» למעלה אומרת מתי המידע נקרא לאחרונה.",

    // For reception, a sales assistant and a seamstress this is the only screen
    // they will ever see, so these are the three longest sentences in the block —
    // three panels totalling ~2,900 lines.
    "guide.floor.1":
      "החלק העליון מראה מי מהצוות נמצאת בקומה ובאיזה מצב — «פנויה», «תפוסה» או «בהפסקה» — ו«להפסקה» ו«חזרה» הם אותו כפתור שמשנה את המצב שלך או של עמיתה.",
    // ⚠ The masculine «פנוי / תפוס» here and the feminine «פנויה / תפוסה» above are
    // DELIBERATELY DIFFERENT WORDS for different subjects (a room, a woman), per
    // `rooms.free`'s own comment. The step keeps them apart.
    "guide.floor.2":
      "בחלק «חדרי מדידה» כל חדר הוא «פנוי» או «תפוס» — «שחרור» מפנה חדר בסיום המדידה, ו«העברה לעמיתה» משאיר את הלקוחה בחדר ומעביר את האחריות עליו.",
    // Teaches in advance the single most confusing thing on this panel: «שבצי
    // לחדר» vanishes from every row at one moment, and `waitlist.noFreeRoom` is
    // the only other surface that explains why.
    "guide.floor.3":
      "ב«ממתינות בתור» מופיעות מי שנרשמו בכניסה מהטלפון, לפי סדר הגעה — «קראי» מסמן שקראת לה בשמה, «שבצי לחדר» מכניס אותה לחדר, וכשאין חדר פנוי הכפתור נעלם עד שיתפנה אחד.",

    // «נמסר» quoted as shipped, and deliberately never «נשלח» — which the register
    // guard rejects outright and which is why the stage is named that way.
    "guide.atelier.1":
      "לוח התפירה בנוי מחמישה שלבים — «התקבל», «בעבודה», «בקרה», «מוכן» ו«נמסר» — וכרטיס עובר ביניהם לפי הסדר הזה.",
    // Lists what a card HOLDS and says nothing about who may change it — that is
    // step 3's job, and step 3 is honest about it.
    "guide.atelier.2":
      "כרטיס נפתח בלחיצה ומרכז את הלקוחה, השמלה, תאריך היעד, משך העבודה המשוער והתופרת המשויכת אליו.",
    // ⚠ THE ONLY PLACE IN THE PRODUCT WHERE THE ATELIER'S PERMISSION MODEL IS
    // WRITTEN DOWN. AtelierSection's `mayWork` deliberately renders no
    // explanation — no disabled button, no lock glyph, no «אין לך הרשאה» line — on
    // a screen she opens fifty times a shift. The walkthrough she opens
    // deliberately is where the other half of that argument lands.
    "guide.atelier.3":
      "הכפתורים שמופיעים על כרטיס תלויים בתפקיד ובשיוך — תופרת עובדת על הכרטיסים שלה ועל כרטיסים שעדיין לא שויכו, ועל כרטיס של עמיתה היא רואה את הפרטים בלבד.",

    "guide.checkinQr.1":
      "הדף הזה הוא השלט לכניסה — מי שסורקת את הקוד מהטלפון שלה מגיעה ישירות לטופס הרישום לתור, והכתובת מודפסת גם באותיות למי שהמצלמה שלה לא מצליחה לסרוק.",
    // Says THE ADDRESS STAYS THE SAME ADDRESS rather than «the code never
    // changes»: the first is what the poster shows and this deck can see, the
    // second is a claim about a token's lifetime it cannot.
    "guide.checkinQr.2":
      "«הדפסה» מדפיסה את הדף הזה כפי שהוא, והכתובת נשארת אותה כתובת — אפשר להדפיס שלט חדש בכל פעם שהקודם נקרע או דוהה.",

    // Reuses `staff.passwordNotice`'s wording rather than respelling it: a second
    // spelling of one fact in one console is a defect.
    "guide.staff.1":
      "הוספת אשת צוות דורשת שם, אימייל, תפקיד וסיסמה — התפקיד הוא שקובע לאילו מסכים היא נכנסת, ואת הסיסמה יש למסור לה בעצמך משום שהמערכת אינה מעבירה אותה לאיש.",
    // «השבתה», never «מחיקה»: the row is soft-deleted and its audit trail lives.
    "guide.staff.2":
      "«השבתה» עוצרת את הגישה של אשת הצוות לניהול הבוטיק ואינה מוחקת אותה — ההיסטוריה שלה נשמרת ואפשר להחזיר אותה בכל עת.",

    "guide.gateway.1":
      "המסך הזה מחבר את הבוטיק לחשבון הסליקה שדרכו נגבות המקדמות, ומטעמי אבטחה הפרטים אינם ניתנים לצפייה אחרי השמירה — שמירה נוספת מחליפה אותם במלואם.",
    "guide.gateway.2":
      "כל עוד אין חשבון מחובר, תור נקבע גם בלי מקדמה — המתג בהגדרות נשאר כפי שהוא, והמקדמה פשוט אינה נגבית עד שהחיבור יושלם.",

    // F20's privacy section. ⚠ THE LEGAL HEBREW IS NOT HERE and may never be:
    // the privacy notice, the processor clause, the sub-processor list, the
    // not-lawyer-reviewed disclaimer and the `reason`-field hint all ride
    // `GET /manage/privacy` (`PrivacyResponse.disclaimer_text` /
    // `.erase_reason_hint`). A copy here would be a second place for a legal
    // string to drift, and would put the one document a tenant may NOT edit into
    // a file a frontend change edits freely. `i18n.test.ts` asserts the absence.
    "nav.privacy": "פרטיות",
    // The section's h2.
    "privacy.heading": "הודעת הפרטיות של הבוטיק",
    // The two textarea labels. What each document IS lives in the disclaimer the
    // API serves above them, so these are names and not explanations.
    "privacy.noticeLabel": "הודעת הפרטיות",
    "privacy.dpaLabel": "סעיף עיבוד המידע",
    // Per field, so she can tell at a glance which document she has taken
    // ownership of. Two badges rather than one line about the pair: they are
    // overridden independently.
    "privacy.isDefault": "נוסח ברירת מחדל",
    "privacy.isCustom": "נוסח משלך",
    // D4's revert sentinel, as a control rather than as folklore about clearing a
    // box. It submits "" — `merge_settings` is one `settings || :patch::jsonb`
    // and `||` can add or replace a JSONB key but never remove one, so "" is the
    // only revert an owner can actually reach.
    "privacy.revert": "חזרה לנוסח ברירת המחדל",
    // ⚠ WCAG 2.5.3: the accessible name STARTS with the visible label, so speech
    // input can say what it reads. Two revert controls on one screen need to be
    // distinguishable by name, which is the whole reason this key exists.
    "privacy.revertAria": "חזרה לנוסח ברירת המחדל של {{document}}",
    // ⚠ BYTES, NOT CHARACTERS, and that is not pedantry: the server's cap is
    // `MAX_PRIVACY_TEXT_BYTES = 8 × 1024` measured on the UTF-8 encoding, and
    // Hebrew is two bytes per character. A character counter would tell an owner
    // she has 8 000 left when the server will refuse her at 4 096.
    "privacy.bytes": "{{used}} מתוך {{max}} בתים",
    "privacy.tooLong": "הנוסח ארוך מדי ולא יישמר. אפשר לקצר אותו.",
    "privacy.save": "שמירת הנוסח",
    "privacy.saved": "הנוסח נשמר",
    // The read-only block. It gets a heading and no control of any kind — the
    // absence IS the disclosure (Gate 1 Q3 / D14), and the disclaimer above says
    // in words why the box is missing so nobody has to guess.
    "privacy.subprocessorsHeading": "ספקי התשתית",
    "privacy.loadFailed": "לא הצלחנו לטעון את נוסחי הפרטיות כרגע.",
    "privacy.saveFailed": "לא הצלחנו לשמור את הנוסח כרגע.",
    // The §13/§14 panel.
    "privacy.subjectHeading": "בקשות של לקוחות למידע ולמחיקה",
    // The two operational duties NO CODE ENFORCES, stated where the person who
    // owes them is standing. The 30-day clock has no timer and the identity check
    // has no field; both are named in the compliance record as manual procedure,
    // and this line is the only place the console says so.
    "privacy.subjectIntro":
      "החוק מחייב להשיב לפנייה בתוך שלושים יום, ולוודא את זהות הפונה לפני מסירת מידע או מחיקתו — כדי שהפרטים לא יגיעו לאדם אחר.",
    "privacy.phoneLabel": "מספר הטלפון של הלקוחה",
    // ⚠ ONE CONTROL, TWO OUTCOMES, and it is deliberately named for both. The
    // §13 export IS the lookup step (D17): the erase and the withdrawal are keyed
    // on `customer_id`, and this response is the only place that id comes from —
    // step 2 of the erase overwrites `customers.phone`, so a phone-keyed erase
    // would destroy its own lookup key.
    "privacy.lookup": "חיפוש והפקת עותק",
    "privacy.lookupHint": "אפשר להזין עשר ספרות, למשל 0501234567.",
    "privacy.notFound": "לא נמצאה לקוחה עם המספר הזה.",
    "privacy.subjectLabel": "הלקוחה שנמצאה",
    "privacy.download": "הורדת העותק כקובץ",
    // The `reason` field. Its HINT is not here — `erase_reason_hint` rides
    // `GET /manage/privacy` with the rest of the approved Hebrew.
    "privacy.reasonLabel": "למה נמחק המידע",
    // «מחיקה», the word §14 uses and the word the endpoint earns. Never
    // «אנונימיזציה»: the survivor set is de-identified with a controlled
    // re-identification key, and a word implying the data is gone would
    // misdescribe it to the one person who has to answer for it.
    "privacy.erase": "מחיקת המידע של הלקוחה",
    "privacy.eraseConfirmTitle": "מחיקת המידע של הלקוחה",
    // Says what SURVIVES as well as what goes. An owner who expects the row to
    // vanish and finds a booking history the next morning has been told the
    // wrong thing at the one moment she could not undo it.
    "privacy.eraseConfirmBody":
      "הפעולה הזאת אינה הפיכה. השם, מספר הטלפון, ההערות והתגיות יימחקו, והתורים יישארו במערכת בלי הפרטים המזהים — כנדרש לצורכי הרישום והדיווח.",
    // ⚠ THE CONFIRMATION IS HER PHONE DIGITS RE-TYPED, and every part of that is
    // deliberate. An ASCII LTR digit run has no bidi ambiguity in an RTL field,
    // which a Hebrew word like «מחק» would; it is already on screen, so this is a
    // transcription and not a memory test; and it is DIFFERENT FOR EVERY SUBJECT,
    // so it cannot be satisfied by muscle memory the way one fixed word can.
    "privacy.eraseConfirmLabel": "להקלדת אישור, יש להקליד את מספר הטלפון של הלקוחה",
    "privacy.eraseConfirmMismatch": "המספר שהוקלד אינו תואם.",
    "privacy.eraseConfirmCta": "מחיקה סופית",
    "privacy.cancel": "ביטול",
    "privacy.erased": "המידע נמחק",
    "privacy.alreadyErased": "המידע של הלקוחה הזאת כבר נמחק.",
    // ⚠ SHARED WITH F53'S CUSTOMER CARD, which is where a front-desk staffer
    // actually looks a caller up — and the shift manager's path to Gate 1 Q4,
    // since the privacy section itself is owner-only. One vocabulary for one
    // consent, in one namespace: two spellings of a §30A state in one console is
    // how the two surfaces start disagreeing.
    "privacy.consentLabel": "הסכמה לדיוור",
    "privacy.consentNone": "לא ניתנה",
    "privacy.consentActive": "ניתנה",
    "privacy.consentWithdrawn": "הוסרה",
    // No confirmation step and that is a decision: withdrawal is the LESSER
    // action, it is reversible by asking again, and §30A says revocation may not
    // be conditioned — a modal asking «are you sure?» at the counter is a
    // condition, however small.
    "privacy.withdraw": "הסרת ההסכמה לדיוור",
    "privacy.withdrawn": "ההסכמה הוסרה",
    // A subject with no live consent. Not an error: it is the outcome she asked
    // for either way, and the front desk should not have to tell the two apart.
    "privacy.withdrawNoop": "לא הייתה הסכמה פעילה להסיר.",
    "privacy.withdrawFailed": "לא הצלחנו להסיר את ההסכמה כרגע.",
    "privacy.exportFailed": "לא הצלחנו להפיק את העותק כרגע.",
    "privacy.eraseFailed": "לא הצלחנו למחוק את המידע כרגע.",
    // The 409. The console maps it because the server's English message would
    // otherwise render into a Hebrew RTL screen at the one moment she is deciding
    // whether to destroy a record.
    "privacy.error.SUBJECT_HAS_ACTIVE_BOOKING": "ללקוחה יש תור עתידי מאושר. אפשר לבטל אותו ואז למחוק את המידע.",
    "privacy.error.TOO_MANY_ATTEMPTS": "בוצעו הרבה בקשות בזמן קצר. אפשר לנסות שוב בעוד זמן מה.",
    "privacy.error.NOT_AUTHORIZED": "הפעולה הזאת פתוחה לבעלת הבוטיק בלבד.",

    // The fifteenth section's two guide steps. `guide.`-namespaced, so they ride
    // HE_F60 by prefix and inherit its register guards and its ar-value guard —
    // the namespace names the payload, not the feature that added the key.
    "guide.privacy.1":
      "במסך הזה נמצאים שני נוסחים שהלקוחה רואה באתר — הודעת הפרטיות וסעיף עיבוד המידע — ואפשר לערוך כל אחד מהם בנפרד; רשימת ספקי התשתית שמתחתיהם נקבעת על ידי מפעילת הפלטפורמה ואינה ניתנת לעריכה.",
    "guide.privacy.2":
      "בחלק התחתון מטפלים בפניות של לקוחות: מחפשים לפי מספר טלפון, ההפקה מורידה עותק של כל המידע שנשמר עליה, ומחיקה היא פעולה שאינה הפיכה — התורים נשארים במערכת בלי הפרטים המזהים.",

    // --- F50: the walk-in booking -------------------------------------------
    //
    // ALL OF IT IS STAFF-FACING CONSOLE COPY, which is the self-approving class.
    // There is no public-facing string in this feature: the request body is two
    // ids, so nothing is obtained from the subject and no §11 notice is owed.
    //
    // The board's one new control. Its accessible name IS its visible text, so
    // there is no *Aria row and WCAG 2.5.3 holds by construction.
    "board.newWalkIn": "תור חדש",

    // The detail's terms Fact, second body. It states the fact rather than
    // leaving a hole — «גרסה null» beside an empty date is what the absence
    // rendered as before this key existed.
    "booking.termsNone": "נוצר בבוטיק · אין אישור תנאים",
    // The row's one muted word, in the attendance treatment: never a second
    // Badge and never a tint.
    "booking.sourceWalkIn": "נכנסה",

    "walkin.title": "תור חדש בבוטיק",
    "walkin.searchLabel": "לקוחה",
    // Both legs, because the server searches both and a staffer reading a phone
    // off a card would otherwise not know she may.
    "walkin.searchHelp": "אפשר לחפש לפי שם או לפי מספר טלפון.",
    "walkin.resultsLegend": "בחירת הלקוחה",
    // ⚠ THE LOAD-BEARING ONE — D3 as product copy. A walk-in for a customer the
    // boutique does not yet hold is out of scope on purpose: her route in is the
    // check-in form at the door, which is behind an approved notice. Not an
    // error and not role="alert": it is the ordinary answer to a search that
    // matched nothing. «קוד סריקה» is the shipped nav label of that screen.
    "walkin.empty":
      "לא נמצאה לקוחה עם השם או הטלפון האלה. לקוחה חדשה נרשמת דרך טופס הרישום בכניסה — הקוד נמצא במסך «קוד סריקה».",
    // Stated, never absorbed — the board's own truncation rule, and it bites the
    // same way here: two brides with one name and only one of them on screen.
    "walkin.truncated": "מוצגות {{count}} הלקוחות הראשונות. אפשר לדייק את החיפוש.",
    "walkin.searchFailed": "לא הצלחנו לחפש לקוחות כרגע.",
    // The SINGULAR field label is `booking.type`'s shipped wording verbatim
    // («סוג הפגישה», also the storefront's `typeHeading`) — one word for one
    // thing across the product. The PLURAL collection is the catalog screen's,
    // «סוגי תורים» (`nav.types`, `dashboard.typesTableCaption`), which is what
    // the two sentences below name and point at: they used to say «סוגי
    // הפגישות», and `typesEmpty` managed both words in ONE sentence — telling a
    // staffer to configure "meeting types" on the "appointment types" screen.
    "walkin.typeLabel": "סוג הפגישה",
    "walkin.typePlaceholder": "בחירת סוג פגישה",
    "walkin.typesFailed": "לא הצלחנו לטעון את סוגי התורים כרגע.",
    "walkin.typesEmpty": "לא הוגדרו סוגי תורים. אפשר להגדיר אותם במסך «סוגי תורים».",
    // The two codes this dialog owns rather than delegating to F15's map
    // (BoardSection's WALK_IN_ERROR_KEYS says why). NOT_FOUND has four reachable
    // producers and they are indistinguishable by design, so the sentence names
    // both halves of the selection and the remedy is to search again.
    "walkin.error.notFound": "הלקוחה או סוג הפגישה שנבחרו כבר אינם זמינים. כדאי לחפש שוב.",
    // NOT «אפשר לבחור מועד אחר»: there is no time to choose here — the
    // appointment starts now — and the only way to lose this race is to lose it
    // to another tap in the same microsecond.
    "walkin.error.slotUnavailable": "לא הצלחנו לפתוח את התור. כדאי לנסות שוב.",
    "walkin.confirm": "יצירת התור",
    // This dialog IS the confirm: the consequence sits above the one submit
    // rather than stacking a second focus trap for a decision she is reading.
    "walkin.consequence": "התור נפתח עכשיו והלקוחה מסומנת כמי שהגיעה.",
    // The board's announced cue, in board.checkedInCue's shape: it names the
    // bride, because after one tap on a forty-row board a nameless confirmation
    // is useless exactly when the board is busy.
    "walkin.createdCue": "נוצר תור חדש עבור {{name}}.",

    // --- F22: the booking waitlist (design §9) -------------------------------
    //
    // ⚠ `bookingWaitlist.*`, NEVER `waitlist.*` — that namespace is F58's
    // walk-in queue a few hundred lines up (spec conflict 1 / design F-W2).
    // «רשימת המתנה לתורים» is deliberately distinct from F58's plain
    // «רשימת המתנה» heading for the same reason.
    "nav.bookingWaitlist": "רשימת המתנה לתורים",
    "bookingWaitlist.dayFilter": "תאריך",
    "bookingWaitlist.dayFilterHint": "אפשר לנקות את התאריך כדי לראות את כל הימים הקרובים.",
    "bookingWaitlist.colDay": "יום",
    "bookingWaitlist.colType": "סוג הפגישה",
    "bookingWaitlist.colCustomer": "לקוחה",
    "bookingWaitlist.colStatus": "סטטוס",
    "bookingWaitlist.colJoined": "נרשמה בשעה",
    "bookingWaitlist.statusWaiting": "ממתינה",
    // F23-era, shipped now so the badge never shows a raw wire value.
    // NOT the design table's «נשלחה הצעה»: the register guard in i18n.test.ts
    // mechanically forbids any manage copy claiming a send (/נשלח/), and an
    // offer BADGE must not promise the SMS F23 has not sent yet. «הוצע תור»
    // states the status itself and nothing about a message.
    "bookingWaitlist.statusOffered": "הוצע תור",
    "bookingWaitlist.cancel": "ביטול",
    // The danger half of the in-place swap (design P3) — the second click.
    "bookingWaitlist.cancelConfirm": "אישור הביטול",
    // The status region's discrete event. No exclamation mark.
    "bookingWaitlist.cancelled": "הרשומה בוטלה.",
    "bookingWaitlist.loading": "טוענת את רשימת ההמתנה",
    "bookingWaitlist.emptyTitle": "אין כרגע רשומות ברשימת ההמתנה",
    "bookingWaitlist.emptyBody":
      "כשלקוחה תצטרף לרשימת ההמתנה מיום מלא באתר, היא תופיע כאן.",
    // A date filter is set, so the day may simply have no entries.
    "bookingWaitlist.emptyFiltered": "אין רשומות בתאריך הזה.",
    "bookingWaitlist.loadFailed": "לא הצלחנו לטעון את הרשימה כרגע.",
    "bookingWaitlist.retry": "ניסיון נוסף",
    // The guide's one step (SectionKey is guide-typed — lib/guide.ts).
    "guide.bookingWaitlist.1":
      "כאן רואים מי מחכה לתור ביום מלא. אם מתפנה מקום, אפשר להתקשר אליה — ובעתיד המערכת תציע לה אותו לבד.",
  },
} as const;
