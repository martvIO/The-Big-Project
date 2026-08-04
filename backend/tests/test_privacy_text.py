"""`resolve_privacy` across its whole input matrix, and the mechanical invariants
`.planning/design/screens/privacy/copy.md` computed for the approved Hebrew.

The invariants are re-asserted here rather than trusted from the deck because the
deck is a document and this is a build gate: copy.md checked them once, against
the strings as it drafted them, and nothing but this file checks them against the
strings as they actually shipped.

No database, no HTTP, no Settings — `app/privacy/text.py` is pure and this is what
proves it stays that way.
"""

from typing import Any

import pytest

from app.privacy.text import (
    PLATFORM_DISCLAIMER_HE,
    PLATFORM_DPA_HE,
    PLATFORM_ERASE_REASON_HINT_HE,
    PLATFORM_NOTICE_HE,
    PLATFORM_SUBPROCESSORS_HE,
    resolve_privacy,
)
from app.privacy.validation import MAX_PRIVACY_TEXT_BYTES

# The three documents a member of the public reads.
PUBLIC_DOCUMENTS = {
    "PLATFORM_NOTICE_HE": PLATFORM_NOTICE_HE,
    "PLATFORM_DPA_HE": PLATFORM_DPA_HE,
    "PLATFORM_SUBPROCESSORS_HE": PLATFORM_SUBPROCESSORS_HE,
}
# Plus the two the manage console renders and nobody outside the boutique sees.
ALL_STRINGS = PUBLIC_DOCUMENTS | {
    "PLATFORM_DISCLAIMER_HE": PLATFORM_DISCLAIMER_HE,
    "PLATFORM_ERASE_REASON_HINT_HE": PLATFORM_ERASE_REASON_HINT_HE,
}

# copy.md String 2, verbatim. NOT a constant in `text.py` — it is the closing
# block of the notice, and the deck is deliberate that there is one copy of it.
# Held here so an edit to the notice that drops or reworks the §30A revocation
# method fails a named test instead of passing every content assertion above it.
WITHDRAWAL_SENTENCE_HE = "אם סימנת אותה ואת רוצה להפסיק — אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת, בטלפון או בבוטיק. אין צורך להסביר למה, אפשר לומר זאת לכל אחת מאיתנו, וההסרה נכנסת לתוקף מיד. הסרת ההסכמה אינה משפיעה על התור שלך או על השירות שאת מקבלת."

# The three phrases that make the console disclaimer what it is: it says the text
# has not been reviewed by a lawyer. copy.md line 449 names exactly these.
DISCLAIMER_MARKERS = ("עורך דין", "ייעוץ משפטי", "נבדק")

# §11's elements, one phrase each, taken from copy.md's statutory duty map. Each
# is a substring of exactly the sentence that discharges its duty, so deleting
# that sentence from the notice reddens this and nothing else.
SECTION_11_ELEMENTS = (
    "{{boutique}}",  # §11(b)(1) — the controller, BY NAME, hence the template
    "בעל המאגר",  # §11(b)(1) — the statute's own term, not a paraphrase
    "לקבוע את התור שלך ולנהל אותו",  # §11(b)(2) — the purpose
    "מרצון",  # §11(b)(3) — voluntariness
    "אין חובה חוקית",  # §11(b)(3) — and the consequence of refusing
    "למי המידע מגיע",  # §11(b)(4) — recipients
    "לעיין במידע שנשמר עלייך",  # §13 — access
    "לבקש לתקן מידע שאינו מדויק",  # §14 — correction
    "לבקש למחוק את המידע",  # §14 — deletion
    "שלושים יום",  # §13/§14 — the response clock, spelled out (copy.md R8)
)

OVERRIDE = "נוסח שכתב עורך הדין של הבוטיק."


def test_no_privacy_string_can_carry_markup() -> None:
    """copy.md R6. These strings are rendered as text into a public page and an
    overriding boutique's copy of one is stored and served back, so a `<` in a
    platform default is stored XSS with a legal document as the vector.

    Asserted at the SOURCE as well as at the renderer: the renderer's escaping is
    a second control, and a default that needed escaping would mean the deck's
    plain-text promise had already been broken."""
    for name, value in ALL_STRINGS.items():
        assert "<" not in value, name


def test_the_withdrawal_sentence_survives_inside_the_notice() -> None:
    """Gate 1 Q4's ruling lives in one sentence, and it is the one clause no code
    change can discharge on its own: it tells her to ask THE BOUTIQUE, never a
    role she has no way to identify behind the counter.

    A substring assertion rather than an equality one because the sentence is the
    notice's closing block by design — copy.md is explicit that a second constant
    would be a second copy of a legal sentence."""
    assert WITHDRAWAL_SENTENCE_HE in PLATFORM_NOTICE_HE


def test_the_disclaimer_markers_are_confined_to_the_console_string() -> None:
    """Bidirectional, and both directions are real failures.

    Missing from the console string: the owner publishes un-reviewed Hebrew under
    her own name without being told it is un-reviewed (spec Risk 1). Present in a
    public document: a privacy notice that announces its own legal unreliability
    to the customer it is addressed to, which is worse than no notice."""
    for marker in DISCLAIMER_MARKERS:
        assert marker in PLATFORM_DISCLAIMER_HE, marker
        for name, document in PUBLIC_DOCUMENTS.items():
            assert marker not in document, f"{marker} leaked into {name}"


def test_every_default_fits_the_cap_the_editor_will_enforce() -> None:
    """BYTES, not characters — Hebrew is two bytes a character in UTF-8, so a
    character-counting assertion here would pass at twice the real size.

    Load-bearing for the two overridable documents specifically: the manage editor
    prefills the platform default, so a default over the cap is a textarea the
    owner cannot save back without deleting text she never wrote. The other three
    are checked on the same line because the bound costs nothing to hold."""
    for name, value in ALL_STRINGS.items():
        assert len(value.encode("utf-8")) <= MAX_PRIVACY_TEXT_BYTES, name


def test_the_notice_carries_every_section_11_element() -> None:
    """The notice is the text that legally discharges §11, rendered both at the
    moment of collection and on `/privacy` from this one constant (D13).

    Phrase-level rather than "is non-empty": a notice can be four kilobytes of
    Hebrew and still omit the consequence of refusing, which is the §11(b)(3) half
    that almost every real-world notice drops."""
    for element in SECTION_11_ELEMENTS:
        assert element in PLATFORM_NOTICE_HE, element


def test_an_absent_privacy_key_resolves_to_every_platform_default() -> None:
    """The shipped state of every tenant on the day this merges."""
    resolved = resolve_privacy({})
    assert resolved.notice_text == PLATFORM_NOTICE_HE
    assert resolved.dpa_text == PLATFORM_DPA_HE
    assert resolved.subprocessors_text == PLATFORM_SUBPROCESSORS_HE
    assert resolved.notice_is_default is True
    assert resolved.dpa_is_default is True


@pytest.mark.parametrize(
    "blob",
    [
        {},
        {"privacy": {}},
        {"privacy": None},
        {"privacy": "הודעת הפרטיות"},
        {"privacy": []},
        {"profile": {"essence": "x"}, "toggles": {}},
    ],
    ids=["empty", "empty-privacy", "null", "string", "list", "siblings-only"],
)
def test_a_privacy_blob_that_is_not_an_object_resolves_to_the_defaults(
    blob: dict[str, Any],
) -> None:
    """`settings` is JSONB written by a PUT and by nothing that validates its
    shape retroactively, so a blob whose `privacy` key is not an object is
    reachable. Every caller of `resolve_privacy` is rendering a document the law
    requires to be on the page, so the only safe answer is the default."""
    resolved = resolve_privacy(blob)
    assert resolved.notice_text == PLATFORM_NOTICE_HE
    assert resolved.dpa_text == PLATFORM_DPA_HE
    assert resolved.notice_is_default is True
    assert resolved.dpa_is_default is True


@pytest.mark.parametrize(
    "value",
    ["", "   ", "\n\n", "\t \n", None, 42, [], {}],
    ids=["empty", "spaces", "newlines", "mixed-space", "null", "int", "list", "object"],
)
def test_a_blank_or_non_string_override_reverts_to_the_platform_default(value: Any) -> None:
    """Blank means "use the default", NEVER "publish nothing", and it is the only
    revert an owner can actually reach: `merge_settings` is one
    `settings || :patch::jsonb` and `||` can add or replace a JSONB key but cannot
    remove one.

    The whitespace cases are the ones that bite. An owner clearing a textarea
    leaves a newline behind, `"\n"` is truthy, and a boutique publishing an empty
    privacy notice is exactly the non-compliance the page exists to declare
    against. Deleting the `.strip()` reddens four of these eight."""
    resolved = resolve_privacy({"privacy": {"notice_text": value, "dpa_text": value}})
    assert resolved.notice_text == PLATFORM_NOTICE_HE
    assert resolved.dpa_text == PLATFORM_DPA_HE
    assert resolved.notice_is_default is True
    assert resolved.dpa_is_default is True


def test_each_document_is_overridden_independently() -> None:
    """Two fields, one JSONB object, and a resolver that crossed them would be
    invisible until a boutique overrode exactly one of them — which is the common
    case, since counsel rewrites the notice far more often than the DPA clause."""
    notice_only = resolve_privacy({"privacy": {"notice_text": OVERRIDE}})
    assert notice_only.notice_text == OVERRIDE
    assert notice_only.notice_is_default is False
    assert notice_only.dpa_text == PLATFORM_DPA_HE
    assert notice_only.dpa_is_default is True

    dpa_only = resolve_privacy({"privacy": {"dpa_text": OVERRIDE}})
    assert dpa_only.dpa_text == OVERRIDE
    assert dpa_only.dpa_is_default is False
    assert dpa_only.notice_text == PLATFORM_NOTICE_HE
    assert dpa_only.notice_is_default is True

    both = resolve_privacy({"privacy": {"notice_text": OVERRIDE, "dpa_text": "אחר."}})
    assert (both.notice_text, both.dpa_text) == (OVERRIDE, "אחר.")
    assert both.notice_is_default is False
    assert both.dpa_is_default is False


def test_an_override_is_stripped_but_its_paragraphs_are_untouched() -> None:
    """The trailing newline a textarea leaves is not part of the document; the
    blank line BETWEEN two paragraphs is the document's only paragraph break
    (copy.md R1), so a resolver that normalised whitespace instead of stripping
    the ends would silently collapse every legal document it touched."""
    resolved = resolve_privacy({"privacy": {"notice_text": "\n  פסקה ראשונה.\n\nפסקה שנייה.  \n"}})
    assert resolved.notice_text == "פסקה ראשונה.\n\nפסקה שנייה."
    assert resolved.notice_is_default is False


@pytest.mark.parametrize(
    "blob",
    [
        {"privacy": {"subprocessors_text": "אנחנו לא נעזרות באף ספק."}},
        {"privacy": {"notice_text": OVERRIDE, "subprocessors_text": ""}},
        {"subprocessors_text": "לא רשימה"},
    ],
    ids=["direct", "alongside-a-real-override", "top-level"],
)
def test_the_subprocessor_list_ignores_every_override(blob: dict[str, Any]) -> None:
    """D14 / Gate 1 Q3, as a property of the resolver rather than of a validator.

    A boutique may rewrite what it promises about processing and may NOT misstate
    who the processors are — and the structural half matters more than the
    permission half: the list is the one document the platform must amend every
    time a processor is added, and under an overridable design that amendment
    would reach only the boutiques that never customised. The moment a real SMS
    provider goes live, every overriding boutique's disclosure would become false,
    permanently and silently, and spec Risk 7 says nothing in CI can detect it.

    Reddens the moment `subprocessors_text=PLATFORM_SUBPROCESSORS_HE` becomes
    `_override(privacy, "subprocessors_text")`."""
    assert resolve_privacy(blob).subprocessors_text == PLATFORM_SUBPROCESSORS_HE
