"""The floor's wire shapes.

Plain `BaseModel`s used as return-type ANNOTATIONS, never `response_model=` (the
shipped house form). No `ForbidExtraModel`: neither POST takes a body, so there
are no extras to forbid.

**The read is an ENVELOPE, not a bare array.** F51's `/manage/staff` answers a
bare list and that was right for a list — this one is the FLOOR's, and F36 adds
rooms and occupancy to it while F58 adds the waitlist. An envelope makes those
additive; a bare array makes the first of them a breaking shape change on a
screen that polls every five seconds.

**A card is a name, a role and a status, and deliberately nothing else** — no
avatar, no phone, no email. `email` in particular is the one a later reader will
reach for as a stable key: `id` is the key, and the address of every member of
staff is not something a seamstress needs in order to see who is on a break.
"""

import datetime
import uuid

from pydantic import BaseModel

from app.floor.service import card_status
from app.models.constants import StaffCardStatus
from app.models.staff_user import StaffUser


class StaffCard(BaseModel):
    id: uuid.UUID
    display_name: str
    role: str
    status: StaffCardStatus
    # Present so the card can render «מאז 11:20» — the mitigation for a break
    # having no upper bound (D7). NULL whenever `status` is `available`, and the
    # console must not infer one from the other in the opposite direction: F36
    # adds `occupied`, which also carries no break timestamp.
    break_started_at: datetime.datetime | None

    @classmethod
    def from_row(cls, row: StaffUser) -> "StaffCard":
        return cls(
            id=row.id,
            display_name=row.display_name,
            role=row.role,
            status=card_status(row),
            break_started_at=row.break_started_at,
        )


class FloorResponse(BaseModel):
    staff: list[StaffCard]

    @classmethod
    def from_rows(cls, rows: list[StaffUser]) -> "FloorResponse":
        return cls(staff=[StaffCard.from_row(row) for row in rows])
