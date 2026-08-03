"""Pure domain validation for the customers CRM — no I/O, unit-tested locally.

Two write-time gates (tags, notes) and one read-time helper. The helper is the
one that earns its own module: `customers.phone` only ever holds strict E.164,
because `normalize_israeli_mobile` rewrites a typed `05X…` to `972` + the rest
before either writer stores it, so an unanchored ILIKE on what an owner types at
the desk (`0501234567`, or the prefix `050`) matches nothing at all. Normalizing
the digits of the search term the same way is what makes the phone leg work.
"""

import re

# The two C0 classes below are underscore-private and this is the first
# cross-module import of either. `_CONTROL_CHARS` (the whole C0 set) is the right
# one for a tag, which is a one-line chip label — a newline inside a TEXT[]
# element renders two lines tall and copies wrong. `_CONTROL_CHARS_EXCEPT_WS`
# permits tab/newline/return and is the right one for notes, a paragraph.
from app.booking.validation import _CONTROL_CHARS, _CONTROL_CHARS_EXCEPT_WS
from app.errors import DomainValidationError


class CustomerValidationError(DomainValidationError):
    """Domain-rule violation on a customer notes/tags write; the router maps it
    to the house-shape 400.

    Re-parented onto the shared base so one handler serves every domain module;
    behaviour-neutral, since Starlette still matches this class through its MRO."""


# A tag is a chip on a 720px-capped column. Longer than this and it is a note,
# and there is a field for notes.
MAX_TAG_LENGTH = 24

# Ten chips is the most that reads as a set rather than a paragraph. It is also
# what makes "no autocomplete" honest — saving a handful of keystrokes on a
# ten-item set is not worth an endpoint and a WCAG-conformant combobox.
MAX_TAGS = 10

# The profile-description peer (`boutique/validation.py:30`), NOT booking-notes'
# 500: a booking note is about one appointment, a CRM note accretes across every
# visit a bride makes over a year of fittings.
MAX_CUSTOMER_NOTES_LENGTH = 2000

# Mirrors MAX_CUSTOMER_NAME_LENGTH — the longest thing that can legitimately be
# searched for. An unbounded term is one annotation away from being a free
# ILIKE-pattern knob on a role-gated but session-cheap route.
MAX_SEARCH_TERM_LENGTH = 80


def normalize_tags(tags: list[str]) -> list[str]:
    """Trim, drop empties, reject control characters and over-long elements,
    then dedup case-insensitively keeping the FIRST occurrence and its casing.

    Caller order is preserved: the order the owner arranged them in is
    information, and alphabetizing on save is the product rearranging her
    screen. The cap is checked AFTER dedup — checking it first would let ten
    duplicates crowd out a real eleventh tag.
    """
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        tag = raw.strip()
        if not tag:
            continue
        if _CONTROL_CHARS.search(tag) is not None:
            raise CustomerValidationError("tags: a tag contains invalid characters")
        if len(tag) > MAX_TAG_LENGTH:
            raise CustomerValidationError("tags: a tag is too long")
        folded = tag.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        normalized.append(tag)
    if len(normalized) > MAX_TAGS:
        raise CustomerValidationError(f"tags: at most {MAX_TAGS} tags are allowed")
    return normalized


def validate_notes(notes: str) -> None:
    """Empty string = cleared field, so blankness is never an error here."""
    if len(notes) > MAX_CUSTOMER_NOTES_LENGTH:
        raise CustomerValidationError("notes is too long")
    if _CONTROL_CHARS_EXCEPT_WS.search(notes) is not None:
        raise CustomerValidationError("notes contains invalid characters")


def phone_search_term(term: str) -> str | None:
    """The digits of `term` in the form the phone column actually stores, or
    None when the term carries no digits at all.

    `None` skips the phone leg entirely, so a pure-Hebrew term costs no second
    predicate. A prefix survives the same rule — `"050"` becomes `"97250"`, a
    genuine substring of `+972501234567` — which is the point.
    """
    digits = re.sub(r"\D", "", term)
    if not digits:
        return None
    if digits.startswith("05"):
        digits = "972" + digits[1:]
    return digits
