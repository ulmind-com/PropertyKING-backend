"""
PropertyKING — Zillow via ReefAPI (RapidAPI)

Zillow has no official public listings API. This talks to ReefAPI's Zillow
endpoint on RapidAPI, which returns normalized JSON for for-sale, for-rent and
recently-sold listings.

  Docs     https://reefapi.com/docs/zillow
  Pricing  Basic $0 (100 req/mo) · Pro $10 (10k) · Ultra $40 (50k)
  Host     zillow-real-estate-data-api.p.rapidapi.com

Notes that shaped this adapter:
  * Requests are POST with a JSON body, not GET with a query string.
  * There are no foreclosure/auction filters, so distress is detected from the
    listing itself (see `detect_distress`) rather than filtered server-side.
    That matches how we import: everything comes in, distressed ones get tagged.
  * `max_results` lets the API paginate internally, so one request can return
    far more than one page — much kinder to a small monthly quota.

Setup: subscribe to the API on RapidAPI (Basic is free), then put the key in
.env as RAPIDAPI_KEY. Run `python probe_zillow.py` to verify.
"""

import asyncio
import re
from typing import List, Optional, Dict, Any

import httpx

from app.config import settings
from app.services.providers.base import (
    BaseProvider, NormalizedProperty, NormalizedImage, ProviderFilters
)

DEFAULT_HOST = "zillow-real-estate-data-api.p.rapidapi.com"
SEARCH_PATH = "/zillow/v1/search"

# Our listing statuses -> the API's `status` values
STATUS_MAP = {
    "ForSale": "for_sale",
    "ForRent": "for_rent",
    "RecentlySold": "sold",
}

# The API's property_type values -> PropertyKING property type names
PROPERTY_TYPE_MAP = {
    "house": "House",
    "single_family": "House",
    "singlefamily": "House",
    "condo": "Condo",
    "townhouse": "Townhouse",
    "multi_family": "Multi-Family",
    "multifamily": "Multi-Family",
    "apartment": "Apartment",
    "manufactured": "Mobile Home",
    "mobile": "Mobile Home",
    "land": "Land",
    "lot": "Land",
    "farm": "Farm/Ranch",
}

# There are no foreclosure filters, so distressed-only mode leans on free-text
# keyword search — imprecise, but the only lever this API exposes.
DISTRESS_KEYWORDS = {
    "pre_foreclosure": "pre-foreclosure",
    "foreclosure": "foreclosure",
    "auction": "auction",
    "bank_owned": "bank owned REO",
    "short_sale": "short sale",
    "tax_lien": "tax lien",
    "fixer_upper": "fixer upper as-is",
}

# "1234 Oak St, Houston, TX 77001"
ADDRESS_RE = re.compile(
    r"^(?P<street>.+?),\s*(?P<city>[^,]+),\s*(?P<state>[A-Z]{2})\b\s*(?P<zip>\d{5})?"
)

DISTRESS_TEXT_PATTERNS = [
    ("pre_foreclosure", re.compile(r"pre[\s-]?foreclosure", re.I)),
    ("bank_owned",      re.compile(r"\b(bank[\s-]?owned|reo)\b", re.I)),
    ("auction",         re.compile(r"\bauction\b", re.I)),
    ("short_sale",      re.compile(r"short[\s-]?sale", re.I)),
    ("foreclosure",     re.compile(r"foreclos", re.I)),
]


def detect_distress(item: dict) -> Optional[str]:
    """
    Infer distress from a normal search result. Returns a DistressType value,
    or None for an ordinary listing.
    """
    haystack = " ".join(
        str(item.get(k) or "")
        for k in ("status", "status_text", "listing_status", "property_type",
                  "address_line", "url", "price_display")
    )
    for kind, pattern in DISTRESS_TEXT_PATTERNS:
        if pattern.search(haystack):
            return kind
    return None


class ReefZillowProvider(BaseProvider):
    name = "zillow_reefapi"
    label = "Zillow via ReefAPI"
    description = (
        "Zillow for-sale, rental and sold listings on RapidAPI. Free tier "
        "100 requests/month, $10/mo for 10,000. Unofficial — Zillow's ToS "
        "prohibits scraping, so the legal exposure sits with the site operator."
    )
    requires_api_key = True
    is_free = True

    # A deep search walks many pages server-side before responding: measured
    # ~20s for 820 listings and ~48s to exhaust a large market.
    TIMEOUT = 300.0
    # The Basic plan allows 3 req/sec; stay far under it so a long
    # backfill is never mistaken for abuse.
    DELAY_BETWEEN_CALLS = 4.0
    MAX_REQUESTS_PER_RUN = settings.ZILLOW_MAX_REQUESTS_PER_RUN
    RESULTS_PER_PAGE = 41
    # Zillow itself stops returning new results past roughly this depth, and a
    # deeper request only costs time and bandwidth.
    MAX_PAGES_PER_REQUEST = 20
    # The API rejects anything above this with INVALID_PARAM
    MAX_RESULTS_PER_REQUEST = 10_000

    def __init__(self):
        # Populated from response headers on every fetch, so callers can watch
        # the monthly allowance drain and stop before it is gone.
        self.last_quota_remaining: Optional[int] = None

    @classmethod
    def _api_key(cls) -> Optional[str]:
        return settings.RAPIDAPI_KEY or None

    @classmethod
    def _host(cls) -> str:
        host = settings.ZILLOW_RAPIDAPI_HOST
        # The old zillow-com1 default is dead; fall back to this API's host.
        return host if "reef" in host or "zillow-real-estate" in host else DEFAULT_HOST

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls._api_key())

    async def fetch(self, filters: ProviderFilters) -> List[NormalizedProperty]:
        if not self.is_configured():
            raise RuntimeError(
                "RAPIDAPI_KEY is not set. Add it to .env, or switch the provider "
                "to 'mock' in the admin sync settings."
            )

        locations = self._build_locations(filters)

        if filters.distressed_only:
            variants = [
                (d, {"keywords": DISTRESS_KEYWORDS.get(d, d.replace("_", " "))})
                for d in (filters.distress_types or list(DISTRESS_KEYWORDS))
            ]
        else:
            variants = [
                (None, {"status": STATUS_MAP.get(s, "for_sale")})
                for s in (filters.status_types or ["ForSale"])
            ]

        host = self._host()
        headers = {
            "X-RapidAPI-Key": self._api_key(),
            "X-RapidAPI-Host": host,
            "Content-Type": "application/json",
        }

        # Split the budget evenly so no single market drains it
        per_variant = max(1, filters.limit // max(1, len(locations) * len(variants)))

        # One HTTP request costs one unit of the monthly quota no matter how
        # many pages it walks internally, so ask for all the pages we need in a
        # single call instead of paging ourselves. Measured: max_pages=1 gives
        # 41 listings, max_pages=20 gives 820 — same quota cost.
        max_pages = min(
            self.MAX_PAGES_PER_REQUEST,
            max(1, -(-per_variant // self.RESULTS_PER_PAGE)),   # ceil
        )

        seen: Dict[str, NormalizedProperty] = {}
        errors: List[str] = []
        requests_used = 0
        quota_left: Optional[str] = None

        async with httpx.AsyncClient(timeout=self.TIMEOUT, headers=headers) as client:
            for location in locations:
                for distress, variant_body in variants:
                    if len(seen) >= filters.limit or requests_used >= self.MAX_REQUESTS_PER_RUN:
                        break

                    body: Dict[str, Any] = {
                        "location": location,
                        "status": "for_sale",
                        "max_results": min(per_variant, filters.limit,
                                           self.MAX_RESULTS_PER_REQUEST),
                        **variant_body,
                    }
                    # Past ~20 pages the API switches to a deeper strategy that
                    # returns several times more for the same single quota unit.
                    if per_variant > self.MAX_PAGES_PER_REQUEST * self.RESULTS_PER_PAGE:
                        body["fetch_all"] = True
                    else:
                        body["max_pages"] = max_pages
                    if filters.home_types:
                        body["home_type"] = filters.home_types[0]
                    if filters.min_price:
                        body["price_min"] = int(filters.min_price)
                    if filters.max_price:
                        body["price_max"] = int(filters.max_price)

                    try:
                        resp = await client.post(f"https://{host}{SEARCH_PATH}", json=body)
                        requests_used += 1
                        quota_left = (
                            resp.headers.get("x-ratelimit-requests-remaining") or quota_left
                        )

                        if resp.status_code == 404 and "doesn't exist" in (resp.text or ""):
                            raise RuntimeError(
                                f"Not subscribed to {host} on RapidAPI. Open the API's "
                                "Pricing tab and subscribe (Basic is free)."
                            )
                        if resp.status_code in (401, 403):
                            raise RuntimeError(
                                f"RapidAPI rejected the key for {host} (HTTP {resp.status_code})."
                            )
                        if resp.status_code == 429:
                            errors.append(f"{location}: monthly RapidAPI quota exhausted")
                            break
                        resp.raise_for_status()
                        payload = resp.json()

                        if isinstance(payload, dict) and payload.get("ok") is False:
                            err = payload.get("error") or {}
                            raise RuntimeError(
                                f"API rejected the request "
                                f"({err.get('code', 'error')}): {err.get('message', payload)}"
                            )
                    except RuntimeError:
                        raise
                    except Exception as exc:
                        errors.append(f"{location}/{distress or 'all'}: {exc}")
                        continue

                    for item in self._extract_items(payload):
                        kind = distress or detect_distress(item)
                        prop = self._normalize(item, kind)
                        if prop and prop.external_id not in seen:
                            seen[prop.external_id] = prop
                            if len(seen) >= filters.limit:
                                break

                    await asyncio.sleep(self.DELAY_BETWEEN_CALLS)

        try:
            self.last_quota_remaining = int(quota_left) if quota_left is not None else None
        except (TypeError, ValueError):
            self.last_quota_remaining = None

        print(
            f"[ZILLOW/reefapi] {len(seen)} listings from {requests_used} request(s)"
            + (f", quota remaining {quota_left}" if quota_left else "")
            + (f", {len(errors)} error(s)" if errors else "")
        )

        if not seen and errors:
            raise RuntimeError("Zillow fetch failed: " + "; ".join(errors[:5]))

        return list(seen.values())

    # ─── helpers ───

    @staticmethod
    def _extract_items(payload: Any) -> List[dict]:
        """The listing array has moved between keys across versions."""
        if isinstance(payload, list):
            return [i for i in payload if isinstance(i, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("results", "listings", "properties", "props", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [i for i in value if isinstance(i, dict)]
            if isinstance(value, dict):
                for inner in ("items", "results", "listings", "properties"):
                    if isinstance(value.get(inner), list):
                        return [i for i in value[inner] if isinstance(i, dict)]
        return []

    def _build_locations(self, filters: ProviderFilters) -> List[str]:
        """Turn the admin's zip/city/state config into search strings."""
        locations: List[str] = []
        locations.extend(filters.zip_codes)
        for city in filters.cities:
            locations.append(f"{city}, {filters.states[0]}" if filters.states else city)
        if not locations:
            locations.extend(filters.states)
        # Cap by the request budget rather than a fixed number, so a wide
        # backfill across many markets is not silently truncated to 10.
        return locations[:self.MAX_REQUESTS_PER_RUN] or ["TX"]

    def _normalize(self, item: dict, distress: Optional[str]) -> Optional[NormalizedProperty]:
        zpid = str(item.get("zpid") or item.get("id") or "").strip()
        if not zpid:
            return None

        street, city, state, zip_code = self._split_address(item)

        price = self._num(item.get("list_price_usd")) or self._num(item.get("price")) or 0.0
        zestimate = self._num(item.get("zestimate_usd"))
        rent_zestimate = self._num(item.get("rent_zestimate_usd"))
        beds = int(self._num(item.get("beds")) or 0)
        baths = float(self._num(item.get("baths")) or 0)
        sqft = self._num(item.get("sqft"))
        lot_sqft = self._num(item.get("lot_sqft"))

        raw_type = str(item.get("property_type") or "").lower().replace(" ", "_")
        ptype = PROPERTY_TYPE_MAP.get(raw_type, "House")

        status = str(item.get("status") or "").lower()
        is_rental = "rent" in status
        listing_type = "rent" if is_rental else "sale"
        price_unit = "per_month" if is_rental else "total"

        # `photos` is a plain array of URLs; older shapes used a single
        # `photo_url` or objects with a `url` key.
        images: List[NormalizedImage] = []
        seen_urls = set()
        candidates = list(item.get("photos") or [])
        for single in (item.get("photo_url"), item.get("image")):
            if single:
                candidates.insert(0, single)
        for entry in candidates:
            url = entry.get("url") if isinstance(entry, dict) else entry
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            images.append(NormalizedImage(
                url=url, is_primary=(len(images) == 0), order=len(images)
            ))
            if len(images) >= 20:   # matches MAX_IMAGES_PER_PROPERTY
                break

        label = distress.replace("_", " ").title() if distress else None
        where = f"{street}, {city}, {state}" if street else (city or state or "US")
        bits = " ".join(x for x in [f"{beds} Bed" if beds else "", ptype] if x)
        if label:
            title = f"{label} — {where}"
        elif street:
            # "4 Bed House at 11319 Olympia Dr, Houston, TX"
            title = f"{bits} at {where}" if bits else where
        else:
            title = f"{bits} in {where}" if bits else where

        description = (
            (f"{label} listing sourced from Zillow. " if label else "Listing sourced from Zillow. ")
            + f"{street or 'Address withheld'}, {city or ''} {state or ''} {zip_code or ''}. ".replace("  ", " ")
            + f"{beds} bed / {baths} bath"
            + (f", {int(sqft):,} sq ft" if sqft else "")
            + f". Listed at ${price:,.0f}" + ("/mo" if is_rental else "")
            + (f" against a Zestimate of ${zestimate:,.0f}" if zestimate else "")
            + ". Verify all details independently before making an offer."
        )

        return NormalizedProperty(
            external_id=zpid,
            source_url=item.get("url"),
            title=title[:500],
            description=description,
            price=float(price),
            listing_type=listing_type,
            price_unit=price_unit,
            distress_type=distress,
            estimated_value=zestimate,
            estimated_equity=(zestimate - price) if (zestimate and price and not is_rental) else None,
            days_on_market=int(self._num(item.get("days_on_market")) or 0) or None,
            address=street,
            city=city,
            state=state,
            zip_code=zip_code,
            latitude=self._num(item.get("latitude")),
            longitude=self._num(item.get("longitude")),
            property_type=ptype,
            bedrooms=beds,
            bathrooms=baths,
            total_sqft=int(sqft) if sqft else None,
            lot_size_sqft=int(lot_sqft) if lot_sqft else None,
            images=images,
            raw={"status": item.get("status"), "rent_zestimate_usd": rent_zestimate},
        )

    @staticmethod
    def _split_address(item: dict):
        """
        This API returns the street in `address_line` with `city`/`state_code`/
        `postal_code` alongside. Older/other shapes pack the whole address into
        one string, so fall back to parsing it.
        """
        street = item.get("street_address") or item.get("streetAddress")
        city = item.get("city")
        state = item.get("state_code") or item.get("state")
        zip_code = item.get("postal_code") or item.get("zipcode") or item.get("zip_code")

        line = item.get("address_line") or item.get("address")
        if isinstance(line, dict):
            street = street or line.get("streetAddress")
            city = city or line.get("city")
            state = state or line.get("state")
            zip_code = zip_code or line.get("zipcode")
        elif isinstance(line, str) and not (street and city and state):
            m = ADDRESS_RE.match(line.strip())
            if m:
                street = street or m.group("street")
                city = city or m.group("city")
                state = state or m.group("state")
                zip_code = zip_code or m.group("zip")
            else:
                street = street or line

        return street, city, state, zip_code

    @staticmethod
    def _num(value) -> Optional[float]:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(re.sub(r"[^\d.\-]", "", str(value)) or 0) or None
        except ValueError:
            return None
