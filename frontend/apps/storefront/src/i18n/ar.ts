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
  },
} as const;
