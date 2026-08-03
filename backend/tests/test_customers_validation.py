"""Pure-validation units for Feature 53 — no database, no event loop.

The load-bearing case is `phone_search_term`: `customers.phone` only ever holds
strict E.164, so an unanchored ILIKE on what a human types at the desk matches
nothing at all. The digit table below is the whole difference between a working
search box and one that answers «אין תוצאות» for a customer who exists.
"""

from collections.abc import Callable

import pytest

from app.customers.validation import (
    MAX_CUSTOMER_NOTES_LENGTH,
    MAX_SEARCH_TERM_LENGTH,
    MAX_TAG_LENGTH,
    MAX_TAGS,
    CustomerValidationError,
    normalize_tags,
    phone_search_term,
    validate_notes,
)
from app.errors import DomainValidationError

# --- normalize_tags ---


def test_tags_are_trimmed_and_empty_elements_dropped() -> None:
    assert normalize_tags(["  כלה  ", "", "   ", "\t\n", " ערב "]) == ["כלה", "ערב"]


def test_dedup_is_case_insensitive_and_the_first_occurrence_keeps_its_casing() -> None:
    assert normalize_tags(["VIP", "vip", " Vip "]) == ["VIP"]


def test_caller_order_is_preserved_and_never_sorted() -> None:
    # Sorted order differs from caller order, so an accidental sorted() red-fails.
    assert normalize_tags(["zebra", "alpha", "mango"]) == ["zebra", "alpha", "mango"]


def test_the_cap_is_applied_after_dedup_not_before() -> None:
    # Eleven elements, the tenth a duplicate of the first -> exactly ten distinct
    # tags, which is the cap. Capping before dedup rejects the whole list (or
    # keeps the first ten and dedups them to nine); either way "tag-9" is lost.
    tags = [f"tag-{index}" for index in range(9)] + ["TAG-0", "tag-9"]
    assert len(tags) == MAX_TAGS + 1
    result = normalize_tags(tags)
    assert len(result) == MAX_TAGS
    assert "tag-9" in result


def test_more_than_max_tags_distinct_is_rejected() -> None:
    with pytest.raises(CustomerValidationError):
        normalize_tags([f"tag-{index}" for index in range(MAX_TAGS + 1)])


def test_a_tag_at_the_length_cap_passes() -> None:
    assert normalize_tags(["a" * MAX_TAG_LENGTH]) == ["a" * MAX_TAG_LENGTH]


def test_a_tag_one_over_the_length_cap_is_rejected() -> None:
    with pytest.raises(CustomerValidationError):
        normalize_tags(["a" * (MAX_TAG_LENGTH + 1)])


@pytest.mark.parametrize("control", ["\x00", "\x0b", "\t", "\n", "\r"])
def test_every_c0_character_is_rejected_in_a_tag(control: str) -> None:
    # \t \n \r are the three _CONTROL_CHARS_EXCEPT_WS permits: these three cases
    # are the only ones that fail if the notes regex was imported for tags.
    with pytest.raises(CustomerValidationError):
        normalize_tags([f"vi{control}p"])


def test_empty_tag_list_is_empty() -> None:
    assert normalize_tags([]) == []


# --- validate_notes ---


def test_notes_at_the_cap_pass() -> None:
    validate_notes("a" * MAX_CUSTOMER_NOTES_LENGTH)


def test_notes_one_over_the_cap_are_rejected() -> None:
    with pytest.raises(CustomerValidationError):
        validate_notes("a" * (MAX_CUSTOMER_NOTES_LENGTH + 1))


@pytest.mark.parametrize("whitespace", ["\n", "\t"])
def test_notes_keep_newlines_and_tabs(whitespace: str) -> None:
    validate_notes(f"מגיעה עם אמא{whitespace}ושתי אחיות")


def test_notes_reject_a_non_whitespace_control_character() -> None:
    with pytest.raises(CustomerValidationError):
        validate_notes("מגיעה\x0bעם אמא")


def test_empty_notes_pass_and_mean_cleared() -> None:
    validate_notes("")


# --- phone_search_term ---


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("0501234567", "972501234567"),
        ("050-123-4567", "972501234567"),
        ("050", "97250"),
        ("972501234567", "972501234567"),
        ("מיכל", None),
        ("", None),
    ],
)
def test_phone_search_term_table(term: str, expected: str | None) -> None:
    assert phone_search_term(term) == expected


# --- house register ---


def test_search_term_bound_mirrors_the_customer_name_bound() -> None:
    from app.booking.validation import MAX_CUSTOMER_NAME_LENGTH

    assert MAX_SEARCH_TERM_LENGTH == MAX_CUSTOMER_NAME_LENGTH


def test_every_error_is_a_domain_validation_error() -> None:
    assert issubclass(CustomerValidationError, DomainValidationError)


@pytest.mark.parametrize(
    "call",
    [
        lambda: normalize_tags(["a" * (MAX_TAG_LENGTH + 1)]),
        lambda: normalize_tags(["vi\np"]),
        lambda: normalize_tags([f"tag-{index}" for index in range(MAX_TAGS + 1)]),
        lambda: validate_notes("a" * (MAX_CUSTOMER_NOTES_LENGTH + 1)),
        lambda: validate_notes("bad\x0bnote"),
    ],
)
def test_messages_follow_the_house_register(call: Callable[[], object]) -> None:
    with pytest.raises(DomainValidationError) as caught:
        call()
    message = str(caught.value)
    assert message.split(":")[0].split()[0] in {"tags", "notes"}
    assert message == message[0].lower() + message[1:]
    assert not message.endswith(".")
