"""
PropertyKING — User Routes
Profile management, FCM token update, public profiles.
"""

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from bson import ObjectId

from app.database import get_database
from app.middleware.auth import get_current_user
from app.models.user import UserProfileUpdate, FCMTokenUpdate, UserResponse, UserPublicProfile, MessageResponse
from app.services.image_upload import upload_image
from app.utils.helpers import now_utc

router = APIRouter(prefix="/users", tags=["Users"])


def build_user_resp(user: dict, favorites_count=0, listings_count=0) -> UserResponse:
    uid = user["_id"] if isinstance(user["_id"], str) else str(user["_id"])
    return UserResponse(
        id=uid, full_name=user.get("full_name", ""), email=user.get("email", ""),
        phone=user.get("phone"), avatar=user.get("avatar"), role=user.get("role", "user"),
        lister_type=user.get("lister_type"), license_number=user.get("license_number"),
        company_name=user.get("company_name"), bio=user.get("bio"),
        verified=user.get("verified", False), location=user.get("location"),
        favorites_count=favorites_count, listings_count=listings_count,
        is_active=user.get("is_active", True), created_at=user.get("created_at"))


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    db = get_database()
    fav_count = await db.favorites.count_documents({"user_id": current_user["_id"]})
    list_count = await db.properties.count_documents({"listed_by": current_user["_id"]})
    return build_user_resp(current_user, fav_count, list_count)


@router.put("/me", response_model=UserResponse)
async def update_my_profile(data: UserProfileUpdate, current_user: dict = Depends(get_current_user)):
    db = get_database()
    update_data = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    update_data["updated_at"] = now_utc()

    await db.users.update_one({"_id": ObjectId(current_user["_id"])}, {"$set": update_data})
    updated = await db.users.find_one({"_id": ObjectId(current_user["_id"])})
    updated["_id"] = str(updated["_id"])
    fav_count = await db.favorites.count_documents({"user_id": current_user["_id"]})
    list_count = await db.properties.count_documents({"listed_by": current_user["_id"]})
    return build_user_resp(updated, fav_count, list_count)


@router.put("/me/avatar", response_model=UserResponse)
async def update_avatar(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    db = get_database()
    result = await upload_image(file, folder="propertyking/avatars")
    await db.users.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": {"avatar": result["url"], "updated_at": now_utc()}})
    updated = await db.users.find_one({"_id": ObjectId(current_user["_id"])})
    updated["_id"] = str(updated["_id"])
    return build_user_resp(updated)


@router.put("/me/fcm-token", response_model=MessageResponse)
async def update_fcm_token(data: FCMTokenUpdate, current_user: dict = Depends(get_current_user)):
    db = get_database()
    await db.users.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": {"fcm_token": data.fcm_token, "updated_at": now_utc()}})
    return MessageResponse(message="FCM token updated")


@router.get("/{user_id}/public", response_model=UserPublicProfile)
async def get_public_profile(user_id: str):
    db = get_database()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    listings_count = await db.properties.count_documents({"listed_by": user_id, "status": "active"})
    return UserPublicProfile(
        id=str(user["_id"]), full_name=user.get("full_name", ""), avatar=user.get("avatar"),
        role=user.get("role", "user"), lister_type=user.get("lister_type"),
        license_number=user.get("license_number"), company_name=user.get("company_name"),
        bio=user.get("bio"), verified=user.get("verified", False),
        listings_count=listings_count, created_at=user.get("created_at"))
