"""
PropertyKING — Inquiry Models
Property inquiry/contact models.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class InquiryType(str, Enum):
    VIEWING = "viewing"
    QUESTION = "question"
    OFFER = "offer"
    GENERAL = "general"


class ContactPreference(str, Enum):
    CALL = "call"
    WHATSAPP = "whatsapp"
    IN_PERSON = "in_person"
    VIDEO_CALL = "video_call"


class InquiryStatus(str, Enum):
    PENDING = "pending"
    RESPONDED = "responded"
    CLOSED = "closed"


class InquiryCreate(BaseModel):
    property_id: str
    message: str = Field(..., min_length=10, max_length=1000)
    inquiry_type: InquiryType = InquiryType.GENERAL
    contact_phone: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    contact_preference: Optional[str] = None


class InquiryRespond(BaseModel):
    response: str = Field(..., min_length=5, max_length=1000)


class InquiryResponse(BaseModel):
    id: str
    property_id: str
    property_title: Optional[str] = None
    property_image: Optional[str] = None
    user_id: str
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    user_email: Optional[str] = None
    lister_id: str
    lister_name: Optional[str] = None
    message: str
    inquiry_type: str
    status: str
    response: Optional[str] = None
    responded_at: Optional[datetime] = None
    contact_phone: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    contact_preference: Optional[str] = None
    created_at: Optional[datetime] = None
