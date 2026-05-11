"""
PropertyKING — User Models
Pydantic models for user registration, authentication, and profile management.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    USER = "user"
    LISTER = "lister"
    ADMIN = "admin"


class ListerType(str, Enum):
    OWNER = "owner"
    AGENT = "agent"
    BROKER = "broker"
    DEVELOPER = "developer"


class UserLocation(BaseModel):
    type: str = "Point"
    coordinates: List[float] = [0.0, 0.0]  # [lng, lat]
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    address: Optional[str] = None


# ─── Auth Models ───

class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, pattern=r"^\+?1?\d{10,15}$")
    password: str = Field(..., min_length=6, max_length=128)
    role: UserRole = UserRole.USER
    lister_type: Optional[ListerType] = None
    license_number: Optional[str] = None
    company_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    token: str  # Google ID token


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ─── Profile Models ───

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, pattern=r"^\+?1?\d{10,15}$")
    bio: Optional[str] = Field(None, max_length=500)
    lister_type: Optional[ListerType] = None
    license_number: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[UserLocation] = None


class FCMTokenUpdate(BaseModel):
    fcm_token: str


# ─── Response Models ───

class UserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    avatar: Optional[str] = None
    role: str
    lister_type: Optional[str] = None
    license_number: Optional[str] = None
    company_name: Optional[str] = None
    bio: Optional[str] = None
    verified: bool = False
    location: Optional[UserLocation] = None
    favorites_count: int = 0
    listings_count: int = 0
    is_active: bool = True
    created_at: Optional[datetime] = None


class UserPublicProfile(BaseModel):
    id: str
    full_name: str
    avatar: Optional[str] = None
    role: str
    lister_type: Optional[str] = None
    license_number: Optional[str] = None
    company_name: Optional[str] = None
    bio: Optional[str] = None
    verified: bool = False
    listings_count: int = 0
    created_at: Optional[datetime] = None


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
    success: bool = True
