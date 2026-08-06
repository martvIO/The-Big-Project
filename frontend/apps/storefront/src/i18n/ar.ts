// Arabic resource keys — SHIPPED, UNTRANSLATED.
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
// F16 is the first feature to add one, so this file starts with F16's keys only.
// Later features append theirs.
export const ar = {
  translation: {
    document: {
      manageTitle: "התור שלך",
      checkin: "רישום לתור",
      queuePosition: "מקומך בתור",
      queueBoard: "לוח התור",
      // F20.
      privacy: "הודעת פרטיות",
    },
    // F20. The footer link is on every route, so the notice is one tap from
    // any of them.
    footer: {
      privacy: "הודעת פרטיות",
    },
    manage: {
      title: "התור שלך",
      loading: "טוענות את פרטי התור",
      attendanceCta: "אישור הגעה",
      attendanceDone: "ההגעה אושרה. נתראה.",
      cancelCta: "ביטול התור",
      cancelQuestion: "לבטל את התור?",
      cancelPolicyLead: "לפי המדיניות שאישרת, אפשר לבטל עד",
      cancelPolicySuffix: "שעות לפני המועד.",
      cancelConsequenceFree: "לא נגבה תשלום על התור, כך שהביטול אינו כרוך בעלות.",
      cancelConfirm: "אישור הביטול",
      cancelKeep: "השארת התור",
      cancelled: "התור בוטל.",
      rebookCta: "קביעת תור חדש",
      past: "המועד הזה כבר עבר.",
      invalid: "הקישור הזה כבר לא תקף.",
      invalidHint: "לכל שאלה על התור, אפשר להתקשר לבוטיק.",
      loadFailed: "לא הצלחנו להציג את פרטי התור כרגע.",
      retry: "ניסיון נוסף",
      // F19.
      awaitingPayment: "התור שמור עבורך וממתין לתשלום המקדמה.",
      cancelConsequenceDeposit: "המקדמה מטופלת בהתאם למדיניות הביטולים של הבוטיק.",
    },
    booking: {
      confirmKeepScreen: "פרטי התור נשמרו אצלנו, וכדאי בכל זאת לצלם את המסך. אנחנו נחכה לך.",
      // F19 — the deposit hand-off's five states.
      payTitle: "תשלום מקדמה",
      payHandoff: "מעבירים אותך לתשלום",
      payManualHint: "אם הדף לא נפתח מעצמו, אפשר לעבור אליו מכאן.",
      payManualCta: "מעבר לתשלום",
      payAwaiting: "מאשרים את התשלום",
      payDeclined: "התשלום לא הושלם",
      payDeclinedBody: "אפשר להשלים את התשלום על אותה קביעת תור ובאותו סכום.",
      payExpired: "הזמן שמור לך פג",
      payUnresolved:
        "עדיין לא קיבלנו אישור על התשלום. אין צורך לשלם שוב — נשמח שתתקשרי אלינו ונבדוק יחד.",
      // F20. The collection notice's chrome and the marketing consent label.
      // ⚠ `marketingOptIn` is a LEGAL CONSENT STRING and is byte-identical to
      // `checkin.optIn` below in both bundles — an Arabic launch that translated
      // one and not the other would put two different §30A consents on one
      // product. It is not in the value-parity test for the reason `checkin`'s
      // two are: that guard is scoped to the four counsel-gated keys by name.
      collectionNoticeHeading: "המידע שאת מוסרת לנו",
      collectionNoticeLink: "לעמוד הפרטיות המלא",
      marketingOptIn:
        "אני מאשרת קבלת הודעות SMS מ{{boutique}} על מבצעים, קולקציות חדשות ואירועים. אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת.",
      marketingOptInHint: "לא חובה. קביעת התור אינה תלויה בסימון התיבה.",
    },
    // F19. The first `errors` key to reach this bundle — the block exists here
    // now so the next feature appends rather than re-deciding where it goes.
    errors: {
      bookingAwaitingPayment: "התור הזה ממתין לתשלום המקדמה, ולכן אי אפשר לעדכן אותו כרגע.",
    },
    // F22's booking-waitlist reveal — Hebrew values standing in, pre-decided
    // #47's file rule.
    waitlist: {
      cta: "הצטרפות לרשימת ההמתנה",
      send: "שליחת קוד אימות",
      sendWait: "אפשר לבקש קוד חדש בעוד רגע",
      sending: "שולחות את הקוד",
      join: "אישור והצטרפות לרשימה",
      joining: "רושמות אותך לרשימת ההמתנה",
      confirmed: "נרשמת לרשימת ההמתנה ליום {{date}}. אם יתפנה תור, נשלח לך הודעה.",
    },
    // F33's walk-in queue. `notice` and `optIn` are counsel-gated in he.ts and
    // are gated here too: the swap F20 makes is a TWO-FILE, two-string edit, and
    // an Arabic launch that shipped a translated notice while Hebrew still
    // carried the interim would be two different legal texts on one form.
    checkin: {
      heading: "רישום לתור",
      lastFromDevice: "הרישום האחרון שנעשה מהמכשיר הזה",
      // F60. Value-parity with he.ts is a TEST here, not a convention — the
      // storefront's first, deliberately scoped to these two keys. The hint names
      // the queue and states no data-handling fact, in both bundles.
      guideTrigger: "מה קורה אחרי הרישום?",
      guideHint:
        "הרישום מכניס אותך לתור ההמתנה של הבוטיק — בסיום נפתח עמוד עם מקומך בתור שאפשר להשאיר פתוח בטלפון, ואשת צוות תקרא לך בשם כשיגיע תורך.",
      name: "שם מלא",
      phone: "טלפון נייד",
      phoneHint: "כדי שנוכל לקרוא לך כשיגיע תורך. אפשר להזין עשר ספרות, למשל 0501234567.",
      visitType: "סוג הביקור",
      visitBride: "מדידת כלה",
      visitEvening: "שמלת ערב",
      visitTypeRequired: "צריך לבחור סוג ביקור כדי להמשיך",
      // F20's APPROVED REPLACEMENT for both values (copy.md Strings 6 and 7),
      // swapped here in the SAME COMMIT as he.ts. F59 amended these in both
      // files at once and it has to stay that way: it is one legal text, and a
      // launch carrying interim Arabic beside approved Hebrew would be two
      // different notices on one form. See he.ts for what was struck from each
      // and why. `i18n-keys.test.ts` now compares the two bundles' VALUES for
      // these two keys, which is what makes forgetting this file a red suite
      // rather than a silent divergence.
      notice:
        "הפרטים שאת מוסרת כאן נשמרים אצל {{boutique}} לצורך ניהול התור בלבד — לשמור את מקומך ולקרוא לך כשיגיע תורך. מסירתם היא מרצון; בלי שם ובלי מספר נייד לא נוכל לרשום אותך לתור, ותמיד אפשר לפנות לאחת מאיתנו כאן.\n\nמקומך בתור והמילה הראשונה בשם שהזנת מוצגים בלוח התור של הבוטיק — עמוד אינטרנט ציבורי שכל מי שיודע את כתובת האתר של הבוטיק יכול לפתוח, ולא רק מסך שנמצא בתוך החנות. מספר הטלפון שלך לא מוצג שם.\n\nהפרטים לא ישמשו לפניות שיווקיות אלא אם סימנת את התיבה שלמטה, ואפשר לבקש מאיתנו להסיר את ההסכמה בכל עת. את הפרטים אנחנו שומרות רק כל עוד הם דרושים לניהול התור, ואפשר לבקש מאיתנו לעיין במידע שנשמר עלייך, לתקן אותו או למחוק אותו. פירוט מלא בעמוד הפרטיות של האתר.",
      optIn:
        "אני מאשרת קבלת הודעות SMS מ{{boutique}} על מבצעים, קולקציות חדשות ואירועים. אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת.",
      submit: "הצטרפות לתור",
      submitting: "רושמות אותך לתור",
      budgetSpent:
        "יש כרגע הרבה רישומים לתור. אפשר לנסות שוב בעוד זמן מה, ואפשר פשוט לפנות אלינו כאן בבוטיק.",
      createFailed: "לא הצלחנו לרשום אותך לתור כרגע.",
      boutiqueUnavailable: "לא הצלחנו לטעון את פרטי הבוטיק כרגע.",
      loading: "טוענות את פרטי הבוטיק",
      positionLoading: "טוענות את מקומך בתור",
      positionLabel: "מקומך בתור",
      statusWaiting: "ממתינה",
      statusInService: "התור שלך התחיל",
      called: "אפשר לגשת לדלפק",
      closed: "הביקור הזה הסתיים.",
      backToCheckin: "רישום לתור חדש",
      notFound: "הקישור הזה כבר לא תקף.",
      notFoundHint: "אפשר להירשם לתור מחדש, ואפשר פשוט לפנות אלינו כאן בבוטיק.",
      loadFailed: "לא הצלחנו להציג את מקומך בתור כרגע.",
      retry: "ניסיון נוסף",
      pause: "השהיית העדכון",
      resume: "חידוש העדכון",
      pausedCue: "העדכון האוטומטי הושהה",
      resumedCue: "העדכון האוטומטי חודש",
      updatedAt: "עודכן",
      staleAt: "העדכון האחרון היה",
      pausedAt: "העדכון מושהה. עודכן",
    },
    // F59's wall board. Eight keys, matching he.ts exactly — the freshness,
    // pause and retry vocabulary lives in `checkin` above and is resolved from
    // there rather than duplicated here, on both bundles.
    queueBoard: {
      heading: "ממתינות בתור",
      empty: "אין כרגע ממתינות",
      emptyHint: "אפשר להצטרף לתור בסריקת הקוד שבבוטיק.",
      overflow: "ועוד {{count}} בתור",
      called: "גשי לדלפק",
      loading: "טוענות את לוח התור",
      loadFailed: "לא הצלחנו להציג את לוח התור כרגע.",
    },
    // F20's /privacy page chrome. The three DOCUMENTS are not here and are not
    // in he.ts either — they ride GET /storefront/boutique, so there is exactly
    // one copy of each and no bundle can drift from it.
    privacy: {
      title: "הודעת פרטיות",
      noticeHeading: "המידע שאנחנו אוספות ומה אנחנו עושות בו",
      dpaHeading: "מי מעבד את המידע ואיך הוא נשמר",
      subprocessorsHeading: "ספקי התשתית",
      updated: "עודכן לאחרונה: 4.8.2026",
    },
  },
} as const;
