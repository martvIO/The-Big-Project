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
      // ONE title for all five booking steps — the flow is one page to the tab
      // strip, and it is the h1 of the two no-step degrade screens as well.
      book: "קביעת תור",
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
      // Booking mid-flow conflicts and dead ends — copy.md §3.7, all APPROVED.
      slotUnavailable:
        "המועד הזה נתפס בינתיים. אלה המועדים הפנויים המעודכנים — אפשר לבחור מועד אחר.",
      termsStale:
        "מדיניות הביטולים התעדכנה בזמן שמילאת את הפרטים. זו הגרסה המעודכנת — נשמח שתקראי ותאשרי אותה שוב.",
      otpInvalid: "הקוד שהוזן אינו נכון. אפשר להקליד אותו שוב, או לבקש קוד חדש.",
      otpExpired: "תוקף הקוד פג. אפשר לבקש קוד חדש.",
      phoneNotVerified:
        "האימות פג תוקף. אפשר לבקש קוד חדש ולהמשיך מכאן — הפרטים שמילאת נשמרו.",
      // One string for both 503 codes — SMS_NOT_CONFIGURED and SMS_UNAVAILABLE.
      smsUnavailable:
        "אימות הטלפון אינו זמין כרגע, ולכן אי אפשר להשלים כאן את קביעת התור. נשמח שתתקשרי אלינו ונקבע יחד מועד.",
      // A 429 on /otp/send only. The wait is about an hour, so it offers the
      // phone rather than a retry — which is what tooManyAttempts would say.
      otpSendBudget:
        "ביקשת כמה קודים בזמן קצר. אפשר לנסות שוב עוד כשעה, ואפשר פשוט להתקשר אלינו ונקבע יחד מועד.",
    },

    gallery: {
      previous: "התמונה הקודמת",
      next: "התמונה הבאה",
      imageOf: "תמונה {{n}} מתוך {{total}}",
    },

    // The /book flow — copy.md rev 3, all 61 rows APPROVED 2026-07-29.
    booking: {
      cta: "קביעת תור למדידה",
      panelTitle: "לקביעת תור, דברו איתנו",
      close: "סגירה",

      // Step labels. Each is also its step's h1, so they are static strings by
      // design: an h1 built from fetched data has a state where it is missing.
      // stepOtp is named for what the step asks for, not for its /verify slug.
      stepsLabel: "שלבי קביעת התור",
      stepSlot: "מועד",
      stepDetails: "פרטים",
      stepTerms: "מדיניות ביטולים",
      stepOtp: "אימות טלפון",
      // Steps 1–3 advance; step 4 commits, and uses booking.submit.
      continue: "המשך",
      backStep: "חזרה לשלב הקודם",
      backToCatalog: "חזרה לקולקציה",

      typeHeading: "סוג הפגישה",
      // The RLM keeps the leading numeral from reordering against the Hebrew
      // that follows it — the one interpolated string that opens with the value.
      typeDuration: "‏{{minutes}} דקות",
      // A label on a brides-only type, not a lock: the type stays selectable.
      audienceBrides: "פגישת כלה",
      // Sits above a ContactPanel, which is why it carries no phone invitation
      // of its own.
      noTypes: "בשלב זה אין כאן סוגי פגישות לקביעה מקוונת.",
      pickDate: "תאריך",
      pickTime: "שעה",
      forDress: "עבור {{dress}}",
      noSlots:
        "אין מועדים פנויים בתאריך הזה. אפשר לבחור תאריך אחר, ואפשר גם להתקשר ונמצא לך מועד.",
      slotsError: "לא הצלחנו לטעון את המועדים כרגע.",
      // Not an error and not an apology: a deposit appointment is arranged by
      // phone by design.
      depositByPhone:
        "את הפגישה הזאת אנחנו קובעות בטלפון, כדי לסגור יחד גם את המקדמה. נשמח שתתקשרי — זה לוקח רגע.",

      name: "שם מלא",
      nameRequired: "צריך למלא שם כדי שנוכל לרשום את התור.",
      // 80 and 500 mirror MAX_CUSTOMER_NAME_LENGTH and MAX_BOOKING_NOTES_LENGTH.
      nameTooLong: "השם ארוך מדי. עד 80 תווים.",
      phone: "טלפון נייד",
      // The only place the format is taught, so it must match validatePhone.
      phoneHint: "לשליחת קוד אימות חד-פעמי. אפשר להזין עשר ספרות, למשל 0501234567.",
      phoneInvalid: "המספר לא נראה כמו מספר נייד ישראלי. אפשר להזין עשר ספרות שמתחילות ב-05.",
      notes: "משהו שנשמח לדעת מראש",
      notesHint: "לא חובה. למשל: מגיעה עם אמא, צריך שולחן נגיש, או דגם שראית ואהבת.",
      notesTooLong: "ההערה ארוכה מדי. עד 500 תווים.",
      // Rendered INSIDE the unavailable chip's own label, so it becomes part of
      // that radio's accessible name — which is why it is ≤24 characters and
      // why the longer invitation is a separate key under the group.
      sizeUnavailable: "אפשר להזמין במיוחד",
      sizeRequired: "צריך לבחור מידה כדי להמשיך",
      sizeUnavailableNote: "מידה שאינה כרגע בבוטיק אפשר להזמין במיוחד לקראת המדידה.",

      termsHeading: "מדיניות ביטולים",
      refundWindow: "ביטול עד {{hours}} שעות לפני המועד — ללא חיוב.",
      // Percent OF THE DEPOSIT — the base the manage console already states.
      forfeit: "ביטול מאוחר יותר, או אי-הגעה — חיוב של {{percent}}% מהמקדמה.",
      acceptTerms: "קראתי את מדיניות הביטולים ואני מסכימה לה.",
      acceptRequired: "כדי להמשיך צריך לאשר את מדיניות הביטולים.",
      noTermsByPhone:
        "קביעת תור מקוונת תיפתח כאן בקרוב. בינתיים נשמח שתתקשרי אלינו ונקבע יחד מועד.",

      // Conditional, never a delivery claim: /storefront/otp/send always answers
      // 204 and reveals nothing.
      otpSent: "שלחנו קוד בן שש ספרות למספר שהזנת. הוא תקף לחמש דקות.",
      otpCode: "קוד האימות",
      // One label for the first send AND the resend — it may not say "again".
      otpResend: "שליחת קוד אימות",
      // No interpolated countdown: Hebrew has no correct singular/dual here
      // without plural resources, and a ticking number reads as urgency.
      otpResendWait: "אפשר לבקש קוד חדש בעוד רגע",
      submit: "אישור וקביעת התור",
      submitting: "קובעות את התור",

      // F16 has not shipped: a booking sends NO message, so this screen is her
      // only record and nothing here may promise one.
      confirmTitle: "התור נקבע",
      confirmTitleNamed: "התור נקבע ב{{name}}",
      // Bare labels, not sentences: the date, time and type beside them are
      // wrapped in <bdi dir="ltr"> at the call site, which interpolation cannot
      // do.
      confirmWhen: "מתי",
      confirmWhat: "מה",
      confirmDress: "{{dress}} · מידה {{size}}",
      confirmKeepScreen:
        "זה האישור היחיד שלך — כדאי לצלם את המסך או לשמור אותו. אנחנו נחכה לך.",
      confirmCold: "התור שלך נקבע. אם תרצי לוודא את הפרטים — אפשר להתקשר ונאשר לך הכול.",

      typeGoneRepick: "סוג הפגישה שבחרת כבר אינו זמין. אפשר לבחור סוג אחר מהרשימה המעודכנת.",
      dressGoneGeneric:
        "השמלה שבחרת כבר אינה זמינה. אפשר להמשיך ולקבוע פגישת מדידה רגילה — נשמח למצוא איתך דגמים דומים.",
      sizeGoneRepick: "המידה שבחרת כבר אינה מופיעה ברשימה. אפשר לבחור מידה אחרת מהרשימה המעודכנת.",
      // Replaces the ContactPanel in all four of its branches when the boutique
      // fetch failed. Name-free by construction: that fetch carried the name.
      contactUnavailable:
        "לא הצלחנו לטעון כאן את פרטי הקשר של הבוטיק. אפשר לנסות לרענן את העמוד בעוד רגע.",
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
      // Must keep describing what the site ACTUALLY does: the card alt is the
      // dress name, and the dress page's main photo announces its position in
      // the gallery, not the garment. A statement that misdescribes the site is
      // itself a non-conformance.
      limitsAlt:
        "בעמוד הקולקציה הטקסט החלופי של כל תצלום הוא שם השמלה בלבד, ואינו מתאר את הגזרה, הבד או הפרטים. בעמוד השמלה התצלומים מוקראים לפי מיקומם בגלריה, למשל: תמונה 1 מתוך 3, ושם השמלה מופיע בכותרת העמוד. נשמח לתאר כל שמלה בטלפון.",
      limitsNote: "אנחנו פועלות לתקן את המגבלות האלה בגרסאות הבאות של האתר.",

      coordinatorHeading: "פניות בנושא נגישות",
      coordinatorIntro: "לכל פנייה בנושא נגישות אפשר ליצור קשר ישירות עם הבוטיק:",
      coordinatorPhoneLabel: "טלפון",
      coordinatorInstagramLabel: "אינסטגרם",
      // A tenant that published neither a phone nor an Instagram — and any
      // tenant whose boutique fetch failed. §35 wants a reachable channel, so
      // the statement says plainly that none is published here and sends the
      // visitor to the boutique itself, instead of an empty contact list.
      coordinatorNoChannel:
        "בשלב זה לא פורסמו כאן מספר טלפון או חשבון אינסטגרם. אפשר לפנות בנושא נגישות ישירות אל {{name}}, בבוטיק עצמו, וכל פנייה תטופל.",

      reportHeading: "נתקלתם בבעיית נגישות?",
      reportBody:
        "אם משהו כאן לא עבד עבורכם, נשמח שתספרו לנו — עם תיאור הבעיה, כתובת העמוד וסוג המכשיר או הדפדפן שבו גלשתם. אנחנו מתחייבות לחזור אליכם ולטפל בפנייה.",

      updated: "עודכן לאחרונה: 28.7.2026",
    },
  },
} as const;
