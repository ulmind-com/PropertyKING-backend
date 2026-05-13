"""
PropertyKING — Property Models
Pydantic models for property listings with comprehensive US market fields.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ListingType(str, Enum):
    SALE = "sale"
    RENT = "rent"
    LEASE = "lease"


class PropertyStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    SOLD = "sold"
    RENTED = "rented"
    EXPIRED = "expired"
    DRAFT = "draft"


class PriceUnit(str, Enum):
    TOTAL = "total"
    PER_MONTH = "per_month"
    PER_NIGHT = "per_night"


class ParkingType(str, Enum):
    ATTACHED_GARAGE = "attached_garage"
    DETACHED_GARAGE = "detached_garage"
    CARPORT = "carport"
    STREET = "street"
    DRIVEWAY = "driveway"
    NONE = "none"


class BasementType(str, Enum):
    FINISHED = "finished"
    UNFINISHED = "unfinished"
    PARTIAL = "partial"
    NONE = "none"


# ─── Sub-Models ───

class PropertyImage(BaseModel):
    url: str
    caption: Optional[str] = None
    is_primary: bool = False
    order: int = 0


class GeoPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float] = [0.0, 0.0]  # [lng, lat]


class PropertyLocation(BaseModel):
    address: str
    unit: Optional[str] = None
    city: str
    state: str = Field(..., max_length=2, description="US state abbreviation e.g. 'IL'")
    zip_code: str = Field(..., pattern=r"^\d{5}(-\d{4})?$")
    county: Optional[str] = None
    neighborhood: Optional[str] = None
    coordinates: GeoPoint = GeoPoint()


class PropertyDetails(BaseModel):
    bedrooms: int = Field(0, ge=0, le=50)
    bathrooms: float = Field(0, ge=0, le=50)
    half_baths: int = Field(0, ge=0, le=20)
    total_sqft: Optional[int] = Field(None, ge=0)
    lot_size_sqft: Optional[int] = Field(None, ge=0)
    lot_size_acres: Optional[float] = Field(None, ge=0)
    year_built: Optional[int] = Field(None, ge=1800, le=2030)
    stories: Optional[int] = Field(None, ge=1, le=200)
    garage_spaces: int = Field(0, ge=0, le=20)
    parking_type: Optional[ParkingType] = None
    basement: Optional[BasementType] = None
    hoa_fee: Optional[float] = Field(None, ge=0)
    hoa_frequency: Optional[str] = "monthly"  # monthly, quarterly, annually
    property_tax_annual: Optional[float] = Field(None, ge=0)
    zoning: Optional[str] = None
    construction_material: Optional[str] = None
    roof_type: Optional[str] = None
    heating: Optional[str] = None
    cooling: Optional[str] = None
    flooring: List[str] = []
    appliances_included: List[str] = []
    mls_number: Optional[str] = None
    virtual_tour_url: Optional[str] = None
    open_house_dates: List[str] = []


class AdminReview(BaseModel):
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None


# ─── Request Models ───

class PropertyCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20, max_length=5000)
    property_type_id: str
    listing_type: ListingType
    price: float = Field(..., gt=0)
    price_unit: PriceUnit = PriceUnit.TOTAL
    details: PropertyDetails = PropertyDetails()
    amenities: List[str] = []  # Amenity IDs
    location: PropertyLocation
    images: List[PropertyImage] = []
    video_url: Optional[str] = None
    floor_plan_url: Optional[str] = None
    floor_plan_urls: Optional[List[str]] = []
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


class PropertyUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=20, max_length=5000)
    property_type_id: Optional[str] = None
    listing_type: Optional[ListingType] = None
    price: Optional[float] = Field(None, gt=0)
    price_unit: Optional[PriceUnit] = None
    status: Optional[PropertyStatus] = None
    details: Optional[PropertyDetails] = None
    amenities: Optional[List[str]] = None
    location: Optional[PropertyLocation] = None
    images: Optional[List[PropertyImage]] = None
    video_url: Optional[str] = None
    floor_plan_url: Optional[str] = None
    floor_plan_urls: Optional[List[str]] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


class PropertyApprove(BaseModel):
    pass  # No body needed


class PropertyReject(BaseModel):
    reason: str = Field(..., min_length=10, max_length=500)


# ─── Query Models ───

class PropertyQuery(BaseModel):
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    search: Optional[str] = None
    property_type_id: Optional[str] = None
    listing_type: Optional[ListingType] = None
    status: Optional[PropertyStatus] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    bedrooms_min: Optional[int] = None
    bedrooms_max: Optional[int] = None
    bathrooms_min: Optional[float] = None
    min_sqft: Optional[int] = None
    max_sqft: Optional[int] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    amenities: Optional[List[str]] = None
    year_built_min: Optional[int] = None
    year_built_max: Optional[int] = None
    has_garage: Optional[bool] = None
    has_basement: Optional[bool] = None
    sort_by: Optional[str] = "created_at"  # price, created_at, sqft
    sort_order: Optional[str] = "desc"  # asc, desc
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_miles: Optional[float] = Field(None, ge=0.1, le=100)


# ─── Response Models ───

class PropertyResponse(BaseModel):
    id: str
    title: str
    slug: str
    description: str
    property_type_id: str
    property_type_name: Optional[str] = None
    listing_type: str
    status: str
    price: float
    price_unit: str
    currency: str = "USD"
    details: PropertyDetails
    amenities: List[str] = []
    amenity_names: List[str] = []
    location: PropertyLocation
    images: List[PropertyImage] = []
    video_url: Optional[str] = None
    floor_plan_url: Optional[str] = None
    floor_plan_urls: Optional[List[str]] = []
    listed_by: str
    lister_name: Optional[str] = None
    lister_avatar: Optional[str] = None
    lister_type: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    admin_review: Optional[AdminReview] = None
    views_count: int = 0
    favorites_count: int = 0
    inquiries_count: int = 0
    is_favorited: bool = False
    listed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PropertyListResponse(BaseModel):
    properties: List[PropertyResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    total_views: Optional[int] = None
    total_inquiries: Optional[int] = None
