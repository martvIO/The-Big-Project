from pydantic import BaseModel, EmailStr, Field

# argon2 cost scales with input size; cap it so a giant password can't be a CPU DoS.
MAX_PASSWORD_LENGTH = 4096


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class StaffResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
