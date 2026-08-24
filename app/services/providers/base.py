"""
PropertyKING — Distressed Property Provider Interface

Every external data source (Zillow scraper, ATTOM, PropStream, a CSV drop, ...)
implements this one interface and returns `NormalizedProperty` objects.

Nothing outside this package knows which provider is in use, so swapping the
data source later means writing one new file and flipping the provider name in
the admin panel — no changes to the sync engine, routes, or frontend.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
import hashlib
import json


@dataclass
class NormalizedImage:
    url: str
    caption: Optional[str] = None
    is_primary: bool = False
    order: int = 0


@dataclass
class NormalizedProperty:
    """
    Provider-agnostic shape. The sync engine maps this onto PropertyKING's
    own property document — providers never touch the database schema.
    """

    # Identity (required)
    external_id: str
    source_url: Optional[str] = None

    # Headline
    title: str = ""
    description: str = ""
    price: float = 0.0
    listing_type: str = "sale"          # sale | rent | lease
    price_unit: str = "total"

    # Distress — None for an ordinary listing. Only set when the source
    # actually reports foreclosure/auction/REO status.
    distress_type: Optional[str] = None  # must match models.sync.DistressType
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

    # Location
    address: Optional[str] = None
    unit: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    county: Optional[str] = None
    neighborhood: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Details
    property_type: Optional[str] = None   # free text, matched to property_types
    bedrooms: int = 0
    bathrooms: float = 0.0
    half_baths: int = 0
    total_sqft: Optional[int] = None
    lot_size_sqft: Optional[int] = None
    lot_size_acres: Optional[float] = None
    year_built: Optional[int] = None
    stories: Optional[int] = None
    garage_spaces: int = 0
    parking_type: Optional[str] = None
    basement: Optional[str] = None
    hoa_fee: Optional[float] = None
    property_tax_annual: Optional[float] = None
    zoning: Optional[str] = None
    heating: Optional[str] = None
    cooling: Optional[str] = None
    flooring: List[str] = field(default_factory=list)
    appliances_included: List[str] = field(default_factory=list)
    mls_number: Optional[str] = None
    virtual_tour_url: Optional[str] = None

    # Media
    images: List[NormalizedImage] = field(default_factory=list)
    video_url: Optional[str] = None

    # Contact
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None

    # Anything provider-specific worth keeping for debugging
    raw: Dict[str, Any] = field(default_factory=dict)

    def content_hash(self) -> str:
        """
        Stable hash of the meaningful fields, used to skip DB writes when a
        re-sync returns identical data. `raw` and timestamps are excluded so
        cosmetic provider churn does not look like a change.
        """
        payload = asdict(self)
        payload.pop("raw", None)
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()


@dataclass
class ProviderFilters:
    """What the admin configured in the sync settings."""
    # False (default) = import every listing, tagging distress only where the
    # source reports it. True = restrict the import to distressed listings.
    distressed_only: bool = False
    distress_types: List[str] = field(default_factory=list)
    status_types: List[str] = field(default_factory=lambda: ["ForSale"])
    home_types: List[str] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    cities: List[str] = field(default_factory=list)
    zip_codes: List[str] = field(default_factory=list)
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    limit: int = 100


class BaseProvider(ABC):
    """Base class for every distressed-property data source."""

    # Shown in the admin panel's provider dropdown
    name: str = "base"
    label: str = "Base Provider"
    description: str = ""
    requires_api_key: bool = False
    is_free: bool = False

    @classmethod
    def is_configured(cls) -> bool:
        """True when this provider has everything it needs to run."""
        return True

    @abstractmethod
    async def fetch(self, filters: ProviderFilters) -> List[NormalizedProperty]:
        """Fetch distressed listings matching the filters."""
        raise NotImplementedError

    @classmethod
    def info(cls) -> Dict[str, Any]:
        return {
            "name": cls.name,
            "label": cls.label,
            "description": cls.description,
            "requires_api_key": cls.requires_api_key,
            "is_free": cls.is_free,
            "configured": cls.is_configured(),
        }
