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
    },
    // F19. The first `errors` key to reach this bundle — the block exists here
    // now so the next feature appends rather than re-deciding where it goes.
    errors: {
      bookingAwaitingPayment: "התור הזה ממתין לתשלום המקדמה, ולכן אי אפשר לעדכן אותו כרגע.",
    },
    // F33's walk-in queue. `notice` and `optIn` are counsel-gated in he.ts and
    // are gated here too: the swap F20 makes is a TWO-FILE, two-string edit, and
    // an Arabic launch that shipped a translated notice while Hebrew still
    // carried the interim would be two different legal texts on one form.
    checkin: {
      heading: "רישום לתור",
      lastFromDevice: "הרישום האחרון שנעשה מהמכשיר הזה",
      name: "שם מלא",
      phone: "טלפון נייד",
      phoneHint: "כדי שנוכל לקרוא לך כשיגיע תורך. אפשר להזין עשר ספרות, למשל 0501234567.",
      visitType: "סוג הביקור",
      visitBride: "מדידת כלה",
      visitEvening: "שמלת ערב",
      visitTypeRequired: "צריך לבחור סוג ביקור כדי להמשיך",
      // F59 amended this value in BOTH files at once, and it has to stay that
      // way: it is one legal text, and an Arabic launch that carried the
      // pre-board wording while Hebrew carried the board clause would be two
      // different notices on one form. See he.ts for why each phrase is what it
      // is.
      notice:
        "הפרטים שאת ממלאת כאן נשמרים אצל {{boutique}} לצורך ניהול התור בלבד — לשמור את מקומך ולקרוא לך כשיגיע תורך — ונמחקים כמה ימים לאחר הביקור. מקומך בתור והמילה הראשונה בשם שהזנת מוצגים בלוח התור של הבוטיק — עמוד אינטרנט ציבורי שכל מי שיודע את כתובת האתר של הבוטיק יכול לפתוח, ולא רק מסך שנמצא בתוך החנות. מספר הטלפון שלך לא מוצג שם. הפרטים לא ישמשו לפניות שיווקיות אלא אם סימנת את התיבה שלמטה; אם סימנת אותה, השם ומספר הטלפון יישמרו לצורך זה עד שתבקשי להסיר את ההסכמה.",
      optIn:
        "אני מאשרת ש{{boutique}} תשלח לי הודעות SMS על מבצעים, קולקציות חדשות ואירועים. אפשר להסיר את ההסכמה בכל הודעה.",
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
  },
} as const;
