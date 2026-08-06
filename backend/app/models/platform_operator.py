from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class PlatformOperator(Base, StandardColumns):
    """A platform operator — the console's only identity, seeded by the CLI.

    Deliberately NOT tenant-scoped (spec D2/D7): no `tenant_id`, no RLS. An
    operator acts across every boutique, which is exactly why `platform_audit_log`
    has `target_tenant_id` and not `tenant_id`, and the same argument lands here.

    Soft delete IS deactivation. `get_current_operator` re-reads this row on every
    request, so clearing `deleted_at`'s NULL bites on the next one — `RoleGate`'s
    property, one table over.
    """

    __tablename__ = "platform_operators"

    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
