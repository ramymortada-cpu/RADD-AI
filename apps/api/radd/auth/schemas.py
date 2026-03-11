import uuid

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    workspace_slug: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    email: str
    name: str
    role: str

    model_config = {"from_attributes": True}
