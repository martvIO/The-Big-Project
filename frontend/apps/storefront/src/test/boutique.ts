// The three F20 privacy documents, as a fixture every `BoutiqueResponse` in the
// suite can spread.
//
// One shared const rather than three fields copied into eleven local fixtures:
// the fields are REQUIRED on the wire type (they are always present in the
// response — `resolve_privacy` is total and falls back to the platform Hebrew),
// so every fixture needs them, and a fourth document would otherwise be an
// eleven-file edit.
//
// The values are deliberately SHORT and deliberately NOT the real Hebrew. The
// approved text lives in exactly one place, `app/privacy/text.py`, and a copy of
// it here would be a second place for a legal string to drift — and a test that
// asserted against that copy would be asserting the fixture agrees with itself.
// What these do carry is the two SHAPES the rendering has to handle: the
// `{{boutique}}` token, and a blank-line paragraph break.
export const PRIVACY_FIXTURE = {
  privacy_notice_text: "הודעת ברירת מחדל של {{boutique}}.\n\nפסקה שנייה.",
  privacy_dpa_text: "סעיף עיבוד מידע של {{boutique}}.",
  privacy_subprocessors_text: "ספקי תשתית.",
} as const;
