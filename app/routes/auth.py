"""Authentication routes: register, login, password reset."""

import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from app.models.schemas import (
    UserRegister, UserLogin, TokenResponse, UserResponse, UserRegisterAdmin,
    ForgotPassword, ResetPassword
)
from app.utils.security import hash_password, verify_password, create_access_token, get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    """Register a new user."""
    db = get_db()

    # Check if email already exists
    existing = await db.users.find_one({"email": user_data.email.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Create user
    user_doc = {
        "name": user_data.name.strip(),
        "email": user_data.email.lower(),
        "password": hash_password(user_data.password),
        "created_at": datetime.now(timezone.utc),
        "is_admin": False,
        "role": "user",
    }

    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    token = create_access_token(data={"sub": user_id})

    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            name=user_doc["name"],
            email=user_doc["email"],
            created_at=user_doc["created_at"],
            is_admin=user_doc.get("is_admin", False),
            role=user_doc.get("role", "user"),
        )
    )

@router.post("/register-admin", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_admin(user_data: UserRegisterAdmin):
    """Register a new admin user."""
    db = get_db()
    
    # Check secret code
    expected_secret = os.getenv("ADMIN_SECRET_KEY", "secret_admin_123")
    if user_data.admin_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin registration secret code"
        )

    # Check if email already exists
    existing = await db.users.find_one({"email": user_data.email.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Create admin user
    user_doc = {
        "name": user_data.name.strip(),
        "email": user_data.email.lower(),
        "password": hash_password(user_data.password),
        "created_at": datetime.now(timezone.utc),
        "is_admin": True,
        "role": "admin",
    }

    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    token = create_access_token(data={"sub": user_id})

    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            name=user_doc["name"],
            email=user_doc["email"],
            created_at=user_doc["created_at"],
            is_admin=True,
            role="admin",
        )
    )



@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    """Login with email and password."""
    db = get_db()

    user = await db.users.find_one({"email": user_data.email.lower()})
    if not user or not verify_password(user_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    user_id = str(user["_id"])
    token = create_access_token(data={"sub": user_id})

    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            name=user["name"],
            email=user["email"],
            created_at=user["created_at"],
            is_admin=user.get("is_admin", False),
            role=user.get("role", "admin" if user.get("is_admin") else "user"),
        )
    )

@router.get("/profile", response_model=UserResponse)
async def get_profile(user=Depends(get_current_user)):
    """Get current user info."""
    return UserResponse(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        created_at=user["created_at"],
        is_admin=user.get("is_admin", False),
        role=user.get("role", "admin" if user.get("is_admin") else "user")
    )

@router.post("/forgot-password")
async def forgot_password(data: ForgotPassword):
    """Generate a password reset token (returns token in response for local demo)."""
    db = get_db()
    user = await db.users.find_one({"email": data.email.lower()})
    
    if not user:
        # Prevent email enumeration by returning success anyway
        return {"message": "If that email is registered, a password reset link has been sent."}
        
    token = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"reset_token": token, "reset_token_expiry": expiry}}
    )
    
    # In a real app we would email this link. For our local 'big project', we return it.
    reset_link = f"/reset-password?token={token}"
    return {
        "message": "If that email is registered, a password reset link has been sent.",
        "demo_link": reset_link
    }

@router.post("/reset-password")
async def reset_password(data: ResetPassword):
    """Reset password using a token."""
    db = get_db()
    
    user = await db.users.find_one({
        "reset_token": data.token,
        "reset_token_expiry": {"$gt": datetime.now(timezone.utc)}
    })
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
        
    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"password": hash_password(data.new_password)},
            "$unset": {"reset_token": "", "reset_token_expiry": ""}
        }
    )
    
    return {"message": "Password successfully reset! You can now log in."}
