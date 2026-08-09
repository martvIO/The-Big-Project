"""`MarkReadRequest`'s three refusals, and the one thing that is NOT a refusal.

The whole write side of this feature is one verb taking a list of ids, so the
body is where the only client-supplied value in F35 arrives. Everything the
server is willing to accept is here.
"""

import uuid

import pytest
from pydantic import ValidationError

from app.floor.schemas import MAX_MARK_READ_IDS, MarkReadRequest


def test_a_body_of_twenty_ids_is_accepted() -> None:
    """20 is the list read's cap, so «mark all» sends at most the rendered page
    and the two numbers are the same number by construction."""
    ids = [uuid.uuid4() for _ in range(MAX_MARK_READ_IDS)]
    assert MarkReadRequest(ids=ids).ids == ids


def test_a_twenty_first_id_is_refused() -> None:
    """The cap is enforced SERVER-side and not merely respected by the console:
    the page is at most 20 rows, so a longer list is either a bug or somebody
    replaying ids by hand."""
    with pytest.raises(ValidationError):
        MarkReadRequest(ids=[uuid.uuid4() for _ in range(MAX_MARK_READ_IDS + 1)])


def test_an_empty_list_is_accepted_and_is_a_no_op() -> None:
    """NOT a 422. «She tapped a row that was already read» and «nothing on the
    page was unread» both arrive here, and both are ordinary — the verb answers
    her current count and writes nothing."""
    assert MarkReadRequest(ids=[]).ids == []


def test_an_unknown_key_is_refused() -> None:
    """`ForbidExtraModel`. `staff_user_id` is the key a client would reach for,
    and it is exactly the one that must never be body-supplied: the actor comes
    from the session cookie, so a body carrying one is a 400 rather than a
    silently ignored field."""
    with pytest.raises(ValidationError):
        MarkReadRequest(ids=[], staff_user_id=str(uuid.uuid4()))  # type: ignore[call-arg]
