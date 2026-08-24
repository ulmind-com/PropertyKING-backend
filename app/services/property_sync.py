"""
PropertyKING — Distressed Property Sync Engine

Pulls distressed listings from whichever provider the admin selected, maps them
onto PropertyKING's own property schema, and upserts them — deduplicating on
(source.provider, source.external_id) so repeated runs update rather than
duplicate.

Rules that matter:
  * A property a user has CLAIMED is never content-overwritten by a re-sync.
    Only the distress data and the last-synced timestamp are refreshed, so the
    owner's edits survive.
  * Identical payloads are skipped via a content hash, which keeps write load
    and `updated_at` churn down.
  * Every run is recorded in `sync_runs` and visible in the admin panel.
"""

from typing import Optional, Dict
from datetime import datetime, timedelta, timezone
import traceback

from app.database import get_database
from app.models.sync import SyncSettings, SyncRunStatus, SyncTrigger, ClaimStatus
from app.services.providers import get_provider, list_providers, ProviderFilters
from app.services.providers.base import NormalizedProperty
from app.services.geocoding import geocode_address
from app.utils.helpers import now_utc, generate_unique_slug

SETTINGS_KEY = "distressed_sync"
LOCK_KEY = "distressed_sync_lock"
LOCK_TTL_MINUTES = 30

IMPORT_USER_EMAIL = "imports@propertyking.system"


# ─── Settings ───

async def get_sync_settings() -> SyncSettings:
    """Read sync settings, seeding defaults on first access."""
    db = get_database()
    doc = await db.sync_settings.find_one({"_id": SETTINGS_KEY})
    if not doc:
        defaults = SyncSettings()
        await db.sync_settings.insert_one({
            "_id": SETTINGS_KEY,
            **defaults.model_dump(mode="json"),
            "last_run_at": None,
            "next_run_at": None,
            "updated_at": now_utc(),
            "updated_by": None,
        })
        return defaults

    doc.pop("_id", None)
    known = SyncSettings.model_fields.keys()
    return SyncSettings(**{k: v for k, v in doc.items() if k in known})


async def get_sync_settings_doc() -> dict:
    """Raw settings document including run metadata."""
    await get_sync_settings()  # ensure seeded
    db = get_database()
    return await db.sync_settings.find_one({"_id": SETTINGS_KEY}) or {}


async def save_sync_settings(changes: dict, admin_id: Optional[str] = None) -> dict:
    """Apply a partial settings update and recompute the next run time."""
    db = get_database()
    await get_sync_settings()  # ensure seeded

    changes = {k: v for k, v in changes.items() if v is not None}
    changes["updated_at"] = now_utc()
    changes["updated_by"] = admin_id

    await db.sync_settings.update_one({"_id": SETTINGS_KEY}, {"$set": changes})

    settings = await get_sync_settings()
    doc = await get_sync_settings_doc()
    next_run = compute_next_run(settings, doc.get("last_run_at"))
    await db.sync_settings.update_one({"_id": SETTINGS_KEY}, {"$set": {"next_run_at": next_run}})

    return await get_sync_settings_doc()


def compute_next_run(settings: SyncSettings, last_run_at: Optional[datetime]) -> Optional[datetime]:
    """Next scheduled run: last run + interval, pinned to the configured hour."""
    if not settings.enabled:
        return None

    base = last_run_at or now_utc()
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)

    nxt = base + timedelta(days=settings.interval_days)
    nxt = nxt.replace(hour=settings.run_hour_utc, minute=0, second=0, microsecond=0)

    # Never schedule into the past (e.g. after shrinking the interval)
    while nxt <= now_utc():
        nxt += timedelta(days=settings.interval_days)
    return nxt


# ─── Supporting lookups ───

async def get_import_user_id() -> str:
    """
    Imported listings need a `listed_by`. A dedicated system user keeps them out
    of any real admin's listing counts and makes them easy to filter.
    """
    db = get_database()
    user = await db.users.find_one({"email": IMPORT_USER_EMAIL})
    if user:
        return str(user["_id"])

    result = await db.users.insert_one({
        "full_name": "PropertyKING Imports",
        "email": IMPORT_USER_EMAIL,
        "phone": None,
        "password_hash": None,       # cannot log in
        "avatar": None,
        "role": "lister",
        "lister_type": "owner",
        "license_number": None,
        "company_name": "PropertyKING",
        "bio": "Automated distressed-property import account",
        "verified": True,
        "is_system": True,
        "is_active": True,
        "fcm_token": None,
        "location": None,
        "favorites": [],
        "created_at": now_utc(),
        "updated_at": now_utc(),
    })
    return str(result.inserted_id)


async def _property_type_map() -> Dict[str, str]:
    """Lowercased property type name -> id."""
    db = get_database()
    cursor = db.property_types.find({}, {"name": 1})
    return {doc["name"].lower(): str(doc["_id"]) async for doc in cursor}


# ─── Mapping ───

def _distress_doc(item: NormalizedProperty) -> Optional[dict]:
    """None for an ordinary listing — only distressed ones get a distress block."""
    if not item.distress_type:
        return None
    return {
        "is_distressed": True,
        "type": item.distress_type,
        "auction_date": item.auction_date,
        "opening_bid": item.opening_bid,
        "estimated_value": item.estimated_value,
        "estimated_equity": item.estimated_equity,
        "unpaid_balance": item.unpaid_balance,
        "default_amount": item.default_amount,
        "lender": item.lender,
        "case_number": item.case_number,
        "filed_date": item.filed_date,
        "days_on_market": item.days_on_market,
        "price_reduced": item.price_reduced,
    }


def _details_doc(item: NormalizedProperty) -> dict:
    return {
        "bedrooms": item.bedrooms or 0,
        "bathrooms": item.bathrooms or 0,
        "half_baths": item.half_baths or 0,
        "total_sqft": item.total_sqft,
        "lot_size_sqft": item.lot_size_sqft,
        "lot_size_acres": item.lot_size_acres,
        "year_built": item.year_built,
        "stories": item.stories,
        "garage_spaces": item.garage_spaces or 0,
        "parking_type": item.parking_type,
        "basement": item.basement,
        "hoa_fee": item.hoa_fee,
        "hoa_frequency": "monthly",
        "property_tax_annual": item.property_tax_annual,
        "zoning": item.zoning,
        "construction_material": None,
        "roof_type": None,
        "heating": item.heating,
        "cooling": item.cooling,
        "flooring": item.flooring or [],
        "appliances_included": item.appliances_included or [],
        "mls_number": item.mls_number,
        "virtual_tour_url": item.virtual_tour_url,
        "open_house_dates": [],
    }


def _location_doc(item: NormalizedProperty) -> dict:
    coords = [0.0, 0.0]
    if item.longitude is not None and item.latitude is not None:
        coords = [float(item.longitude), float(item.latitude)]
    return {
        "address": item.address,
        "unit": item.unit,
        "city": item.city,
        "state": item.state,
        "zip_code": item.zip_code,
        "county": item.county,
        "neighborhood": item.neighborhood,
        "coordinates": {"type": "Point", "coordinates": coords},
    }


# ─── The run ───

async def _acquire_lock() -> bool:
    """
    Mongo-based lock so multiple uvicorn workers (or a manual run racing the
    scheduler) cannot sync at the same time. Expires so a crash cannot wedge it.
    """
    db = get_database()
    cutoff = now_utc() - timedelta(minutes=LOCK_TTL_MINUTES)
    await db.sync_locks.delete_many({"_id": LOCK_KEY, "acquired_at": {"$lt": cutoff}})
    try:
        await db.sync_locks.insert_one({"_id": LOCK_KEY, "acquired_at": now_utc()})
        return True
    except Exception:
        return False


async def _release_lock():
    db = get_database()
    await db.sync_locks.delete_one({"_id": LOCK_KEY})


async def run_sync(trigger: str = SyncTrigger.SCHEDULE, triggered_by: Optional[str] = None) -> dict:
    """Execute one sync run. Returns the run summary document."""
    db = get_database()
    settings = await get_sync_settings()

    if not await _acquire_lock():
        return {"status": "skipped", "reason": "Another sync is already running"}

    run_doc = {
        "provider": settings.provider,
        "trigger": trigger,
        "status": SyncRunStatus.RUNNING.value,
        "fetched": 0, "created": 0, "updated": 0, "skipped": 0, "failed": 0,
        "errors": [],
        "started_at": now_utc(),
        "finished_at": None,
        "duration_seconds": None,
        "triggered_by": triggered_by,
    }
    run_id = (await db.sync_runs.insert_one(run_doc)).inserted_id

    try:
        provider = get_provider(settings.provider)
        filters = ProviderFilters(
            distressed_only=settings.distressed_only,
            distress_types=[d.value if hasattr(d, "value") else d for d in settings.distress_types],
            status_types=settings.status_types,
            home_types=settings.home_types,
            states=settings.target_states,
            cities=settings.target_cities,
            zip_codes=settings.target_zip_codes,
            min_price=settings.min_price,
            max_price=settings.max_price,
            limit=settings.max_per_run,
        )

        items = await provider.fetch(filters)
        run_doc["fetched"] = len(items)

        type_map = await _property_type_map()
        import_user_id = await get_import_user_id()

        for item in items:
            try:
                outcome = await _upsert_property(item, settings, type_map, import_user_id)
                run_doc[outcome] += 1
            except Exception as exc:
                run_doc["failed"] += 1
                if len(run_doc["errors"]) < 20:
                    run_doc["errors"].append(f"{item.external_id}: {exc}")

        if run_doc["failed"] == 0:
            run_doc["status"] = SyncRunStatus.SUCCESS.value
        elif run_doc["created"] or run_doc["updated"]:
            run_doc["status"] = SyncRunStatus.PARTIAL.value
        else:
            run_doc["status"] = SyncRunStatus.FAILED.value

    except Exception as exc:
        run_doc["status"] = SyncRunStatus.FAILED.value
        run_doc["errors"].append(str(exc))
        print(f"[SYNC] Failed: {exc}\n{traceback.format_exc()}")

    finally:
        run_doc["finished_at"] = now_utc()
        run_doc["duration_seconds"] = round(
            (run_doc["finished_at"] - run_doc["started_at"]).total_seconds(), 2
        )
        await db.sync_runs.update_one({"_id": run_id}, {"$set": run_doc})

        next_run = compute_next_run(settings, run_doc["finished_at"])
        await db.sync_settings.update_one(
            {"_id": SETTINGS_KEY},
            {"$set": {"last_run_at": run_doc["finished_at"], "next_run_at": next_run}},
        )
        await _release_lock()

    print(
        f"[SYNC] {run_doc['status']} — fetched={run_doc['fetched']} "
        f"created={run_doc['created']} updated={run_doc['updated']} "
        f"skipped={run_doc['skipped']} failed={run_doc['failed']}"
    )

    run_doc["id"] = str(run_id)
    return run_doc


async def _upsert_property(
    item: NormalizedProperty,
    settings: SyncSettings,
    type_map: Dict[str, str],
    import_user_id: str,
) -> str:
    """Insert or update one property. Returns 'created' | 'updated' | 'skipped'."""
    db = get_database()

    existing = await db.properties.find_one({
        "source.provider": settings.provider,
        "source.external_id": item.external_id,
    })

    content_hash = item.content_hash()

    # ── Existing record ──
    if existing:
        if not settings.update_existing:
            return "skipped"

        claim_status = (existing.get("claim") or {}).get("status")

        # A claimed property belongs to its owner now — never clobber their edits.
        if claim_status == ClaimStatus.CLAIMED.value:
            await db.properties.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "distress": _distress_doc(item),
                    "source.last_synced_at": now_utc(),
                }},
            )
            return "skipped"

        if existing.get("source", {}).get("content_hash") == content_hash:
            await db.properties.update_one(
                {"_id": existing["_id"]},
                {"$set": {"source.last_synced_at": now_utc()}},
            )
            return "skipped"

        update = {
            "title": item.title,
            "description": item.description,
            "price": item.price,
            "details": _details_doc(item),
            "location": await _resolve_location(item, settings, existing),
            "distress": _distress_doc(item),
            "images": [
                {"url": i.url, "caption": i.caption, "is_primary": i.is_primary, "order": i.order}
                for i in item.images
            ] or existing.get("images", []),
            "source.url": item.source_url,
            "source.content_hash": content_hash,
            "source.last_synced_at": now_utc(),
            "updated_at": now_utc(),
        }
        if item.property_type and item.property_type.lower() in type_map:
            update["property_type_id"] = type_map[item.property_type.lower()]

        await db.properties.update_one({"_id": existing["_id"]}, {"$set": update})
        return "updated"

    # ── New record ──
    slug = await generate_unique_slug(db.properties, item.title or f"distressed-{item.external_id}")
    property_type_id = type_map.get((item.property_type or "House").lower()) or type_map.get("house")

    doc = {
        "title": item.title,
        "slug": slug,
        "description": item.description,
        "property_type_id": property_type_id,
        "listing_type": item.listing_type or "sale",
        "status": "active" if settings.auto_publish else "pending",
        "price": item.price,
        "price_unit": item.price_unit or "total",
        "currency": "USD",
        "details": _details_doc(item),
        "amenities": [],
        "location": await _resolve_location(item, settings, None),
        "images": [
            {"url": i.url, "caption": i.caption, "is_primary": i.is_primary, "order": i.order}
            for i in item.images
        ],
        "video_url": item.video_url,
        "floor_plan_url": None,
        "floor_plan_urls": [],
        "listed_by": import_user_id,
        "contact_phone": item.contact_phone,
        "contact_email": item.contact_email,
        "admin_review": None,
        "views_count": 0,
        "favorites_count": 0,
        "inquiries_count": 0,
        "listed_at": now_utc() if settings.auto_publish else None,
        "created_at": now_utc(),
        "updated_at": now_utc(),

        # Distressed-import specific
        "source": {
            "provider": settings.provider,
            "external_id": item.external_id,
            "url": item.source_url,
            "content_hash": content_hash,
            "first_imported_at": now_utc(),
            "last_synced_at": now_utc(),
        },
        "distress": _distress_doc(item),
        "claim": {
            "status": ClaimStatus.UNCLAIMED.value,
            "claimed_by": None,
            "claimed_at": None,
            "approved_by": None,
            "approved_at": None,
        },
        "has_pending_edit": False,
    }

    await db.properties.insert_one(doc)
    return "created"


async def _resolve_location(
    item: NormalizedProperty, settings: SyncSettings, existing: Optional[dict]
) -> dict:
    """Build the location sub-document, geocoding only when coordinates are missing."""
    location = _location_doc(item)
    coords = location["coordinates"]["coordinates"]

    if coords != [0.0, 0.0]:
        return location

    # Reuse coordinates we already geocoded for this property
    if existing:
        old = ((existing.get("location") or {}).get("coordinates") or {}).get("coordinates")
        if old and old != [0.0, 0.0]:
            location["coordinates"] = {"type": "Point", "coordinates": old}
            return location

    if settings.geocode_missing and (item.address or item.city):
        geo = await geocode_address(
            item.address or "", item.city or "", item.state or "", item.zip_code or ""
        )
        if geo:
            location["coordinates"] = {"type": "Point", "coordinates": [geo["lng"], geo["lat"]]}

    return location


# ─── Stats for the admin dashboard ───

async def sync_overview() -> dict:
    db = get_database()
    settings_doc = await get_sync_settings_doc()

    imported = await db.properties.count_documents({"source.provider": {"$exists": True}})
    distressed = await db.properties.count_documents({"distress.is_distressed": True})
    unclaimed = await db.properties.count_documents({"claim.status": "unclaimed"})
    pending_claims = await db.property_claims.count_documents({"status": "pending"})
    claimed = await db.properties.count_documents({"claim.status": "claimed"})
    pending_edits = await db.property_edit_requests.count_documents({"status": "pending"})

    by_type = await db.properties.aggregate([
        {"$match": {"distress.is_distressed": True}},
        {"$group": {"_id": "$distress.type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]).to_list(20)

    return {
        "imported": imported,
        "distressed": distressed,
        "unclaimed": unclaimed,
        "claimed": claimed,
        "pending_claims": pending_claims,
        "pending_edits": pending_edits,
        "by_distress_type": [{"type": r["_id"], "count": r["count"]} for r in by_type if r["_id"]],
        "last_run_at": settings_doc.get("last_run_at"),
        "next_run_at": settings_doc.get("next_run_at"),
        "providers": list_providers(),
    }
