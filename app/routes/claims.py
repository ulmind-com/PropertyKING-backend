"""
PropertyKING — Property Claims & Edit Requests (user-facing)

Flow:
  1. A user finds an unclaimed imported/distressed property and submits a claim.
  2. An admin approves it, and the property moves into that user's account.
  3. The owner can then edit it — but edits are queued as edit requests and only
     go live once an admin approves them.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
from typing import Optional, List, Any, Dict
import math

from app.database import get_database
from app.middleware.auth import get_current_user
from app.models.sync import (
    ClaimCreate, EditRequestCreate, ClaimStatus, EditRequestStatus
)
from app.models.property import PropertyUpdate
from app.utils.helpers import now_utc

router = APIRouter(prefix="/claims", tags=["Claims"])
edit_router = APIRouter(prefix="/edit-requests", tags=["Edit Requests"])


# ─── Shared helpers (also used by the admin routes) ───

FIELD_LABELS = {
    "title": "Title",
    "description": "Description",
    "price": "Price",
    "price_unit": "Price Unit",
    "listing_type": "Listing Type",
    "property_type_id": "Property Type",
    "status": "Status",
    "contact_phone": "Contact Phone",
    "contact_email": "Contact Email",
    "video_url": "Video URL",
    "floor_plan_url": "Floor Plan",
    "images": "Photos",
    "amenities": "Amenities",
    "details.bedrooms": "Bedrooms",
    "details.bathrooms": "Bathrooms",
    "details.half_baths": "Half Baths",
    "details.total_sqft": "Total Sq Ft",
    "details.lot_size_sqft": "Lot Size (sq ft)",
    "details.lot_size_acres": "Lot Size (acres)",
    "details.year_built": "Year Built",
    "details.stories": "Stories",
    "details.garage_spaces": "Garage Spaces",
    "details.parking_type": "Parking Type",
    "details.basement": "Basement",
    "details.hoa_fee": "HOA Fee",
    "details.property_tax_annual": "Annual Property Tax",
    "details.heating": "Heating",
    "details.cooling": "Cooling",
    "details.mls_number": "MLS Number",
    "location.address": "Address",
    "location.unit": "Unit",
    "location.city": "City",
    "location.state": "State",
    "location.zip_code": "ZIP Code",
    "location.county": "County",
    "location.neighborhood": "Neighborhood",
}

# Fields a claimant is never allowed to change through an edit request
BLOCKED_EDIT_FIELDS = {"status", "source", "distress", "claim", "listed_by", "slug", "has_pending_edit"}


def _summarise(value: Any) -> Any:
    """Compact a value for display in the admin diff view."""
    if isinstance(value, list):
        if value and isinstance(value[0], dict) and "url" in value[0]:
            return f"{len(value)} photo(s)"
        return f"{len(value)} item(s)" if len(value) > 3 else value
    if isinstance(value, str) and len(value) > 300:
        return value[:300] + "…"
    return value


def build_diff(original: dict, changes: dict) -> List[dict]:
    """
    Flatten a change payload into a list of {field, label, old, new} entries,
    dropping anything that is not actually different.
    """
    diff: List[dict] = []

    def walk(prefix: str, old_obj: dict, new_obj: dict):
        for key, new_val in new_obj.items():
            path = f"{prefix}{key}"
            old_val = (old_obj or {}).get(key)

            if isinstance(new_val, dict) and isinstance(old_val, dict) and key in ("details", "location"):
                walk(f"{path}.", old_val, new_val)
                continue

            if old_val == new_val:
                continue

            diff.append({
                "field": path,
                "label": FIELD_LABELS.get(path, path.replace("_", " ").replace(".", " › ").title()),
                "old": _summarise(old_val),
                "new": _summarise(new_val),
            })

    walk("", original, changes)
    return diff


def flatten_for_set(changes: dict) -> Dict[str, Any]:
    """
    Turn a nested change payload into dotted $set keys so approving an edit only
    touches the fields the user actually changed (rather than replacing whole
    sub-documents and wiping fields they never saw).
    """
    flat: Dict[str, Any] = {}
    for key, value in changes.items():
        if key in ("details", "location") and isinstance(value, dict):
            for sub_key, sub_val in value.items():
                if sub_key == "coordinates":
                    flat["location.coordinates"] = sub_val
                else:
                    flat[f"{key}.{sub_key}"] = sub_val
        else:
            flat[key] = value
    return flat


async def _property_card(prop: dict) -> dict:
    images = prop.get("images") or []
    image = None
    for img in images:
        if isinstance(img, dict) and img.get("url"):
            image = img["url"]
            if img.get("is_primary"):
                break
        elif isinstance(img, str):
            image = img
            break
    loc = prop.get("location") or {}
    address = ", ".join(
        p for p in [loc.get("address"), loc.get("city"), loc.get("state"), loc.get("zip_code")] if p
    )
    return {
        "property_title": prop.get("title"),
        "property_slug": prop.get("slug"),
        "property_image": image,
        "property_address": address or None,
    }


# ─── User: claims ───

@router.post("/{property_id}")
async def submit_claim(
    property_id: str,
    data: ClaimCreate,
    current_user: dict = Depends(get_current_user),
):
    """Submit a claim on an unclaimed property. Requires admin approval."""
    db = get_database()

    try:
        prop = await db.properties.find_one({"_id": ObjectId(property_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid property ID")
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Only imported/distressed listings are claimable. Without this guard a user
    # could file a claim on another member's genuine listing and, if an admin
    # approved it carelessly, take ownership of it.
    if not (prop.get("source") or (prop.get("distress") or {}).get("is_distressed")):
        raise HTTPException(status_code=400, detail="This property is not claimable")

    if str(prop.get("listed_by")) == str(current_user["_id"]):
        raise HTTPException(status_code=400, detail="You already own this property")

    claim_state = prop.get("claim") or {}
    status = claim_state.get("status", ClaimStatus.UNCLAIMED.value)

    if status == ClaimStatus.CLAIMED.value:
        if str(claim_state.get("claimed_by")) == str(current_user["_id"]):
            raise HTTPException(status_code=400, detail="You already own this property")
        raise HTTPException(status_code=400, detail="This property has already been claimed")

    existing = await db.property_claims.find_one({
        "property_id": property_id,
        "user_id": str(current_user["_id"]),
        "status": EditRequestStatus.PENDING.value,
    })
    if existing:
        raise HTTPException(status_code=400, detail="You already have a pending claim on this property")

    claim_doc = {
        "property_id": property_id,
        "user_id": str(current_user["_id"]),
        "status": EditRequestStatus.PENDING.value,
        "message": data.message,
        "proof_urls": data.proof_urls,
        "contact_phone": data.contact_phone or current_user.get("phone"),
        "rejection_reason": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": now_utc(),
    }
    result = await db.property_claims.insert_one(claim_doc)

    # Put the property "under review", but only if nobody else already holds it.
    # Competing claims are allowed — the admin picks the legitimate owner — and
    # the filter stops a later claimant from overwriting the first one's hold.
    await db.properties.update_one(
        {
            "_id": ObjectId(property_id),
            "$or": [
                {"claim.status": ClaimStatus.UNCLAIMED.value},
                {"claim.status": {"$exists": False}},
                {"claim": None},
            ],
        },
        {"$set": {
            "claim.status": ClaimStatus.PENDING.value,
            "claim.claimed_by": str(current_user["_id"]),
            "claim.claimed_at": now_utc(),
            "updated_at": now_utc(),
        }},
    )

    competing = await db.property_claims.count_documents({
        "property_id": property_id, "status": EditRequestStatus.PENDING.value,
    })

    return {
        "message": "Claim submitted. An admin will review it shortly."
                   + (" Note: other users have also claimed this property."
                      if competing > 1 else ""),
        "claim_id": str(result.inserted_id),
        "status": "pending",
        "competing_claims": competing,
        "success": True,
    }


@router.get("/my")
async def my_claims(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
):
    """List the current user's claim requests."""
    db = get_database()
    query: Dict[str, Any] = {"user_id": str(current_user["_id"])}
    if status_filter:
        query["status"] = status_filter

    total = await db.property_claims.count_documents(query)
    cursor = db.property_claims.find(query).sort("created_at", -1).skip((page - 1) * limit).limit(limit)

    claims = []
    async for claim in cursor:
        card = {}
        try:
            prop = await db.properties.find_one({"_id": ObjectId(claim["property_id"])})
            if prop:
                card = await _property_card(prop)
        except Exception:
            pass
        claims.append({
            "id": str(claim["_id"]),
            "property_id": claim["property_id"],
            "status": claim.get("status"),
            "message": claim.get("message"),
            "rejection_reason": claim.get("rejection_reason"),
            "reviewed_at": claim.get("reviewed_at"),
            "created_at": claim.get("created_at"),
            **card,
        })

    return {"claims": claims, "total": total, "page": page, "limit": limit,
            "total_pages": math.ceil(total / limit) if limit else 0}


@router.delete("/{claim_id}")
async def cancel_claim(claim_id: str, current_user: dict = Depends(get_current_user)):
    """Withdraw a still-pending claim."""
    db = get_database()
    try:
        claim = await db.property_claims.find_one({"_id": ObjectId(claim_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid claim ID")
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized")
    if claim.get("status") != EditRequestStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Only pending claims can be withdrawn")

    await db.property_claims.delete_one({"_id": ObjectId(claim_id)})
    # Release the hold only if this user is the one holding it — withdrawing a
    # competing claim must not free up someone else's pending claim.
    await db.properties.update_one(
        {"_id": ObjectId(claim["property_id"]),
         "claim.status": ClaimStatus.PENDING.value,
         "claim.claimed_by": claim["user_id"]},
        {"$set": {
            "claim.status": ClaimStatus.UNCLAIMED.value,
            "claim.claimed_by": None,
            "claim.claimed_at": None,
        }},
    )
    return {"message": "Claim withdrawn", "success": True}


# ─── User: edit requests ───

@edit_router.post("/{property_id}")
async def submit_edit_request(
    property_id: str,
    data: EditRequestCreate,
    current_user: dict = Depends(get_current_user),
):
    """Propose changes to a property you have claimed. Goes to the admin queue."""
    db = get_database()

    try:
        prop = await db.properties.find_one({"_id": ObjectId(property_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid property ID")
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    claim_state = prop.get("claim") or {}
    is_owner = (
        str(claim_state.get("claimed_by")) == str(current_user["_id"])
        and claim_state.get("status") == ClaimStatus.CLAIMED.value
    ) or str(prop.get("listed_by")) == str(current_user["_id"])

    if not is_owner:
        raise HTTPException(status_code=403, detail="You do not own this property")

    pending = await db.property_edit_requests.find_one({
        "property_id": property_id,
        "status": EditRequestStatus.PENDING.value,
    })
    if pending:
        raise HTTPException(
            status_code=400,
            detail="This property already has an edit awaiting admin approval",
        )

    changes = {k: v for k, v in (data.changes or {}).items() if k not in BLOCKED_EDIT_FIELDS}
    if not changes:
        raise HTTPException(status_code=400, detail="No editable changes provided")

    # Validate against the same schema a direct update would use
    try:
        PropertyUpdate(**changes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid changes: {exc}")

    diff = build_diff(prop, changes)
    if not diff:
        raise HTTPException(status_code=400, detail="Nothing changed")

    doc = {
        "property_id": property_id,
        "user_id": str(current_user["_id"]),
        "status": EditRequestStatus.PENDING.value,
        "changes": changes,
        "diff": diff,
        "note": data.note,
        "rejection_reason": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": now_utc(),
    }
    result = await db.property_edit_requests.insert_one(doc)

    await db.properties.update_one(
        {"_id": ObjectId(property_id)},
        {"$set": {"has_pending_edit": True, "updated_at": now_utc()}},
    )

    return {
        "message": "Changes submitted for admin approval.",
        "edit_request_id": str(result.inserted_id),
        "changed_fields": len(diff),
        "status": "pending",
        "success": True,
    }


@edit_router.get("/my")
async def my_edit_requests(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
):
    """List the current user's edit requests."""
    db = get_database()
    query: Dict[str, Any] = {"user_id": str(current_user["_id"])}
    if status_filter:
        query["status"] = status_filter

    total = await db.property_edit_requests.count_documents(query)
    cursor = db.property_edit_requests.find(query).sort("created_at", -1).skip((page - 1) * limit).limit(limit)

    requests = []
    async for req in cursor:
        card = {}
        try:
            prop = await db.properties.find_one({"_id": ObjectId(req["property_id"])})
            if prop:
                card = await _property_card(prop)
        except Exception:
            pass
        requests.append({
            "id": str(req["_id"]),
            "property_id": req["property_id"],
            "status": req.get("status"),
            "diff": req.get("diff", []),
            "note": req.get("note"),
            "rejection_reason": req.get("rejection_reason"),
            "reviewed_at": req.get("reviewed_at"),
            "created_at": req.get("created_at"),
            **card,
        })

    return {"edit_requests": requests, "total": total, "page": page, "limit": limit,
            "total_pages": math.ceil(total / limit) if limit else 0}


@edit_router.delete("/{request_id}")
async def cancel_edit_request(request_id: str, current_user: dict = Depends(get_current_user)):
    """Withdraw a pending edit request."""
    db = get_database()
    try:
        req = await db.property_edit_requests.find_one({"_id": ObjectId(request_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request ID")
    if not req:
        raise HTTPException(status_code=404, detail="Edit request not found")
    if req["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized")
    if req.get("status") != EditRequestStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Only pending requests can be withdrawn")

    await db.property_edit_requests.delete_one({"_id": ObjectId(request_id)})
    await db.properties.update_one(
        {"_id": ObjectId(req["property_id"])},
        {"$set": {"has_pending_edit": False}},
    )
    return {"message": "Edit request withdrawn", "success": True}
