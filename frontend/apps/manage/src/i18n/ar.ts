// Arabic resource keys — SHIPPED, UNTRANSLATED. The console's first.
//
// Interview Q3 / pre-decided #47: every feature from F16 on adds `ar` keys
// alongside its Hebrew, left untranslated, so the eventual launch is a
// translation job rather than a retrofit across ~28 features. Arabic is NOT live
// for the pilot: `lng` stays "he", no language switcher ships, and nothing
// renders from this file today.
//
// The expensive half of Arabic is already paid for — Hebrew makes RTL the
// default and Arabic is also RTL — so what is missing is strings, number/date
// formatting and a switcher. No direction-switching logic and no second
// stylesheet, by that same ruling.
//
// **Every value below is the approved Hebrew, standing in as a placeholder.**
// That is deliberate rather than lazy: a translator opens one file, sees every
// key with its live source text beside it, and replaces values in place. An empty
// string would be worse — i18next's `returnEmptyString` default renders "" rather
// than falling back, so a premature switch would blank the page instead of
// showing Hebrew. `fallbackLng: "he"` covers every key this file does not carry.
//
// F15 is the first feature to add one HERE (the storefront has had its own since
// F16), so this file starts with F15's keys only. Later console features append
// theirs. NOTHING keeps this file in sync with he.ts — no he/ar parity guard
// exists in this repo and F15 does not invent one; a key added to he.ts and not
// to this one simply falls back to Hebrew, which is what renders today anyway.
export const ar = {
  translation: {
    "nav.bookings": "תורים",
    "booking.heading": "תורים",
    "booking.dateLabel": "תאריך",
    "booking.listLoading": "טוען תורים…",
    "booking.dayCount": "תורים ביום זה: {{count}}",
    "booking.loadFailed": "לא הצלחנו לטעון את התורים כרגע.",
    "booking.emptyDayTitle": "אין תורים בתאריך הזה",
    "booking.emptyDayBody": "אפשר לבחור תאריך אחר.",
    "booking.attendanceConfirmed": "אישרה הגעה",
    "booking.statusConfirmed": "מאושר",
    "booking.statusCompleted": "התקיים",
    "booking.statusNoShow": "לא הגיעה",
    "booking.statusCancelled": "בוטל",
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
    "booking.actionsHeading": "פעולות",
    "booking.deliveryNotice":
      "אין באפשרותנו לאמת שהודעות נמסרו ללקוחה. אם חשוב לוודא, אפשר להתקשר אליה.",
    "booking.cancelledNoActions":
      "תור שבוטל אינו ניתן לשחזור. לקביעת מועד חדש, הלקוחה מזמינה מחדש דרך אתר הבוטיק.",
    "booking.cancelCta": "ביטול התור",
    "booking.cancelModalTitle": "לבטל את התור?",
    "booking.cancelModalBody":
      "הביטול סופי ואי אפשר לשחזר אותו. המועד יתפנה להזמנה, ולקביעת מועד חדש הלקוחה מזמינה מחדש דרך אתר הבוטיק.",
    "booking.cancelConfirm": "אישור הביטול",
    "booking.modalKeep": "חזרה",
    "booking.cancelDone": "התור בוטל.",
    "booking.noShowCta": "סימון: לא הגיעה",
    "booking.noShowDone": "התור סומן: לא הגיעה.",
    "booking.completeCta": "סימון: התקיים",
    "booking.completeDone": "התור סומן: התקיים.",
    "booking.reopenCta": "החזרה לסטטוס מאושר",
    "booking.reopenDone": "הסטטוס הוחזר למאושר.",
    "booking.rescheduleCta": "שינוי מועד",
    "booking.rescheduleTitle": "שינוי מועד התור",
    "booking.rescheduleCurrent": "המועד הנוכחי:",
    "booking.rescheduleConsequence": "המועד יתעדכן, והקישור של הלקוחה יצביע על המועד החדש.",
    "booking.rescheduleConfirm": "עדכון המועד",
    "booking.rescheduleDone": "המועד עודכן.",
    "booking.retry": "ניסיון נוסף",
    "booking.pickDate": "תאריך",
    "booking.pickTime": "שעה",
    "booking.noSlots":
      "אין מועדים פנויים בתאריך הזה. אפשר לבחור תאריך אחר, או לפתוח שעות נוספות במסך «שעות פעילות».",
    "booking.resendCta": "הנפקת קישור ניהול חדש",
    "booking.resendHint": "הנפקת קישור חדש מבטלת את הקישור הקודם של הלקוחה.",
    "booking.resendDone": "הונפק קישור חדש. הקישור הקודם בוטל.",
    "booking.phoneEditCta": "תיקון מספר הטלפון",
    "booking.phoneFieldLabel": "מספר טלפון חדש",
    "booking.phoneEditCancel": "ביטול העריכה",
    "booking.phoneSaveCta": "שמירת המספר",
    "booking.phoneModalTitle": "לעדכן את מספר הטלפון?",
    "booking.phoneModalBody":
      "המספר שהוזן: {{phone}}. המערכת אינה מאמתת שהמספר שייך ללקוחה — העדכון נרשם על אחריות הבוטיק. הקישור הקיים של הלקוחה יפסיק לעבוד, ובמקומו יונפק קישור חדש.",
    "booking.phoneModalConfirm": "עדכון המספר",
    "booking.phoneDone": "מספר הטלפון עודכן. הקישור הקודם בוטל.",
    "booking.error.BOOKING_TRANSITION_INVALID":
      "לא ניתן לבצע את הפעולה במצב הנוכחי של התור. כדאי לחזור לרשימה ולפתוח את התור מחדש.",
    "booking.error.SLOT_UNAVAILABLE": "המועד הזה נתפס הרגע. אפשר לבחור מועד אחר.",
    "booking.error.CUSTOMER_ALREADY_BOOKED": "ללקוחה כבר יש תור פעיל במועד הזה.",
    "booking.error.TOO_MANY_ATTEMPTS":
      "בוצעו יותר מדי פעולות בזמן קצר. כדאי להמתין מעט ולנסות שוב.",
    // --- F51 staff section, untranslated placeholders ---
    "nav.staff": "צוות",
    "staff.heading": "צוות",
    "staff.loadFailed": "לא הצלחנו לטעון את רשימת הצוות כרגע.",
    "staff.roleOwner": "בעלת הבוטיק",
    "staff.roleShiftManager": "אחראית משמרת",
    "staff.selfMarker": "זו את",
    "staff.editCta": "עריכה",
    "staff.deactivateCta": "השבתה",
    "staff.displayNameLabel": "שם לתצוגה",
    "staff.emailLabel": "אימייל",
    "staff.roleLabel": "תפקיד",
    "staff.newPasswordLabel": "סיסמה חדשה",
    "staff.newPasswordHelp": "אפשר להשאיר ריק כדי לא לשנות את הסיסמה.",
    "staff.currentPasswordLabel": "הסיסמה הנוכחית שלך",
    "staff.currentPasswordHelp": "נדרשת כדי לשנות את הסיסמה של עצמך.",
    "staff.currentPasswordWrong":
      "הסיסמה הנוכחית שגויה. יש להזין את הסיסמה הנוכחית כדי לשנות אותה.",
    "staff.saveCta": "שמירה",
    "staff.cancelCta": "ביטול",
    "staff.createHeading": "הוספת אשת צוות",
    "staff.passwordLabel": "סיסמה",
    "staff.passwordNotice": "יש למסור את הסיסמה לעובדת בעצמך. המערכת אינה מעבירה אותה לאיש.",
    "staff.createCta": "הוספה לצוות",
    "staff.deactivateTitle": "להשבית את הגישה?",
    "staff.deactivateBody":
      "הגישה של <bdi>{{name}}</bdi> לניהול הבוטיק תיפסק בפעולה הבאה שלה. אפשר להוסיף אותה מחדש בכל עת.",
    "staff.deactivateConfirm": "השבתה",
    "staff.error.DUPLICATE_EMAIL": "כתובת האימייל הזו כבר משויכת לאשת צוות פעילה.",
    "staff.error.LAST_OWNER_REQUIRED": "לבוטיק חייבת להיות בעלת בוטיק אחת לפחות.",
    "staff.error.STAFF_SELF_MANAGE": "אי אפשר לשנות את התפקיד של עצמך או להשבית את עצמך.",
    "staff.error.NOT_AUTHORIZED": "הפעולה הזו זמינה לבעלת הבוטיק בלבד.",

    // --- F52, the KPI dashboard ---
    "nav.dashboard": "סקירה",
    "dashboard.heading": "סקירה",
    "dashboard.generatedOnLabel": "נכון לתאריך:",
    "dashboard.loading": "טוענים את הנתונים.",
    "dashboard.summary": "סך התורים שלא בוטלו בתקופה: {{count}}",
    "dashboard.loadFailed": "לא הצלחנו לטעון את הנתונים כרגע.",
    "dashboard.firstRunNote":
      "המסך הזה מתמלא מעצמו ככל שנקבעים תורים. עד אז המספרים כאן הם אפס.",
    "dashboard.notEnoughData": "אין עדיין מספיק נתונים לחישוב.",
    "dashboard.rateUnderFloor": "פחות מ־0.1%",
    "dashboard.forwardHeading": "תפוסה בשבעת הימים הקרובים",
    "dashboard.forwardRange": "הטווח:",
    "dashboard.forwardValueLabel": "אחוז התפוסה",
    "dashboard.forwardCapacityLabel": "סך המקומות בטווח",
    "dashboard.forwardBookedLabel": "מקומות שנתפסו",
    "dashboard.forwardHelp":
      "הספירה כוללת רק מועדים שאפשר עדיין להציע מהרגע הזה. מועדים שכבר חלפו היום אינם נכללים בה.",
    "dashboard.forwardNoHours": "אין שעות פעילות פתוחות בטווח הזה, ולכן אין כאן מה לחשב.",
    "dashboard.weeksHeading": "תורים לפי שבוע",
    "dashboard.weeksRange": "התקופה:",
    "dashboard.weeksHelp": "נספרים תורים שנקבעו ולא בוטלו, כולל תורים שהלקוחה לא הגיעה אליהם.",
    "dashboard.weeksTableCaption": "תורים שלא בוטלו, לפי שבוע",
    "dashboard.weekColumn": "תחילת שבוע",
    "dashboard.bookingsColumn": "תורים שלא בוטלו",
    "dashboard.ratesHeading": "ביטולים ואי־הגעה",
    "dashboard.cancellationRateLabel": "שיעור הביטולים",
    "dashboard.cancellationHelp": "מתוך כל התורים שנקבעו בתקופה, בכל סטטוס.",
    "dashboard.cancelledByCustomerLabel": "ביטולים ביוזמת הלקוחה",
    "dashboard.cancelledByOwnerLabel": "ביטולים ביוזמת הבוטיק",
    "dashboard.noShowRateLabel": "שיעור אי־ההגעה",
    "dashboard.noShowHelp": "מתוך התורים שסומנו כהתקיימו או כאי־הגעה בלבד.",
    "dashboard.unclassifiedLabel": "תורים שעברו ולא סומנו",
    "dashboard.unclassifiedHelp":
      "תורים שכבר עברו ולא סומנו כהתקיימו או כאי־הגעה. הם אינם נכללים בשיעור אי־ההגעה.",
    "dashboard.customersHeading": "לקוחות בתקופה",
    "dashboard.customersHelp": "נספרות לקוחות עם תור אחד לפחות בתקופה שלא בוטל.",
    "dashboard.customersTotalLabel": "סך הלקוחות",
    "dashboard.customersNewLabel": "לקוחות חדשות",
    "dashboard.customersReturningLabel": "לקוחות חוזרות",
    "dashboard.repeatRateLabel": "שיעור החזרה",
    "dashboard.repeatRateHelp": "חלקן של הלקוחות בתקופה שקבעו בבוטיק יותר מתור אחד אי פעם.",
    "dashboard.typesHeading": "סוגי התורים המבוקשים",
    "dashboard.typesHelp": "מוצגים סוגי התורים שנקבעו הכי הרבה פעמים בתקופה.",
    "dashboard.typesTableCaption": "סוגי תורים לפי מספר התורים בתקופה",
    "dashboard.typeColumn": "סוג תור",
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
  },
} as const;
