"""
PropertyKING — Distressed Property Sync Models
Pydantic models for the external data sync (Zillow / ATTOM / etc), claims,
and the admin-approved edit request workflow.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


class DistressType(str, Enum):
    PRE_FORECLOSURE = "pre_foreclosure"
    FORECLOSURE = "foreclosure"
    AUCTION = "auction"
    BANK_OWNED = "bank_owned"        # REO
    SHORT_SALE = "short_sale"
    TAX_LIEN = "tax_lien"
    FIXER_UPPER = "fixer_upper"


DISTRESS_LABELS = {
    DistressType.PRE_FORECLOSURE: "Pre-Foreclosure",
    DistressType.FORECLOSURE: "Foreclosure",
    DistressType.AUCTION: "Auction",
    DistressType.BANK_OWNED: "Bank Owned (REO)",
    DistressType.SHORT_SALE: "Short Sale",
    DistressType.TAX_LIEN: "Tax Lien",
    DistressType.FIXER_UPPER: "Fixer Upper",
}


class SyncRunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class SyncTrigger(str, Enum):
    SCHEDULE = "schedule"
    MANUAL = "manual"


class ClaimStatus(str, Enum):
    UNCLAIMED = "unclaimed"
    PENDING = "pending"
    CLAIMED = "claimed"
    REJECTED = "rejected"


class EditRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ─── Property sub-documents (embedded in `properties`) ───

class PropertySource(BaseModel):
    """Where an imported property came from."""
    provider: str                                    # "zillow", "attom", "mock"
    external_id: str                                 # zpid / attom id
    url: Optional[str] = None
    content_hash: Optional[str] = None               # to skip no-op updates
    first_imported_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None


class PropertyDistress(BaseModel):
    """Distress signals for a property."""
    is_distressed: bool = True
    type: DistressType
    auction_date: Optional[datetime] = None
    opening_bid: Optional[float] = None
    estimated_value: Optional[float] = None
    estimated_equity: Optional[float] = None
    unpaid_balance: Optional[float] = None
    default_amount: Optional[float] = None
    lender: Optional[str] = None
    case_number: Optional[str] = None
    filed_date: Optional[datetime] = None
    days_on_market: Optional[int] = None
    price_reduced: bool = False


class PropertyClaim(BaseModel):
    """Claim state embedded on the property document."""
    status: ClaimStatus = ClaimStatus.UNCLAIMED
    claimed_by: Optional[str] = None
    claimed_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


# ─── Sync settings (single document in `sync_settings`) ───

LISTING_STATUS_OPTIONS = ["ForSale", "ForRent", "RecentlySold"]


class SyncSettings(BaseModel):
    enabled: bool = True
    provider: str = "mock"
    interval_days: int = Field(1, ge=1, le=90)
    # When set, this wins over interval_days. Lets the sync run several
    # times a day, which interval_days alone cannot express.
    interval_hours: Optional[int] = Field(None, ge=1, le=2160)
    run_hour_utc: int = Field(3, ge=0, le=23)        # which hour of the day to run
    auto_publish: bool = True                        # imported -> active vs pending
    max_per_run: int = Field(100, ge=1, le=200_000)

    # When False (the default) every kind of listing is imported and distress is
    # only tagged where the source actually reports it. Turn it on to restrict
    # the import to foreclosures/auctions/REO only.
    distressed_only: bool = False
    status_types: List[str] = ["ForSale"]            # ForSale / ForRent / RecentlySold
    home_types: List[str] = []                       # empty = every property type

    distress_types: List[DistressType] = [
        DistressType.PRE_FORECLOSURE,
        DistressType.FORECLOSURE,
        DistressType.AUCTION,
        DistressType.BANK_OWNED,
    ]
    target_states: List[str] = ["TX", "FL", "GA"]
    target_cities: List[str] = []
    target_zip_codes: List[str] = []
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    update_existing: bool = True                     # refresh price/status on re-sync
    geocode_missing: bool = True
    notify_admin_on_run: bool = False


class SyncSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    provider: Optional[str] = None
    interval_days: Optional[int] = Field(None, ge=1, le=90)
    interval_hours: Optional[int] = Field(None, ge=1, le=2160)
    run_hour_utc: Optional[int] = Field(None, ge=0, le=23)
    auto_publish: Optional[bool] = None
    max_per_run: Optional[int] = Field(None, ge=1, le=200_000)
    distressed_only: Optional[bool] = None
    status_types: Optional[List[str]] = None
    home_types: Optional[List[str]] = None
    distress_types: Optional[List[DistressType]] = None
    target_states: Optional[List[str]] = None
    target_cities: Optional[List[str]] = None
    target_zip_codes: Optional[List[str]] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    update_existing: Optional[bool] = None
    geocode_missing: Optional[bool] = None
    notify_admin_on_run: Optional[bool] = None


class SyncSettingsResponse(SyncSettings):
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    available_providers: List[Dict[str, Any]] = []
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None


# ─── Sync run log ───

class SyncRunResponse(BaseModel):
    id: str
    provider: str
    trigger: SyncTrigger
    status: SyncRunStatus
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: List[str] = []
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    triggered_by: Optional[str] = None


# ─── Claims ───

class ClaimCreate(BaseModel):
    message: Optional[str] = Field(None, max_length=1000)
    proof_urls: List[str] = []
    contact_phone: Optional[str] = None


class ClaimReject(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class ClaimResponse(BaseModel):
    id: str
    property_id: str
    property_title: Optional[str] = None
    property_slug: Optional[str] = None
    property_image: Optional[str] = None
    property_address: Optional[str] = None
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    status: str
    message: Optional[str] = None
    proof_urls: List[str] = []
    rejection_reason: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ─── Edit requests ───

class EditRequestCreate(BaseModel):
    """Free-form changes; validated against PropertyUpdate before storing."""
    changes: Dict[str, Any]
    note: Optional[str] = Field(None, max_length=1000)


class EditRequestReject(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class FieldDiff(BaseModel):
    field: str
    label: str
    old: Any = None
    new: Any = None


class EditRequestResponse(BaseModel):
    id: str
    property_id: str
    property_title: Optional[str] = None
    property_slug: Optional[str] = None
    property_image: Optional[str] = None
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    status: EditRequestStatus
    changes: Dict[str, Any] = {}
    diff: List[FieldDiff] = []
    note: Optional[str] = None
    rejection_reason: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
