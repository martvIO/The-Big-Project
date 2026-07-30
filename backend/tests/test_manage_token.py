"""The manage token's three properties: enough entropy, one-way storage, and a
comparison that cannot be widened into a leak.

Security-checklist row 21 and spec D1/D2. No I/O.
"""

from app.booking.comms_templates import MANAGE_LINK_SLUG_BUDGET_CHARS
from app.booking.tokens import manage_token_hash, manage_token_matches, mint_manage_token

# generate_session_token() is token_urlsafe(32) -> 43 characters. The SMS segment
# arithmetic is written against exactly this, so a change here is a change there.
EXPECTED_TOKEN_LENGTH = 43


def test_a_minted_token_is_43_urlsafe_characters() -> None:
    token = mint_manage_token()
    assert len(token) == EXPECTED_TOKEN_LENGTH
    # The frontend route matches [A-Za-z0-9_-]+, so a token carrying anything
    # else would produce a link that the router refuses to read as a token.
    assert all(char.isalnum() or char in "-_" for char in token), token


def test_tokens_are_not_reused() -> None:
    assert len({mint_manage_token() for _ in range(50)}) == 50


def test_the_hash_is_one_way_and_stable() -> None:
    token = mint_manage_token()
    digest = manage_token_hash(token)
    assert digest != token
    assert token not in digest
    assert len(digest) == 64  # sha256 hex
    assert manage_token_hash(token) == digest


def test_the_right_token_matches_its_stored_hash() -> None:
    token = mint_manage_token()
    assert manage_token_matches(token, manage_token_hash(token))


def test_a_one_character_difference_does_not_match() -> None:
    token = mint_manage_token()
    stored = manage_token_hash(token)
    tampered = ("A" if token[0] != "A" else "B") + token[1:]
    assert not manage_token_matches(tampered, stored)


def test_a_truncated_token_does_not_match() -> None:
    """The lookup predicate is an equality on the hash today. If it is ever
    widened to a prefix or LIKE match, this is the assertion that fails."""
    token = mint_manage_token()
    assert not manage_token_matches(token[:-1], manage_token_hash(token))


def test_a_pre_f16_booking_with_no_hash_never_matches() -> None:
    """manage_token_hash is NULL on every row the backfill has not reached, and
    `None` must be a miss rather than a crash on an anonymous endpoint."""
    assert not manage_token_matches(mint_manage_token(), None)
    assert not manage_token_matches("", None)


def test_an_empty_token_never_matches_a_real_hash() -> None:
    assert not manage_token_matches("", manage_token_hash(mint_manage_token()))


def test_the_documented_link_budget_still_assumes_this_token_length() -> None:
    """A tripwire, not a tautology: the two constants are only correct together,
    and they live in different modules."""
    assert MANAGE_LINK_SLUG_BUDGET_CHARS == 30
    assert len(mint_manage_token()) == EXPECTED_TOKEN_LENGTH
