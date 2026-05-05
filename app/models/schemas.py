"""Pydantic models for request/response validation."""

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator
from typing import Optional, List
from datetime import datetime
import re

def validate_strong_password(v: str) -> str:
    if not re.search(r'[A-Z]', v):
        raise ValueError('Password must contain at least one uppercase letter')
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
        raise ValueError('Password must contain at least one symbol (!@#$%^&*(),.?":{}|<>)')
    return v

# ─── Auth Models ───

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return validate_strong_password(v)


class UserRegisterAdmin(UserRegister):
    admin_secret: str = Field(..., description="Secret code to authorize admin registration")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, max_length=100)

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return validate_strong_password(v)


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime
    is_admin: bool = False
    role: str = "user"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ─── URL Models ───

class URLCreate(BaseModel):
    original_url: str = Field(..., min_length=5)
    custom_alias: Optional[str] = Field(None, min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_-]+$")
    expiry_days: Optional[int] = Field(None, ge=1, le=365)
    # Password Protection
    password: Optional[str] = Field(None, min_length=1, max_length=100)
    # Geo-targeting: map of country_code -> redirect_url
    geo_targets: Optional[dict[str, str]] = Field(
        None,
        description="Country-code to URL mapping, e.g. {'US': 'https://us.example.com', 'IN': 'https://in.example.com'}"
    )
    # Tags / Categories
    tags: Optional[List[str]] = Field(default=[], description="List of tags, e.g. ['work', 'personal']")


class PasswordConfig(BaseModel):
    password: Optional[str] = Field(None, min_length=1, max_length=100, description="New password or null to remove")


class GeoConfig(BaseModel):
    geo_targets: Optional[dict[str, str]] = Field(None)


class URLVerifyPassword(BaseModel):
    password: str

class URLResponse(BaseModel):
    id: str
    original_url: str
    short_code: str
    short_url: str
    created_at: datetime
    expiry_date: Optional[datetime] = None
    total_clicks: int = 0
    qr_code_url: Optional[str] = None
    is_password_protected: bool = False
    has_geo_targets: bool = False
    geo_targets: Optional[dict[str, str]] = None
    tags: List[str] = []


class URLListResponse(BaseModel):
    urls: list[URLResponse]
    total: int


# ─── Analytics Models ───

class ClickEvent(BaseModel):
    url_id: str
    ip_address: str
    location: Optional[str] = "Unknown"
    device: Optional[str] = "Unknown"
    browser: Optional[str] = "Unknown"
    timestamp: datetime


class AnalyticsResponse(BaseModel):
    url_id: str
    original_url: str
    short_code: str
    total_clicks: int
    unique_visitors: int
    clicks_by_day: list[dict]
    clicks_by_browser: list[dict]
    clicks_by_device: list[dict]
    clicks_by_location: list[dict]
    recent_clicks: list[dict]
