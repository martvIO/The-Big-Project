// Hebrew is the only locale in v1. Every visible string on the storefront lives
// here — no component may hardcode Hebrew. Interpolation uses i18next {{name}}
// placeholders; day labels are seven flat keys rather than an array, so nothing
// needs returnObjects.
export const he = {
  translation: {
    brand: {
      // Shown only before the boutique's own name arrives from /storefront/boutique.
      title: "חנות הכלות",
    },

    // Per-route <title>. Set on every client navigation (WCAG 2.4.2, Level A).
    doc: {
      catalog: "הקולקציה",
      dress: "פרטי השמלה",
      about: "על הבוטיק",
      accessibility: "הצהרת נגישות",
    },

    skip: {
      toContent: "דלג לתוכן",
    },

    nav: {
      backToCatalog: "חזרה לקולקציה",
    },

    common: {
      retry: "נסי שוב",
    },

    catalog: {
      empty: {
        title: "הקולקציה בדרך",
        body: "השמלות עולות לאתר בימים הקרובים. בינתיים אפשר לקבוע תור ולראות הכל מקרוב.",
      },
      error: "לא הצלחנו לטעון את הקולקציה כרגע.",
    },

    price: {
      // Occupies the same slot at the same height as a real price, so a mixed
      // grid never jumps.
      hidden: "מחיר בתיאום",
    },

    dress: {
      reserved: "הוזמן",
      sizes: "מידות",
      more: "עוד",
      less: "פחות",
      share: "שיתוף",
      shareCopied: "הקישור הועתק",
      // An archived dress is a 404 within the tenant — same copy as an unknown id.
      unavailable: "השמלה כבר לא זמינה",
      error: "לא הצלחנו לטעון את השמלה כרגע.",
      backToCatalog: "חזרה לקולקציה",
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
      // No `instagram` key: PublicProfileResponse carries no handle, so the row
      // can never render. It returns with the backend field, not before.
    },

    hours: {
      heading: "שעות פעילות",
      closed: "סגור",
      // Sun-first, matching the Israeli week and lib/hours.ts day indices.
      day: {
        sun: "א׳",
        mon: "ב׳",
        tue: "ג׳",
        wed: "ד׳",
        thu: "ה׳",
        fri: "ו׳",
        sat: "שבת",
      },
      today: "היום: {{hours}}",
      closedToday: "סגור היום",
      opensTomorrow: "נפתח מחר ב-{{time}}",
      opensOn: "נפתח ביום {{day}} ב-{{time}}",
      exceptionsLabel: "שעות מיוחדות",
      exceptionClosed: "{{date}} סגור",
      exceptionHours: "{{date}} {{open}}–{{close}}",
    },

    about: {
      heading: "על הבוטיק",
      error: "לא הצלחנו לטעון את פרטי הבוטיק כרגע.",
    },

    a11y: {
      statement: "הצהרת נגישות",
      menu: {
        trigger: "תפריט נגישות",
        contrast: "ניגודיות גבוהה",
        textSize: "הגדלת טקסט",
        readableFont: "גופן קריא",
        underlineLinks: "הדגשת קישורים",
        stopMotion: "עצירת אנימציות",
      },
    },

    // הצהרת נגישות — the /accessibility page. IS 5568 §35 makes this page and
    // its named coordinator a legal obligation, not a nicety.
    //
    // TODO(launch blocker): the four coordinator placeholder values below MUST
    // be replaced with the real platform-operator details before the pilot goes
    // live. They are one constant for every tenant — the platform operator, not
    // the boutique owner. Shipping the placeholders is a compliance failure.
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
        "הטקסט החלופי של תצלומי השמלות נגזר משם השמלה ואינו מתאר את פרטי הגזרה. נשמח לתאר כל שמלה בטלפון.",
      limitsNote: "אנחנו פועלות לתקן את המגבלות האלה בגרסאות הבאות של האתר.",

      coordinatorHeading: "רכז הנגישות",
      coordinatorIntro: "לכל פנייה בנושא נגישות אפשר ליצור קשר עם רכז הנגישות של הפלטפורמה:",
      coordinatorNameLabel: "שם",
      coordinatorName: "«שם רכז הנגישות — למילוי לפני העלייה לאוויר»",
      coordinatorRoleLabel: "תפקיד",
      coordinatorRole: "«תפקיד — למילוי לפני העלייה לאוויר»",
      coordinatorPhoneLabel: "טלפון",
      coordinatorPhone: "«מספר טלפון — למילוי לפני העלייה לאוויר»",
      coordinatorEmailLabel: "דוא״ל",
      coordinatorEmail: "«כתובת דוא״ל — למילוי לפני העלייה לאוויר»",

      reportHeading: "נתקלתם בבעיית נגישות?",
      reportBody:
        "אם משהו כאן לא עבד עבורכם, נשמח שתספרו לנו — עם תיאור הבעיה, כתובת העמוד וסוג המכשיר או הדפדפן שבו גלשתם. אנחנו מתחייבות לחזור אליכם ולטפל בפנייה.",

      updated: "עודכן לאחרונה: 27.7.2026",
    },

    // --- appended by the dress-detail page. Kept as its own top-level block,
    // not nested under `dress`, so concurrent edits to this file never land in
    // the same region. ---
    size: {
      // Per-size availability on the detail page. This is a SIZE-level marker,
      // not the dress-level out-of-stock badge, which the storefront never
      // renders — but "not available" still has to be readable as words, since
      // a dimmed chip alone is colour-only signalling.
      unavailable: "לא זמין",
    },
  },
} as const;
