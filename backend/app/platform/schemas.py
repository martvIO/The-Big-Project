from pydantic import BaseModel


class OperatorResponse(BaseModel):
    """What `/platform/auth/me` and the login answer. `id` is deliberately absent:
    the console has no per-operator screen, no operator management UI (spec D2 —
    creation and deactivation are CLI-only), and nothing on the wire needs a
    handle to an operator. A field nobody reads is a field somebody eventually
    keys something on."""

    email: str
    display_name: str
