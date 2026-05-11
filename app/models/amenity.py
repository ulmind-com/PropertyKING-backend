"""
PropertyKING — Amenity Models
Admin-controlled amenities with categories.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class AmenityCategory(str, Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    COMMUNITY = "community"
    SECURITY = "security"
    UTILITIES = "utilities"
    ACCESSIBILITY = "accessibility"


class AmenityCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    icon: Optional[str] = "✅"
    category: AmenityCategory = AmenityCategory.INDOOR
    is_active: bool = True
    order: int = 0


class AmenityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=50)
    icon: Optional[str] = None
    category: Optional[AmenityCategory] = None
    is_active: Optional[bool] = None
    order: Optional[int] = None


class AmenityResponse(BaseModel):
    id: str
    name: str
    slug: str
    icon: str = "✅"
    category: str
    is_active: bool = True
    order: int = 0
    created_at: Optional[datetime] = None
