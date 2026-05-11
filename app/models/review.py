"""
PropertyKING — Review Models
Property review/rating models.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ReviewCreate(BaseModel):
    property_id: str
    rating: float = Field(..., ge=1, le=5)
    comment: str = Field(..., min_length=10, max_length=1000)


class ReviewResponse(BaseModel):
    id: str
    property_id: str
    user_id: str
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    rating: float
    comment: str
    is_approved: bool = True
    created_at: Optional[datetime] = None
