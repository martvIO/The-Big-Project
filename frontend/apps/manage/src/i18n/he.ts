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
  },
} as const;
