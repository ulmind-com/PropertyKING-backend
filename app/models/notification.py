"""
PropertyKING — Notification Models
Push notification models.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum


class NotificationType(str, Enum):
    PROPERTY_APPROVED = "property_approved"
    PROPERTY_REJECTED = "property_rejected"
    NEW_INQUIRY = "new_inquiry"
    INQUIRY_RESPONSE = "inquiry_response"
    PRICE_DROP = "price_drop"
    NEW_LISTING = "new_listing"
    FAVORITE_UPDATE = "favorite_update"
    SYSTEM = "system"


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    body: str
    type: str
    data: Optional[Dict] = None
    is_read: bool = False
    created_at: Optional[datetime] = None


class BroadcastNotification(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=500)
    type: NotificationType = NotificationType.SYSTEM
    image_url: Optional[str] = None
    data: Optional[Dict] = None
    target_roles: Optional[List[str]] = None  # Filter by role
    target_states: Optional[List[str]] = None  # Filter by US state
