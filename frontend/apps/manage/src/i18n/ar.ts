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
    "booking.statusPendingPayment": "ממתין לתשלום",
    "booking.statusOther": "מצב לא מוכר",
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
    "booking.checkedInAt": "נרשמה הגעה",
    "booking.cancelledAt": "בוטל בתאריך",
    "booking.cancelledBy": "בוטל על ידי",
    "booking.cancelledByOwner": "הבוטיק",
    "booking.cancelledByCustomer": "הלקוחה",
    "booking.payment": "תשלום",
    "booking.paymentPending": "בהמתנה",
    "booking.paymentPaid": "שולם",
    "booking.paymentFailed": "נכשל",
    "booking.paymentExpired": "פג תוקף",
    "booking.paymentRefundDue": "זיכוי לביצוע",
    "booking.paymentRefunded": "זוכה",
    "booking.paymentForfeited": "חולט",
    "booking.paymentOther": "מצב תשלום לא מוכר",
    "booking.refundDue": "סכום להחזר",
    "booking.paymentActionCancelledPaid":
      "דרושה פעולה: התור בוטל והפיקדון עדיין מוחזק בבוטיק.",
    "booking.paymentActionNoDeposit":
      "דרושה פעולה: התור נקבע ללא פיקדון, משום שספק הסליקה לא היה זמין בעת ההזמנה.",
    "booking.notesHeading": "הערות הלקוחה",
    "booking.notesEmpty": "הלקוחה לא הוסיפה הערות.",
    "booking.actionsHeading": "פעולות",
    "booking.deliveryNotice":
      "אין באפשרותנו לאמת שהודעות נמסרו ללקוחה. אם חשוב לוודא, אפשר להתקשר אליה.",
    "booking.cancelledNoActions":
      "תור שבוטל אינו ניתן לשחזור. לקביעת מועד חדש, הלקוחה מזמינה מחדש דרך אתר הבוטיק.",
    "booking.cancelledPaidActions":
      "התור בוטל והפיקדון עדיין מוחזק בבוטיק. אפשר לקבוע ללקוחה מועד חדש, והתור יחזור לסטטוס מאושר.",
    "booking.awaitingPaymentNoActions":
      "התור ממתין לתשלום הפיקדון. עד להשלמת התשלום אין פעולות זמינות, ואם התשלום לא יושלם המועד יתפנה מעצמו.",
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
    "booking.rescheduleConsequenceRestore":
      "המועד יתעדכן, התור יחזור לסטטוס מאושר, והקישור של הלקוחה יצביע על המועד החדש.",
    "booking.rescheduleRestoreCta": "קביעת מועד חדש ושחזור התור",
    "booking.rescheduleConfirm": "עדכון המועד",
    "booking.rescheduleDone": "המועד עודכן.",
    "booking.rescheduleRestoreDone": "התור הוחזר לסטטוס מאושר במועד שנבחר.",
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

    // --- F34, the live shift board ---
    //
    // Same 34 keys as he.ts, values standing in untranslated. NOTHING keeps
    // these two files in sync — no parity guard exists in this repo and F34 does
    // not invent one (Risk 6, inherited from F15) — so copy.md's table is the
    // single source for both columns and this is one file to one file.
    "nav.board": "לוח היום",
    "board.heading": "לוח היום",
    "board.dayLine": "היום · {{date}}",

    "board.summary": "הגיעו {{ratio}}",
    "board.updatedAt": "עודכן {{time}}",
    "board.staleAt": "אין עדכון מאז {{time}}",
    "board.staleBody": "ייתכן שהמידע אינו עדכני.",
    "board.refresh": "רענון",

    "board.pause": "השהיה",
    "board.pauseAria": "השהיה — עדכון הלוח",
    "board.resume": "חידוש",
    "board.resumeAria": "חידוש — עדכון הלוח",
    "board.pausedAt": "מושהה · עודכן {{time}}",
    "board.paused": "העדכון מושהה. הלוח לא יתעדכן עד לחידוש.",
    "board.idleStopped": "העדכון הופסק אחרי {{minutes}} דקות ללא פעילות.",
    "board.resumed": "העדכון חודש.",

    "board.checkIn": "הגיעה",
    "board.checkInAria": "הגיעה — {{name}}, {{time}}",
    "board.checkedInAt": "נרשמה הגעה · {{time}}",
    "board.undo": "ביטול הרישום",
    "board.undoAria": "ביטול הרישום — {{name}}, {{time}}",
    "board.now": "עכשיו {{time}}",
    "board.movedAway": "התור הועבר לתאריך אחר",

    "board.checkedInCue": "נרשמה הגעה עבור {{name}}.",
    "board.undoneCue": "הרישום בוטל עבור {{name}}.",

    "board.loading": "טוען את לוח היום…",
    "board.loadFailed": "לא הצלחנו לטעון את הלוח כרגע.",
    "board.emptyTitle": "אין תורים היום",
    "board.emptyBody":
      "תורים שייקבעו להיום יופיעו כאן. לתאריכים אחרים אפשר לעבור למסך «תורים».",
    "board.truncated":
      "מוצגים {{count}} התורים הראשונים של היום. לרשימה המלאה אפשר לעבור למסך «תורים».",
    "board.sessionEnded": "תוקף החיבור פג. צריך להתחבר מחדש.",
    "board.accessEnded": "אין הרשאה לצפות בלוח כרגע. לבירור אפשר לפנות לבעלת הבוטיק.",
    "board.reload": "רענון הדף",

    "board.error.transitionInvalid": "מצב התור השתנה. השורה תתוקן בעדכון הבא.",

    // --- F57: the floor's staff cards -------------------------------------
    //
    // Untranslated Hebrew standing in, per Q3 / pre-decided #47 and the
    // 2026-07-31 languages ruling (Hebrew only for now, no switcher). NEVER "":
    // i18next's returnEmptyString renders the empty string rather than falling
    // back, so a premature switch would blank the panel instead of showing
    // Hebrew.
    //
    // ⚠ Nothing keeps this file in step with he.ts — no parity guard exists and
    // F57 does not invent one (Risk 7 / design.md F-5). The mitigation is that
    // both columns are transcribed from ONE copy.md table. F45 owns the real
    // translation.
    "nav.floor": "הצוות בקומה",
    "floor.heading": "צוות בקומה",

    "floor.loading": "טוען את רשימת הצוות…",
    "floor.empty": "אין נשות צוות פעילות",

    "floor.updatedAt": "עודכן {{time}}",
    "floor.staleAt": "אין עדכון מאז {{time}}",
    "floor.staleBody": "ייתכן שהמידע אינו עדכני.",
    "floor.refresh": "רענון",

    "floor.pause": "השהיה",
    "floor.pauseAria": "השהיה — עדכון הצוות",
    "floor.resume": "חידוש",
    "floor.resumeAria": "חידוש — עדכון הצוות",
    "floor.pausedAt": "מושהה · עודכן {{time}}",
    "floor.paused": "העדכון מושהה. רשימת הצוות לא תתעדכן עד לחידוש.",
    "floor.idleStopped": "עדכון הצוות הופסק אחרי {{minutes}} דקות ללא פעילות.",
    "floor.resumed": "העדכון חודש.",

    "floor.statusAvailable": "פנויה",
    "floor.statusBreak": "בהפסקה",
    "floor.breakSince": "מאז {{time}}",
    "floor.breakStart": "להפסקה",
    "floor.breakStartAria": "להפסקה — {{name}}",
    "floor.breakEnd": "חזרה",
    "floor.breakEndAria": "חזרה — {{name}}",

    "floor.breakStartedCue": "נרשמה הפסקה עבור {{name}}.",
    "floor.breakEndedCue": "ההפסקה הסתיימה עבור {{name}}.",

    "floor.sessionEnded": "תוקף החיבור פג. צריך להתחבר מחדש.",
    "floor.accessEnded": "אין הרשאה לצפות ברשימת הצוות כרגע. לבירור אפשר לפנות לבעלת הבוטיק.",
    "floor.reload": "רענון הדף",
    "floor.error.notFound": "אשת הצוות הזו כבר לא פעילה. הרשימה תתוקן בעדכון הבא.",

    "staff.roleReception": "קבלה",
    "staff.roleSalesAssistant": "יועצת מכירות",
    "staff.roleSeamstress": "תופרת",

    // --- F53, customers CRM ---
    "nav.customers": "לקוחות",
    "customers.heading": "לקוחות",
    "customers.searchLabel": "חיפוש לפי שם או טלפון",
    "customers.searchPlaceholder": "שם או מספר טלפון",
    "customers.listLoading": "טוען את רשימת הלקוחות…",
    "customers.count": "לקוחות ברשימה: {{count}}",
    "customers.loadFailed":
      "לא ניתן לטעון את רשימת הלקוחות כרגע. אפשר לנסות שוב בעוד רגע.",
    "customers.emptyTitle": "אין עדיין לקוחות",
    "customers.emptyBody":
      "לקוחה נוספת לרשימה אחרי שהיא מאמתת את מספר הטלפון שלה וקובעת תור.",
    "customers.noResultsTitle": "אין תוצאות לחיפוש הזה",
    "customers.noResultsBody": "אפשר לנסות שם חלקי או ספרות מתוך מספר הטלפון.",
    "customers.back": "חזרה לרשימה",
    "customers.detailLoading": "טוען את פרטי הלקוחה…",
    "customers.detailFailed": "לא ניתן לטעון את פרטי הלקוחה כרגע.",
    "customers.notFound": "הלקוחה הזו לא נמצאה. ייתכן שהכרטיס הוסר.",
    "customers.phoneLabel": "טלפון",
    "customers.notesLabel": "הערות",
    "customers.notesHelp": "ההערות נשמרות בכרטיס ונראות לצוות הבוטיק בלבד.",
    "customers.notesPlaceholder": "מה כדאי לזכור לפעם הבאה",
    "customers.notesTooLong": "ההערות יכולות להכיל עד {{length}} תווים.",
    "customers.notesInvalid": "ההערות מכילות תווים שאי אפשר לשמור.",
    "customers.tagsLabel": "תגיות",
    "customers.tagsHelp": "עד {{max}} תגיות, עד {{length}} תווים לתגית.",
    "customers.tagAddLabel": "תגית חדשה",
    "customers.tagAdd": "הוספה",
    "customers.tagRemove": "הסרה",
    "customers.tagRemoveAria": "הסרה של התגית {{tag}}",
    "customers.tagsEmpty": "אין תגיות בכרטיס הזה.",
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
    "customers.messagesTruncated": "מוצגות {{count}} מתוך {{total}} רשומות ביומן.",
    "customers.messageKindOtp": "קוד אימות",
    "customers.messageKindConfirmation": "אישור תור",
    "customers.messageKindReminder": "תזכורת",
    "customers.messageKindOwnerCancel": "ביטול מטעם הבוטיק",
    "customers.messageKindOwnerReschedule": "שינוי מועד מטעם הבוטיק",
    "customers.messageStatusQueued": "בהמתנה",
    "customers.messageStatusSent": "הועברה לספק",
    "customers.messageStatusFailed": "נכשלה",
    "customers.error.NOT_AUTHORIZED":
      "אין הרשאה לצפות בכרטיסי הלקוחות כרגע. לבירור אפשר לפנות לבעלת הבוטיק.",
  },
} as const;
