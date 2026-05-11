"""
PropertyKING — Property Type Models
Admin-controlled property categories.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PropertyTypeCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    icon: Optional[str] = "🏠"
    icon_url: Optional[str] = None
    description: Optional[str] = Field(None, max_length=200)
    is_active: bool = True
    order: int = 0


class PropertyTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=50)
    icon: Optional[str] = None
    icon_url: Optional[str] = None
    description: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None
    order: Optional[int] = None


class PropertyTypeResponse(BaseModel):
    id: str
    name: str
    slug: str
    icon: str = "🏠"
    icon_url: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    order: int = 0
    properties_count: int = 0
    created_at: Optional[datetime] = None
