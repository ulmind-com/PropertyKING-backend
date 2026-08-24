"""
PropertyKING — Mock Distressed Property Provider

Free, offline, zero-config. Generates realistic distressed listings so the whole
sync → claim → edit-approval pipeline can be built, demoed and tested before the
client picks (and pays for) a real data source.

External IDs are deterministic, so re-running a sync updates the same records
instead of creating duplicates — exactly like a real provider would behave.
"""

import random
from datetime import timedelta
from typing import List

from app.services.providers.base import (
    BaseProvider, NormalizedProperty, NormalizedImage, ProviderFilters
)
from app.utils.helpers import now_utc


# Real city/county pairs so generated data looks plausible on a map
CITY_POOL = {
    "TX": [("Houston", "Harris", 29.7604, -95.3698), ("Dallas", "Dallas", 32.7767, -96.7970),
           ("San Antonio", "Bexar", 29.4241, -98.4936), ("Austin", "Travis", 30.2672, -97.7431),
           ("Fort Worth", "Tarrant", 32.7555, -97.3308)],
    "FL": [("Miami", "Miami-Dade", 25.7617, -80.1918), ("Orlando", "Orange", 28.5383, -81.3792),
           ("Tampa", "Hillsborough", 27.9506, -82.4572), ("Jacksonville", "Duval", 30.3322, -81.6557)],
    "GA": [("Atlanta", "Fulton", 33.7490, -84.3880), ("Savannah", "Chatham", 32.0809, -81.0912),
           ("Augusta", "Richmond", 33.4735, -82.0105)],
    "OH": [("Cleveland", "Cuyahoga", 41.4993, -81.6944), ("Columbus", "Franklin", 39.9612, -82.9988),
           ("Cincinnati", "Hamilton", 39.1031, -84.5120)],
    "MI": [("Detroit", "Wayne", 42.3314, -83.0458), ("Flint", "Genesee", 43.0125, -83.6875)],
    "IL": [("Chicago", "Cook", 41.8781, -87.6298), ("Rockford", "Winnebago", 42.2711, -89.0940)],
    "AZ": [("Phoenix", "Maricopa", 33.4484, -112.0740), ("Tucson", "Pima", 32.2226, -110.9747)],
    "NV": [("Las Vegas", "Clark", 36.1699, -115.1398), ("Reno", "Washoe", 39.5296, -119.8138)],
    "NC": [("Charlotte", "Mecklenburg", 35.2271, -80.8431), ("Raleigh", "Wake", 35.7796, -78.6382)],
    "PA": [("Philadelphia", "Philadelphia", 39.9526, -75.1652), ("Pittsburgh", "Allegheny", 40.4406, -79.9959)],
}

STREETS = [
    "Oakwood Dr", "Maple Ave", "Cedar Ln", "Elm St", "Sunset Blvd", "Willow Creek Rd",
    "Magnolia Ct", "Birchwood Way", "Riverside Dr", "Hillcrest Ave", "Pinehurst Ln",
    "Sycamore St", "Brookside Dr", "Meadow Ln", "Ashford Pl", "Lakeview Ter",
]

PROPERTY_TYPES = ["House", "Condo", "Townhouse", "Multi-Family", "Mobile Home"]

LENDERS = [
    "Wells Fargo Bank N.A.", "Bank of America N.A.", "JPMorgan Chase Bank",
    "US Bank National Association", "PNC Bank N.A.", "Deutsche Bank Trust Co.",
]

CONDITION_NOTES = [
    "Sold as-is. Buyer responsible for all inspections and repairs.",
    "Property has deferred maintenance. Cash offers preferred.",
    "Occupancy status unknown. Do not disturb occupants.",
    "Roof and HVAC nearing end of life. Priced accordingly.",
    "Great rehab opportunity in an established neighbourhood.",
    "Interior access not available. Drive-by viewing only.",
]

HEATING = ["Forced Air", "Central Gas", "Heat Pump", "Baseboard", "None"]
COOLING = ["Central Air", "Window Units", "Evaporative", "None"]


def _anchor():
    """
    Dates are generated relative to the start of the current month, not "now".
    A real provider returns a fixed calendar auction date, so anchoring this way
    keeps the content hash stable between runs — otherwise every single sync
    would look like an update and rewrite the whole collection.
    """
    return now_utc().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class MockProvider(BaseProvider):
    name = "mock"
    label = "Demo Data (Free)"
    description = (
        "Generates realistic distressed listings offline. No API key, no cost. "
        "Use this to test the full pipeline, then switch to a real provider."
    )
    requires_api_key = False
    is_free = True

    @classmethod
    def is_configured(cls) -> bool:
        return True

    async def fetch(self, filters: ProviderFilters) -> List[NormalizedProperty]:
        states = [s.upper() for s in filters.states if s.upper() in CITY_POOL] or list(CITY_POOL.keys())
        distress_types = filters.distress_types or [
            "pre_foreclosure", "foreclosure", "auction", "bank_owned"
        ]

        # Everything below is derived from a seed built out of the index and the
        # filter set — never the global RNG. Two runs with the same settings
        # therefore return the same properties, so the sync engine updates them
        # instead of inserting duplicates every time.
        fingerprint = f"{sorted(states)}|{sorted(distress_types)}|{filters.distressed_only}"

        results: List[NormalizedProperty] = []
        for i in range(filters.limit):
            picker = random.Random(f"{fingerprint}|{i}")
            state = picker.choice(states)
            city, county, base_lat, base_lng = picker.choice(CITY_POOL[state])

            # In "import everything" mode most listings are ordinary, with a
            # realistic minority carrying distress — same shape the live API
            # returns when we do not filter server-side.
            if filters.distressed_only:
                distress = picker.choice(distress_types)
            else:
                distress = picker.choice(distress_types) if picker.random() < 0.25 else None

            street_no = 100 + (i * 37) % 9800
            street = STREETS[i % len(STREETS)]
            external_id = f"MOCK-{state}-{city[:3].upper()}-{street_no}-{i % len(STREETS)}"

            prop = self._build(
                external_id=external_id,
                street=f"{street_no} {street}",
                city=city, county=county, state=state,
                base_lat=base_lat, base_lng=base_lng,
                distress=distress, seed=i,
            )

            if filters.min_price and prop.price < filters.min_price:
                continue
            if filters.max_price and prop.price > filters.max_price:
                continue
            if filters.cities and prop.city not in filters.cities:
                continue
            if filters.zip_codes and prop.zip_code not in filters.zip_codes:
                continue

            results.append(prop)

        return results

    def _build(self, external_id, street, city, county, state,
               base_lat, base_lng, distress, seed) -> NormalizedProperty:
        rng = random.Random(external_id)  # stable per-property values across runs

        market_value = rng.randint(120_000, 720_000)
        discount = {
            "pre_foreclosure": rng.uniform(0.72, 0.90),
            "foreclosure": rng.uniform(0.60, 0.80),
            "auction": rng.uniform(0.50, 0.72),
            "bank_owned": rng.uniform(0.65, 0.85),
            "short_sale": rng.uniform(0.68, 0.86),
            "tax_lien": rng.uniform(0.40, 0.65),
            "fixer_upper": rng.uniform(0.70, 0.88),
        }.get(distress, 0.75)

        # A normal listing sits at market value; a distressed one is discounted.
        price = int(market_value * (discount if distress else 1.0) / 1000) * 1000
        beds = rng.randint(2, 5)
        baths = rng.choice([1, 1.5, 2, 2.5, 3, 3.5])
        sqft = rng.randint(850, 3800)
        year = rng.randint(1945, 2016)
        ptype = rng.choice(PROPERTY_TYPES)
        unpaid = int(market_value * rng.uniform(0.55, 0.95))
        lot = rng.randint(4000, 18000)

        if distress:
            label = distress.replace("_", " ").title()
            title = f"{label} — {beds} Bed {ptype} in {city}, {state}"
            description = (
                f"{label} opportunity at {street}, {city}, {state}. "
                f"This {sqft:,} sq ft {ptype.lower()} was built in {year} and offers "
                f"{beds} bedrooms and {baths} bathrooms on a {lot:,} sq ft lot. "
                f"Estimated market value is ${market_value:,}, listed at ${price:,} — "
                f"an estimated ${market_value - price:,} below market. "
                f"{rng.choice(CONDITION_NOTES)}"
            )
        else:
            title = f"{beds} Bed {ptype} in {city}, {state}"
            description = (
                f"{beds} bedroom, {baths} bathroom {ptype.lower()} at {street}, "
                f"{city}, {state}. Built in {year}, offering {sqft:,} sq ft of living "
                f"space on a {lot:,} sq ft lot. Listed at ${price:,}."
            )

        images = [
            NormalizedImage(
                url=f"https://picsum.photos/seed/{external_id}-{n}/1200/800",
                caption=cap, is_primary=(n == 0), order=n,
            )
            for n, cap in enumerate(["Exterior", "Living Area", "Kitchen", "Bedroom", "Yard"])
        ]

        anchor = _anchor()
        auction_date = None
        opening_bid = None
        if distress in ("auction", "foreclosure"):
            auction_date = anchor + timedelta(days=rng.randint(35, 150))
            opening_bid = int(price * rng.uniform(0.70, 0.95) / 500) * 500

        return NormalizedProperty(
            external_id=external_id,
            source_url=f"https://example-demo-source.local/homes/{external_id}",
            title=title,
            description=description,
            price=float(price),
            listing_type="sale",
            distress_type=distress,
            # Foreclosure paperwork only exists for distressed listings
            auction_date=auction_date,
            opening_bid=opening_bid,
            estimated_value=float(market_value) if distress else None,
            estimated_equity=float(market_value - price) if distress else None,
            unpaid_balance=float(unpaid) if distress else None,
            default_amount=float(rng.randint(4_000, 60_000)) if distress else None,
            lender=rng.choice(LENDERS) if distress else None,
            case_number=(f"{state}-{rng.randint(2023, 2026)}-CV-{rng.randint(10000, 99999)}"
                         if distress else None),
            filed_date=anchor - timedelta(days=rng.randint(20, 400)) if distress else None,
            days_on_market=rng.randint(3, 260),
            price_reduced=rng.random() < 0.4,
            address=street,
            city=city,
            state=state,
            county=county,
            zip_code=f"{rng.randint(10000, 99999)}",
            latitude=round(base_lat + rng.uniform(-0.18, 0.18), 6),
            longitude=round(base_lng + rng.uniform(-0.18, 0.18), 6),
            property_type=ptype,
            bedrooms=beds,
            bathrooms=float(baths),
            total_sqft=sqft,
            lot_size_sqft=rng.randint(4000, 18000),
            year_built=year,
            stories=rng.randint(1, 3),
            garage_spaces=rng.randint(0, 3),
            property_tax_annual=float(rng.randint(1200, 12000)),
            heating=rng.choice(HEATING),
            cooling=rng.choice(COOLING),
            mls_number=f"MLS{rng.randint(1000000, 9999999)}",
            images=images,
            raw={"generated": True, "market_value": market_value},
        )
