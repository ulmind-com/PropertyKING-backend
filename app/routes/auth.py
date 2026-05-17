"""
PropertyKING — Auth Routes
Registration, login, password reset, Google OAuth, token refresh.
"""

from fastapi import APIRouter, HTTPException, status
from bson import ObjectId

from app.database import get_database
from app.models.user import (
    UserRegister, UserLogin, GoogleAuthRequest,
    ForgotPasswordRequest, ResetPasswordRequest, RefreshTokenRequest,
    OTPRequest, OTPVerify,
    AuthResponse, UserResponse, MessageResponse
)
from app.middleware.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, create_reset_token,
    decode_token
)
from app.services.email_service import send_welcome_email, send_password_reset_email, send_otp_email
from app.utils.helpers import now_utc, serialize_doc

import httpx
import random
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["Authentication"])


def build_user_response(user: dict) -> UserResponse:
    """Build UserResponse from DB document."""
    return UserResponse(
        id=str(user["_id"]) if "_id" in user else user.get("id", ""),
        full_name=user.get("full_name", ""),
        email=user.get("email", ""),
        phone=user.get("phone"),
        avatar=user.get("avatar"),
        role=user.get("role", "user"),
        lister_type=user.get("lister_type"),
        license_number=user.get("license_number"),
        company_name=user.get("company_name"),
        bio=user.get("bio"),
        verified=user.get("verified", False),
        location=user.get("location"),
        is_active=user.get("is_active", True),
        created_at=user.get("created_at")
    )


@router.post("/request-otp", response_model=MessageResponse)
async def request_otp(data: OTPRequest):
    """Request an OTP for registration or password reset."""
    db = get_database()
    
    # Check if email exists for registration
    existing = await db.users.find_one({"email": data.email.lower()})
    if data.purpose == "registration" and existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    if data.purpose == "reset" and not existing:
        # Always return success to prevent email enumeration, but we won't send the email
        return MessageResponse(message="If the email exists, an OTP has been sent.")

    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    
    # Store OTP in DB
    await db.otps.delete_many({"email": data.email.lower(), "purpose": data.purpose})
    await db.otps.insert_one({
        "email": data.email.lower(),
        "otp": otp,
        "purpose": data.purpose,
        "verified": False,
        "expires_at": now_utc() + timedelta(minutes=10)
    })
    
    # Send email
    await send_otp_email(data.email.lower(), otp, data.purpose)
    
    return MessageResponse(message="OTP sent successfully")


@router.post("/verify-otp", response_model=MessageResponse)
async def verify_otp(data: OTPVerify):
    """Verify an OTP."""
    db = get_database()
    
    otp_doc = await db.otps.find_one({
        "email": data.email.lower(),
        "otp": data.otp,
        "purpose": data.purpose
    })
    
    if not otp_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP"
        )
        
    expires_at = otp_doc["expires_at"]
    if expires_at.tzinfo is None:
        from datetime import timezone
        expires_at = expires_at.replace(tzinfo=timezone.utc)
        
    if now_utc() > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired"
        )
        
    # Mark as verified
    await db.otps.update_one(
        {"_id": otp_doc["_id"]},
        {"$set": {"verified": True}}
    )
    
    return MessageResponse(message="OTP verified successfully")


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister):
    """Register a new user."""
    db = get_database()

    # Check if email already exists
    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )


    # Check if OTP was verified
    otp_doc = await db.otps.find_one({
        "email": data.email.lower(),
        "purpose": "registration",
        "verified": True
    })
    
    if not otp_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not verified. Please request and verify OTP first."
        )

    # Create user document
    user_doc = {
        "full_name": data.full_name,
        "email": data.email.lower(),
        "phone": data.phone,
        "password_hash": hash_password(data.password),
        "avatar": None,
        "role": "user",
        "lister_type": None,
        "license_number": None,
        "company_name": None,
        "bio": None,
        "verified": False,
        "fcm_token": None,
        "location": None,
        "favorites": [],
        "created_at": now_utc(),
        "updated_at": now_utc(),
        "is_active": True
    }

    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    # Clean up verified OTP
    await db.otps.delete_one({"_id": otp_doc["_id"]})

    # Generate tokens
    user_id = str(result.inserted_id)
    access_token = create_access_token(user_id, "user")
    refresh_token = create_refresh_token(user_id)

    # Send welcome email (non-blocking)
    try:
        await send_welcome_email(data.email, data.full_name)
    except Exception:
        pass

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=build_user_response(user_doc)
    )


@router.post("/login", response_model=AuthResponse)
async def login(data: UserLogin):
    """Login with email and password."""
    db = get_database()

    user = await db.users.find_one({"email": data.email.lower()})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated"
        )

    if not verify_password(data.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Generate tokens
    user_id = str(user["_id"])
    access_token = create_access_token(user_id, user.get("role", "user"))
    refresh_token = create_refresh_token(user_id)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=build_user_response(user)
    )


@router.post("/google", response_model=AuthResponse)
async def google_auth(data: GoogleAuthRequest):
    """Authenticate via Google OAuth token."""
    # Verify Google token
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={data.token}"
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google token"
                )
            google_data = response.json()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to verify Google token"
        )

    email = google_data.get("email", "").lower()
    name = google_data.get("name", "")
    avatar = google_data.get("picture", "")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not found in Google account"
        )

    db = get_database()
    user = await db.users.find_one({"email": email})

    if user:
        # Existing user — login
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account has been deactivated"
            )
        # Update avatar if not set
        if not user.get("avatar") and avatar:
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"avatar": avatar, "updated_at": now_utc()}}
            )
            user["avatar"] = avatar
    else:
        # New user — register
        user_doc = {
            "full_name": name,
            "email": email,
            "phone": None,
            "password_hash": "",  # No password for Google auth
            "avatar": avatar,
            "role": "user",
            "lister_type": None,
            "license_number": None,
            "company_name": None,
            "bio": None,
            "verified": True,  # Google-verified email
            "fcm_token": None,
            "location": None,
            "favorites": [],
            "created_at": now_utc(),
            "updated_at": now_utc(),
            "is_active": True
        }
        result = await db.users.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        user = user_doc

        try:
            await send_welcome_email(email, name)
        except Exception:
            pass

    user_id = str(user["_id"])
    access_token = create_access_token(user_id, user.get("role", "user"))
    refresh_token = create_refresh_token(user_id)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=build_user_response(user)
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(data: ResetPasswordRequest):
    """Reset password using verified OTP."""
    db = get_database()
    
    # Check if OTP was verified
    otp_doc = await db.otps.find_one({
        "email": data.email.lower(),
        "otp": data.otp,
        "purpose": "reset",
        "verified": True
    })
    
    if not otp_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or unverified OTP."
        )

    result = await db.users.update_one(
        {"email": data.email.lower()},
        {"$set": {
            "password_hash": hash_password(data.new_password),
            "updated_at": now_utc()
        }}
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    # Clean up OTP
    await db.otps.delete_one({"_id": otp_doc["_id"]})

    return MessageResponse(message="Password reset successfully")


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(data: RefreshTokenRequest):
    """Refresh access token using refresh token."""
    payload = decode_token(data.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token"
        )

    user_id = payload.get("sub")
    db = get_database()
    user = await db.users.find_one({"_id": ObjectId(user_id)})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated"
        )

    new_access_token = create_access_token(user_id, user.get("role", "user"))
    new_refresh_token = create_refresh_token(user_id)

    return AuthResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user=build_user_response(user)
    )
