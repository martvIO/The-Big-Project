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
    "booking.cancelledNoActions":
      "תור שבוטל אינו ניתן לשחזור. לקביעת מועד חדש, הלקוחה מזמינה מחדש דרך אתר הבוטיק.",

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
    "booking.rescheduleConfirm": "עדכון המועד",
    "booking.rescheduleDone": "המועד עודכן.",
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
  },
} as const;
