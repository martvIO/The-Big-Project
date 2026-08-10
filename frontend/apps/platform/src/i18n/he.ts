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

    // ---- F26, from .planning/design/screens/invite-signup/design.md §1–§5 ----
    //
    // ⚠ THE CREATE FORM MINTS NO NEW FIELD KEYS. Design A1's declared deviation
    // from spec D8: slug / name / owner-email are byte-identical to the provision
    // form's, so it REUSES `platform.provision.slugLabel|slugHelp|slugInvalid|
    // slugReserved|nameLabel|ownerEmailLabel`. Three duplicate strings are a
    // drift surface for zero benefit. Only genuinely new copy gets a key.

    // §1 Invites table
    "platform.invites.heading": "הזמנות",
    "platform.invites.caption": "רשימת ההזמנות שנוצרו",
    "platform.invites.colName": "שם",
    "platform.invites.colSlug": "כתובת",
    "platform.invites.colOwnerEmail": "אימייל",
    "platform.invites.colStatus": "סטטוס",
    "platform.invites.colExpires": "בתוקף עד",
    "platform.invites.colActions": "פעולות",
    "platform.invites.statusOpen": "פתוחה",
    "platform.invites.statusRedeemed": "נוצלה",
    "platform.invites.statusExpired": "פג תוקף",
    "platform.invites.empty": "אין עדיין הזמנות. אפשר ליצור את הראשונה בטופס שלמטה.",
    "platform.invites.loadFailed": "לא הצלחנו לטעון את רשימת ההזמנות כרגע.",

    // §2 Create + the one-time link
    "platform.invites.createHeading": "הזמנה חדשה",
    "platform.invites.createCta": "יצירת הזמנה",
    "platform.invites.createdHeading": "ההזמנה נוצרה",
    // ⚠ <Trans>, NEVER t() — see the comment in Console.tsx beside the call
    // site. Two tag names because the two isolates are not interchangeable:
    // <bdi> wraps a url/slug/email, which is ALWAYS Latin, so its element takes
    // dir="ltr"; <name> wraps a boutique name, which may well be Hebrew, so its
    // element is a BARE <bdi /> (the BookPage lesson). A bare {{token}} in an
    // RTL sentence is the defect — the comma below is exactly the neutral
    // character that reorders without an isolate.
    "platform.invites.createdFor":
      "ההזמנה נוצרה עבור <name>{{name}}</name>, בכתובת <bdi>{{url}}</bdi>",
    "platform.invites.linkOnce":
      "הקישור מוצג פעם אחת בלבד. אחרי סגירת החלונית לא נציג אותו שוב, וגם לא נשמור אותו. אם הקישור אבד, אפשר לבטל את ההזמנה וליצור אחת חדשה.",
    "platform.invites.linkLabel": "קישור ההזמנה",
    "platform.invites.linkExpires": "הקישור בתוקף עד {{date}}",
    "platform.invites.linkDeliver":
      "יש למסור את הקישור לבעלת הבוטיק בעצמך. המערכת אינה מעבירה אותו לאיש.",
    "platform.invites.copy": "העתקת הקישור",
    "platform.invites.copied": "הקישור הועתק.",
    "platform.invites.copyFailed":
      "לא הצלחנו להעתיק את הקישור. אפשר לסמן אותו ולהעתיק ידנית.",
    // The single dismiss control, and its label states the consequence (A2 r2).
    "platform.invites.dismiss": "שמרתי את הקישור — סגירה",

    // §3 Revoke
    "platform.invites.revokeCta": "ביטול ההזמנה",
    "platform.invites.revokeTitle": "לבטל את ההזמנה?",
    // <Trans> again — the PARENTHESES are the neutral characters that reorder.
    "platform.invites.revokeBody":
      "הקישור שנמסר עבור <name>{{name}}</name> (<bdi>{{slug}}</bdi>) יפסיק לפעול מיד, וההזמנה תרד מהרשימה. אפשר ליצור הזמנה חדשה לאותה כתובת.",
    "platform.invites.revokeConfirm": "ביטול ההזמנה",
    // ⚠ NOT «ביטול» (design A4): a dialog whose confirm reads «ביטול ההזמנה»
    // beside a cancel reading «ביטול» is a mis-click generator. F25's
    // `platform.suspend.cancel` is untouched.
    "platform.invites.revokeCancel": "חזרה",

    // §4 Join — the one screen in this app a non-operator opens
    "platform.join.title": "MODRYN — הקמת בוטיק",
    "platform.join.checking": "בודקים את ההזמנה.",
    "platform.join.codeLabel": "קוד ההזמנה",
    "platform.join.codePrompt":
      "אפשר להדביק כאן את הקישור המלא שקיבלת, או את הקוד בלבד.",
    "platform.join.codeSubmit": "המשך",
    "platform.join.headingCode": "הזנת קוד הזמנה",
    "platform.join.heading": "הקמת הבוטיק",
    "platform.join.headingDone": "הבוטיק מוכן",
    "platform.join.claiming":
      "אלה הפרטים שאושרו לבוטיק. אם משהו כאן אינו נכון, כדאי לפנות ל‑MODRYN לפני שממשיכים.",
    "platform.join.boutiqueLabel": "שם הבוטיק",
    "platform.join.addressLabel": "כתובת הבוטיק",
    "platform.join.emailLabel": "אימייל של בעלת הבוטיק",
    "platform.join.password": "בחירת סיסמה",
    "platform.join.submit": "הקמת הבוטיק",
    "platform.join.success": "הבוטיק מוכן.",
    // <Trans>, tag `bdi` only — no name token. The password is never repeated.
    "platform.join.successBody":
      "אפשר להיכנס לניהול הבוטיק עם האימייל <bdi>{{email}}</bdi> והסיסמה שנבחרה.",
    "platform.join.toManage": "כניסה לניהול הבוטיק",
    "platform.join.loadFailed": "לא הצלחנו לבדוק את ההזמנה כרגע.",
    "platform.join.retry": "ניסיון נוסף",

    // §5 Refusals. ONE sentence for unknown / expired / redeemed / revoked —
    // the UI must not distinguish four states the server deliberately collapsed
    // into one 404 (D5 anti-enumeration).
    "platform.error.invalid_invite":
      "ההזמנה אינה תקפה. אפשר לבקש מ‑MODRYN הזמנה חדשה.",
    // ⚠ REACHED BY STATUS (429), NOT BY CODE. The server's body carries
    // `TOO_MANY_ATTEMPTS`; LoginPanel already branches on `status === 429` for
    // its own sentence, and this follows that shipped precedent rather than
    // minting a second key named after a wire constant. No countdown — the
    // window is server-side and a wrong number is worse than none.
    "platform.error.rate_limited":
      "יותר מדי ניסיונות. אפשר לנסות שוב בעוד מספר דקות.",
    // Join-SPECIFIC sentences for two codes the operator side already has. The
    // shipped operator copy («הכתובת הזו כבר תפוסה.») tells an owner nothing she
    // can act on — she never chose the address (D2). Lookup order in JoinPanel
    // is platform.join.error.{code} -> platform.error.{code} -> errorMessage().
    "platform.join.error.slug_taken":
      "הכתובת שהוקצתה לבוטיק אינה פנויה יותר. כדאי לפנות ל‑MODRYN לקבלת הזמנה חדשה.",
    "platform.join.error.invalid_or_reserved_slug":
      "הכתובת שהוקצתה לבוטיק אינה תקינה. כדאי לפנות ל‑MODRYN לקבלת הזמנה חדשה.",
  },
};
