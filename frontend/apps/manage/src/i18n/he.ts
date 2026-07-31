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
  },
} as const;
