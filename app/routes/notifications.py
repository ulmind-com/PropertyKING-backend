"""
PropertyKING — Notification Routes
"""

from fastapi import APIRouter, Depends, Query
from bson import ObjectId
import math

from app.database import get_database
from app.middleware.auth import get_current_user
from app.models.notification import NotificationResponse
from app.utils.helpers import now_utc

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
async def get_notifications(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get user's notifications."""
    db = get_database()
    query = {"user_id": current_user["_id"]}
    total = await db.notifications.count_documents(query)
    unread = await db.notifications.count_documents({**query, "is_read": False})
    skip = (page - 1) * limit

    cursor = db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit)
    notifications = []
    async for n in cursor:
        notifications.append(NotificationResponse(
            id=str(n["_id"]), user_id=n.get("user_id", ""), title=n.get("title", ""),
            body=n.get("body", ""), type=n.get("type", "system"),
            data=n.get("data"), is_read=n.get("is_read", False), created_at=n.get("created_at")))

    return {"notifications": notifications, "total": total, "unread_count": unread,
            "page": page, "limit": limit, "total_pages": math.ceil(total / limit) if limit > 0 else 0}


@router.put("/{notification_id}/read")
async def mark_as_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    """Mark notification as read."""
    db = get_database()
    await db.notifications.update_one(
        {"_id": ObjectId(notification_id), "user_id": current_user["_id"]},
        {"$set": {"is_read": True}})
    return {"message": "Marked as read", "success": True}


@router.put("/read-all")
async def mark_all_read(current_user: dict = Depends(get_current_user)):
    """Mark all notifications as read."""
    db = get_database()
    await db.notifications.update_many(
        {"user_id": current_user["_id"], "is_read": False},
        {"$set": {"is_read": True}})
    return {"message": "All marked as read", "success": True}
