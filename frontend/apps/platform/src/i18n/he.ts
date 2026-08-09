// F25's copy deck, transcribed from
// .planning/design/screens/platform-console/design.md §Copy deck §1–§6.
//
// DOTTED LITERAL KEYS, one per row of the deck — i18next resolves them through
// `ignoreJSONStructure`, and `__tests__/i18n.test.ts` is the proof, because a
// silently unresolved key renders the key itself onto the screen.
//
// ⚠ ZERO EXCLAMATION MARKS (#5) and NO FORM OF «נשלח» IN ANY TENSE: no channel
// exists — the operator hands the password over herself. Both are enforced
// mechanically by the guard test, not by review.
export const he = {
  translation: {
    // §1 Login and session
    "platform.login.title": "MODRYN — ניהול הפלטפורמה",
    "platform.login.email": "אימייל",
    "platform.login.password": "סיסמה",
    "platform.login.submit": "כניסה",
    "platform.login.failed": "האימייל או הסיסמה אינם נכונים.",
    "platform.login.tooMany":
      "יותר מדי ניסיונות כניסה. אפשר לנסות שוב בעוד מספר דקות.",
    "platform.login.sessionExpired": "ההתחברות הסתיימה. יש להיכנס שוב.",
    "platform.heading": "ניהול הפלטפורמה",
    "platform.logoutCta": "יציאה",

    // §2 Tenant table
    "platform.tenants.heading": "בוטיקים",
    "platform.tenants.filterLabel": "סינון לפי שם או כתובת",
    "platform.tenants.colName": "שם",
    "platform.tenants.colSlug": "כתובת",
    "platform.tenants.colStatus": "סטטוס",
    "platform.tenants.colCreated": "נוצר",
    "platform.tenants.colActions": "פעולות",
    "platform.tenants.caption": "רשימת הבוטיקים בפלטפורמה",
    "platform.tenants.statusActive": "פעיל",
    "platform.tenants.statusSuspended": "מושהה",
    "platform.tenants.empty":
      "אין עדיין בוטיקים במערכת. אפשר להקים את הראשון בטופס שלמטה.",
    "platform.tenants.filterNoMatch": "אף בוטיק אינו תואם את הסינון.",
    "platform.tenants.loadFailed": "לא הצלחנו לטעון את רשימת הבוטיקים כרגע.",
    "platform.tenants.suspendCta": "השהיה",
    "platform.tenants.resetCta": "איפוס סיסמת בעלים",

    // §3 Suspend confirm
    "platform.suspend.title": "להשהות את הבוטיק?",
    "platform.suspend.body":
      "הבוטיק {{name}} ({{slug}}) יפסיק להיות זמין ללקוחות ולצוות מיד. אין בקונסולה פעולת הפעלה מחדש.",
    "platform.suspend.confirm": "השהיה",
    "platform.suspend.cancel": "ביטול",

    // §4 Reset owner password
    "platform.reset.title": "איפוס סיסמה — {{name}}",
    "platform.reset.emailLabel": "אימייל של בעלת הבוטיק",
    "platform.reset.emailHelp": "חייב להתאים לבעלת הבוטיק הרשומה.",
    "platform.reset.passwordLabel": "סיסמה חדשה",
    "platform.reset.notice":
      "יש למסור את הסיסמה החדשה לבעלת הבוטיק בעצמך. המערכת אינה מציגה אותה שוב.",
    "platform.reset.submit": "איפוס סיסמה",
    "platform.reset.done": "הסיסמה אופסה. יש למסור אותה לבעלת הבוטיק בעצמך.",

    // §5 Provision form
    "platform.provision.heading": "בוטיק חדש",
    "platform.provision.slugLabel": "כתובת (תת־דומיין)",
    "platform.provision.slugHelp": "הכתובת תהיה {{slug}}.modryn.co.il",
    "platform.provision.slugInvalid":
      "הכתובת יכולה להכיל אותיות לטיניות קטנות, ספרות ומקפים בלבד.",
    "platform.provision.slugReserved": "הכתובת הזו שמורה למערכת ואינה זמינה.",
    "platform.provision.nameLabel": "שם הבוטיק",
    "platform.provision.ownerEmailLabel": "אימייל של בעלת הבוטיק",
    "platform.provision.ownerPasswordLabel": "סיסמה ראשונית",
    "platform.provision.passwordNotice":
      "יש למסור את הסיסמה לבעלת הבוטיק בעצמך. המערכת אינה מעבירה אותה לאיש.",
    "platform.provision.submitCta": "הקמת בוטיק",
    "platform.provision.done": "הבוטיק הוקם. הכתובת: {{url}}",

    // §6 Error codes → Hebrew. Keyed on the server's own refusal string; an
    // unlisted code falls through to errorMessage().
    "platform.error.slug_taken": "הכתובת הזו כבר תפוסה.",
    "platform.error.invalid_or_reserved_slug": "הכתובת אינה תקינה או שמורה למערכת.",
    "platform.error.empty_password": "יש להזין סיסמה.",
    // One key beyond the deck's §6, and it is the server's own new refusal code:
    // the same 10-character floor the staff screen enforces now covers the
    // owner's initial password and its reset. The number is in the sentence
    // because "too short" without it sends the operator guessing.
    "platform.error.password_too_short": "הסיסמה חייבת להכיל לפחות 10 תווים.",
    "platform.error.tenant_not_found": "הבוטיק לא נמצא. כדאי לרענן את הרשימה.",
    "platform.error.owner_not_found": "האימייל אינו תואם את בעלת הבוטיק הרשומה.",

    // ⚠ TWO KEYS BEYOND THE DECK, and the addition is recorded rather than
    // slipped in. The design covers login, the table, both forms and both
    // modals; it does not cover the ROOT CRASH state, because that state is not
    // a screen anyone designed — it is what `main.tsx`'s ErrorBoundary renders
    // when React 19 unmounts the tree on an uncaught render error. Without a
    // string there the console is a blank white page with no text and no
    // control. Both are lifted verbatim from the manage app's equivalents
    // (`dashboard.loadFailed`, `board.reload`) rather than newly written, so no
    // unreviewed register enters at the one place copy cannot be reviewed in
    // context.
    "platform.crash.body": "לא הצלחנו לטעון את הנתונים כרגע.",
    "platform.crash.reload": "רענון הדף",
  },
};
