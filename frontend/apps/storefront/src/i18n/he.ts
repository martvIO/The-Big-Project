// Hebrew is the only locale in v1. Every visible string on the storefront lives
// here — no component may hardcode Hebrew. Interpolation uses i18next {{name}}
// placeholders.
//
// `hours.days` is a SEVEN-ITEM SUN-FIRST ARRAY feeding HoursTable.dayLabels.
// Read it with t("hours.days", { returnObjects: true }) as string[] — nothing in
// this repo declares CustomTypeOptions resource typing, so a bare t() is typed
// `string` and would fail the blocking `pnpm -r typecheck` CI step.
export const he = {
  translation: {
    // Per-route <title>. Set on every client navigation (WCAG 2.4.2, Level A).
    document: {
      catalog: "הקולקציה",
      dress: "פרטי השמלה",
      about: "על הבוטיק",
      accessibility: "הצהרת נגישות",
    },

    catalog: {
      // Shown only before the boutique's own name arrives from /storefront/boutique.
      essenceFallback: "חנות הכלות",
      // Occupies the same slot at the same height as a real price, so a mixed
      // grid never jumps.
      priceOnRequest: "מחיר בתיאום",
      reserved: "הוזמן",
      empty: "הקולקציה בדרך",
      emptyBody:
        "השמלות עולות לאתר בימים הקרובים. בינתיים אפשר לקבוע תור ולראות הכל מקרוב.",
      // The only path to dress 25 of ~60.
      more: "עוד שמלות",
      loading: "טוענת את הקולקציה",
      error: "לא הצלחנו לטעון את הקולקציה כרגע.",
      retry: "נסי שוב",
    },

    dress: {
      back: "חזרה לקולקציה",
      sizes: "מידות",
      available: "זמין",
      // A SIZE-level marker, not the dress-level out-of-stock badge, which the
      // storefront never renders — but "not available" still has to be readable
      // as words, since a dimmed chip alone is colour-only signalling.
      unavailable: "לא זמין",
      more: "עוד",
      less: "פחות",
      share: "שיתוף",
      shareCopied: "הקישור הועתק",
      // An archived dress is a 404 within the tenant — same copy as an unknown id.
      unavailableDress: "השמלה כבר לא זמינה",
      backToCatalog: "חזרה לקולקציה",
      error: "לא הצלחנו לטעון את השמלה כרגע.",
      reserved: "הוזמן",
    },

    about: {
      heading: "על הבוטיק",
      story: "הסיפור שלנו",
      hoursHeading: "שעות פעילות",
      closed: "סגור",
      closedToday: "סגור היום",
      opensTomorrow: "נפתח מחר ב-{{time}}",
      opensOn: "נפתח ביום {{day}} ב-{{time}}",
      today: "היום: {{hours}}",
      // A boutique with no weekly rules at all — the state every new tenant
      // ships in. Never blank, never "undefined", never yesterday's range.
      hoursUnavailable: "שעות הפעילות יתעדכנו בקרוב. אפשר להתקשר ולתאם.",
      exceptionsLabel: "שעות מיוחדות",
      exceptionClosed: "{{date}} סגור",
      exceptionHours: "{{date}} {{open}}–{{close}}",
      contactHeading: "יצירת קשר",
      error: "לא הצלחנו לטעון את פרטי הבוטיק כרגע.",
    },

    hours: {
      // Sun-first, matching the Israeli week and lib/hours.ts day indices.
      days: ["א׳", "ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "שבת"],
      closed: "סגור",
    },

    // The code, never the server's English message, selects one of these.
    errors: {
      tenantNotFound: "הבוטיק הזה לא זמין כרגע.",
      notFound: "הפריט המבוקש לא נמצא.",
      tooManyAttempts: "יותר מדי בקשות. נסי שוב בעוד רגע.",
      validation: "הבקשה לא תקינה.",
      unknown: "אירעה שגיאה בלתי צפויה. נסי שוב.",
    },

    gallery: {
      previous: "התמונה הקודמת",
      next: "התמונה הבאה",
      imageOf: "תמונה {{n}} מתוך {{total}}",
    },

    booking: {
      cta: "קביעת תור למדידה",
      panelTitle: "לקביעת תור, דברו איתנו",
      close: "סגירה",
    },

    contact: {
      call: "חיוג",
      whatsapp: "וואטסאפ",
      waze: "ניווט ב-Waze",
      maps: "פתיחה ב-Google Maps",
      instagram: "אינסטגרם",
    },

    footer: {
      contactHeading: "יצירת קשר",
      about: "על הבוטיק",
    },

    a11y: {
      skipLink: "דלג לתוכן",
      statementLink: "הצהרת נגישות",
      menuTrigger: "תפריט נגישות",
      contrast: "ניגודיות גבוהה",
      textSize: "הגדלת טקסט",
      readableFont: "גופן קריא",
      underlineLinks: "הדגשת קישורים",
      stopMotion: "עצירת אנימציות",
    },

    // הצהרת נגישות — the /accessibility page. IS 5568 §35 makes this page and a
    // named, reachable contact inside it a legal obligation, not a nicety.
    //
    // The responsible party is THE BOUTIQUE: it is the service provider, and its
    // own phone and Instagram come from the layout-level getBoutique(). There is
    // deliberately no platform-operator coordinator layer — the spec's design
    // gate names the boutique, and a statement that declares conformance while
    // showing «fill this in» is itself the non-conformance it declares against.
    statement: {
      title: "הצהרת נגישות",
      intro:
        "אנחנו מאמינות שכל אחת ואחד צריכים להיות מסוגלים לגלוש כאן, לראות את השמלות ולקבוע תור — בלי מחסומים. השקענו מאמץ כדי שהאתר יהיה נגיש, ואנחנו ממשיכות לשפר אותו.",

      conformanceHeading: "רמת הנגישות של האתר",
      conformanceBody:
        "האתר נבנה בהתאם לתקן הישראלי ת״י 5568 ברמת AA, המבוסס על הנחיות WCAG 2.0 של ארגון התקינה W3C.",

      doneHeading: "מה עשינו כדי להנגיש את האתר",
      doneFonts:
        "הגופנים העבריים מתארחים בשרת שלנו ואינם נטענים משירות חיצוני, כדי שהטקסט יופיע מיד ובצורה קריאה גם בחיבור איטי.",
      doneKeyboard:
        "אפשר להפעיל את כל האתר במקלדת בלבד. סדר המעבר בין הרכיבים תואם לסדר שרואים על המסך, ולכל רכיב פעיל יש סימון מיקוד ברור. בראש כל עמוד יש קישור דילוג ישירות אל התוכן.",
      doneContrast:
        "כל צירופי הצבעים באתר נבדקו ועומדים ביחס ניגודיות של 4.5:1 לפחות בטקסט רגיל.",
      doneRtl:
        "האתר כולו בעברית ובכיוון מימין לשמאל, כולל האזורים שמכילים ספרות, מספרי טלפון וכתובות אינטרנט באנגלית.",
      doneImages:
        "לכל תצלום שמלה יש טקסט חלופי, וקישוטים גרפיים מוסתרים מקוראי מסך כדי לא להעמיס.",
      doneMenu:
        "באתר תפריט נגישות משלנו — לא הרחבה חיצונית — הזמין בכל עמוד בפינה התחתונה.",

      menuHeading: "מה עושה כל אפשרות בתפריט הנגישות",
      menuContrast: "ניגודיות גבוהה — מחזקת את הניגוד בין הטקסט לרקע.",
      menuTextSize: "הגדלת טקסט — מגדילה את כל הטקסטים באתר.",
      menuReadableFont: "גופן קריא — מחליף את הגופן העיצובי בגופן פשוט וברור יותר.",
      menuUnderlineLinks: "הדגשת קישורים — מוסיפה קו תחתון לכל הקישורים כדי שיבלטו בתוך הטקסט.",
      menuStopMotion: "עצירת אנימציות — מבטלת מעברים ותנועה באתר.",
      menuNote:
        "ההעדפות חלות על הגלישה הנוכחית בלבד ואינן נשמרות במכשיר, מפני שאיננו שומרים מידע על הגולשים.",

      limitsHeading: "מגבלות שאנחנו מודעות להן",
      limitsZoom:
        "בשלב זה אין באתר אפשרות להגדלת תצלומי שמלות. אפשר להיעזר בהגדלת התצוגה של הדפדפן.",
      limitsAlt:
        "הטקסט החלופי של תצלומי השמלות נגזר משם השמלה ואינו מתאר את פרטי הגזרה. בעמוד השמלה, שם השמלה מוקרא פעמיים ברצף — פעם מהכותרת ופעם מהתצלום. נשמח לתאר כל שמלה בטלפון.",
      limitsNote: "אנחנו פועלות לתקן את המגבלות האלה בגרסאות הבאות של האתר.",

      coordinatorHeading: "פניות בנושא נגישות",
      coordinatorIntro: "לכל פנייה בנושא נגישות אפשר ליצור קשר ישירות עם הבוטיק:",
      coordinatorPhoneLabel: "טלפון",
      coordinatorInstagramLabel: "אינסטגרם",

      reportHeading: "נתקלתם בבעיית נגישות?",
      reportBody:
        "אם משהו כאן לא עבד עבורכם, נשמח שתספרו לנו — עם תיאור הבעיה, כתובת העמוד וסוג המכשיר או הדפדפן שבו גלשתם. אנחנו מתחייבות לחזור אליכם ולטפל בפנייה.",

      updated: "עודכן לאחרונה: 28.7.2026",
    },
  },
} as const;
