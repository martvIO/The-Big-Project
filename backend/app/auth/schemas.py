from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class StaffResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
