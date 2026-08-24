"""
PropertyKING — Admin: Distressed Sync, Claims & Edit Approvals

Everything the admin panel needs to run the show:
  * configure and trigger the external distressed-property sync
  * review the run history
  * approve/reject property claims
  * approve/reject the edits claimants submit
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from bson import ObjectId
from typing import Optional, Dict, Any
import math

from app.database import get_database
from app.middleware.auth import require_admin
from app.models.sync import (
    SyncSettingsUpdate, SyncTrigger, ClaimStatus, EditRequestStatus,
    ClaimReject, EditRequestReject, DISTRESS_LABELS,
)
from app.services.property_sync import (
    get_sync_settings_doc, save_sync_settings, run_sync, sync_overview,
)
from app.services.providers import list_providers
from app.routes.claims import flatten_for_set, _property_card
from app.services.push_notification import send_push_notification
from app.utils.helpers import now_utc

router = APIRouter(prefix="/admin", tags=["Admin — Distressed Sync"])


# ─── Sync configuration ───

@router.get("/sync/overview")
async def sync_overview_endpoint(admin: dict = Depends(require_admin)):
    """Headline numbers for the sync dashboard."""
    return await sync_overview()


@router.get("/sync/providers")
async def sync_providers(admin: dict = Depends(require_admin)):
    """Available data sources and whether each one is configured."""
    return {"providers": list_providers()}


@router.get("/sync/settings")
async def read_sync_settings(admin: dict = Depends(require_admin)):
    """Current sync configuration."""
    doc = await get_sync_settings_doc()
    doc.pop("_id", None)
    doc["available_providers"] = list_providers()
    doc["distress_labels"] = {k.value: v for k, v in DISTRESS_LABELS.items()}
    return doc


@router.put("/sync/settings")
async def update_sync_settings(
    data: SyncSettingsUpdate,
    admin: dict = Depends(require_admin),
):
    """
    Update the sync configuration. Changing `interval_days` recomputes the next
    run immediately — no restart needed.
    """
    changes = data.model_dump(exclude_none=True, mode="json")
    if not changes:
        raise HTTPException(status_code=400, detail="No settings provided")

    doc = await save_sync_settings(changes, admin_id=str(admin["_id"]))
    doc.pop("_id", None)
    doc["available_providers"] = list_providers()

    return {"message": "Sync settings updated", "settings": doc, "success": True}


@router.post("/sync/run")
async def trigger_sync(
    background: BackgroundTasks,
    wait: bool = Query(False, description="Run inline and return the full result"),
    admin: dict = Depends(require_admin),
):
    """Run the sync right now, without waiting for the schedule."""
    if wait:
        result = await run_sync(trigger=SyncTrigger.MANUAL.value, triggered_by=str(admin["_id"]))
        return {"message": "Sync finished", "run": result, "success": True}

    background.add_task(run_sync, SyncTrigger.MANUAL.value, str(admin["_id"]))
    return {
        "message": "Sync started in the background. Refresh the run history in a moment.",
        "success": True,
    }


@router.get("/sync/runs")
async def list_sync_runs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    """Run history with per-run counts and errors."""
    db = get_database()
    total = await db.sync_runs.count_documents({})
    cursor = db.sync_runs.find({}).sort("started_at", -1).skip((page - 1) * limit).limit(limit)

    runs = []
    async for run in cursor:
        runs.append({
            "id": str(run.pop("_id")),
            **run,
        })

    return {"runs": runs, "total": total, "page": page, "limit": limit,
            "total_pages": math.ceil(total / limit) if limit else 0}


@router.get("/distressed")
async def list_distressed_properties(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    distress_type: Optional[str] = None,
    claim_status: Optional[str] = None,
    provider: Optional[str] = None,
    state: Optional[str] = None,
    search: Optional[str] = None,
    admin: dict = Depends(require_admin),
):
    """Imported distressed properties, filterable by distress and claim state."""
    db = get_database()
    query: Dict[str, Any] = {"distress.is_distressed": True}
    if distress_type:
        query["distress.type"] = distress_type
    if claim_status:
        query["claim.status"] = claim_status
    if provider:
        query["source.provider"] = provider
    if state:
        query["location.state"] = state.upper()
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"location.city": {"$regex": search, "$options": "i"}},
            {"location.address": {"$regex": search, "$options": "i"}},
            {"source.external_id": {"$regex": search, "$options": "i"}},
        ]

    total = await db.properties.count_documents(query)
    cursor = db.properties.find(query).sort("created_at", -1).skip((page - 1) * limit).limit(limit)

    properties = []
    async for prop in cursor:
        card = await _property_card(prop)
        claim = prop.get("claim") or {}
        owner = None
        if claim.get("claimed_by"):
            try:
                user = await db.users.find_one(
                    {"_id": ObjectId(claim["claimed_by"])}, {"full_name": 1, "email": 1}
                )
                if user:
                    owner = {"id": str(user["_id"]), "name": user.get("full_name"), "email": user.get("email")}
            except Exception:
                pass

        properties.append({
            "id": str(prop["_id"]),
            "title": prop.get("title"),
            "slug": prop.get("slug"),
            "status": prop.get("status"),
            "price": prop.get("price"),
            "image": card.get("property_image"),
            "address": card.get("property_address"),
            "city": (prop.get("location") or {}).get("city"),
            "state": (prop.get("location") or {}).get("state"),
            "distress": prop.get("distress"),
            "source": prop.get("source"),
            "claim": claim,
            "owner": owner,
            "has_pending_edit": prop.get("has_pending_edit", False),
            "views": prop.get("views_count", 0),
            "created_at": prop.get("created_at"),
            "updated_at": prop.get("updated_at"),
        })

    return {"properties": properties, "total": total, "page": page, "limit": limit,
            "total_pages": math.ceil(total / limit) if limit else 0}


# ─── Claim review ───

async def _hydrate_claim(db, claim: dict) -> dict:
    card: Dict[str, Any] = {}
    try:
        prop = await db.properties.find_one({"_id": ObjectId(claim["property_id"])})
        if prop:
            card = await _property_card(prop)
            card["distress_type"] = (prop.get("distress") or {}).get("type")
            card["property_price"] = prop.get("price")
    except Exception:
        pass

    user = None
    try:
        user = await db.users.find_one(
            {"_id": ObjectId(claim["user_id"])},
            {"full_name": 1, "email": 1, "phone": 1, "avatar": 1, "created_at": 1},
        )
    except Exception:
        pass

    return {
        "id": str(claim["_id"]),
        "property_id": claim["property_id"],
        "user_id": claim["user_id"],
        "user_name": user.get("full_name") if user else None,
        "user_email": user.get("email") if user else None,
        "user_phone": claim.get("contact_phone") or (user.get("phone") if user else None),
        "user_avatar": user.get("avatar") if user else None,
        "user_since": user.get("created_at") if user else None,
        "status": claim.get("status"),
        "message": claim.get("message"),
        "proof_urls": claim.get("proof_urls", []),
        "rejection_reason": claim.get("rejection_reason"),
        "reviewed_by": claim.get("reviewed_by"),
        "reviewed_at": claim.get("reviewed_at"),
        "created_at": claim.get("created_at"),
        **card,
    }


@router.get("/claims")
async def admin_list_claims(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    admin: dict = Depends(require_admin),
):
    """Claim requests awaiting (or past) review."""
    db = get_database()
    query: Dict[str, Any] = {}
    if status_filter:
        query["status"] = status_filter

    if search:
        # Match on the claimant's name/email by resolving user ids first
        user_ids = [
            str(u["_id"]) async for u in db.users.find(
                {"$or": [
                    {"full_name": {"$regex": search, "$options": "i"}},
                    {"email": {"$regex": search, "$options": "i"}},
                ]},
                {"_id": 1},
            )
        ]
        query["user_id"] = {"$in": user_ids}

    total = await db.property_claims.count_documents(query)
    cursor = db.property_claims.find(query).sort("created_at", -1).skip((page - 1) * limit).limit(limit)

    claims = [await _hydrate_claim(db, claim) async for claim in cursor]
    pending = await db.property_claims.count_documents({"status": EditRequestStatus.PENDING.value})

    return {"claims": claims, "total": total, "pending": pending, "page": page,
            "limit": limit, "total_pages": math.ceil(total / limit) if limit else 0}


@router.put("/claims/{claim_id}/approve")
async def approve_claim(claim_id: str, admin: dict = Depends(require_admin)):
    """
    Approve a claim: the property moves into the claimant's account. They become
    the lister of record, and their future edits go through the approval queue.
    """
    db = get_database()
    try:
        claim = await db.property_claims.find_one({"_id": ObjectId(claim_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid claim ID")
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.get("status") != EditRequestStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="This claim has already been reviewed")

    prop = await db.properties.find_one({"_id": ObjectId(claim["property_id"])})
    if not prop:
        raise HTTPException(status_code=404, detail="Property no longer exists")
    if (prop.get("claim") or {}).get("status") == ClaimStatus.CLAIMED.value:
        raise HTTPException(status_code=400, detail="Property was already claimed by someone else")

    user = await db.users.find_one({"_id": ObjectId(claim["user_id"])})
    if not user:
        raise HTTPException(status_code=404, detail="Claimant account no longer exists")

    await db.properties.update_one(
        {"_id": ObjectId(claim["property_id"])},
        {"$set": {
            "listed_by": claim["user_id"],
            "contact_phone": claim.get("contact_phone") or user.get("phone") or prop.get("contact_phone"),
            "contact_email": user.get("email") or prop.get("contact_email"),
            "claim": {
                "status": ClaimStatus.CLAIMED.value,
                "claimed_by": claim["user_id"],
                "claimed_at": claim.get("created_at") or now_utc(),
                "approved_by": str(admin["_id"]),
                "approved_at": now_utc(),
            },
            "updated_at": now_utc(),
        }},
    )

    await db.property_claims.update_one(
        {"_id": ObjectId(claim_id)},
        {"$set": {
            "status": EditRequestStatus.APPROVED.value,
            "reviewed_by": str(admin["_id"]),
            "reviewed_at": now_utc(),
        }},
    )

    # Any other pending claims on the same property lose out
    await db.property_claims.update_many(
        {"property_id": claim["property_id"], "status": EditRequestStatus.PENDING.value,
         "_id": {"$ne": ObjectId(claim_id)}},
        {"$set": {
            "status": EditRequestStatus.REJECTED.value,
            "rejection_reason": "Another claim on this property was approved first",
            "reviewed_by": str(admin["_id"]),
            "reviewed_at": now_utc(),
        }},
    )

    await send_push_notification(
        claim["user_id"],
        "Claim Approved! 🎉",
        f"'{prop.get('title', 'Your property')}' is now in your account. You can manage it from My Listings.",
        "claim_approved",
        {"property_id": claim["property_id"]},
    )

    return {"message": "Claim approved — property transferred to the user", "success": True}


@router.put("/claims/{claim_id}/reject")
async def reject_claim(claim_id: str, data: ClaimReject, admin: dict = Depends(require_admin)):
    """Reject a claim and release the property back to unclaimed."""
    db = get_database()
    try:
        claim = await db.property_claims.find_one({"_id": ObjectId(claim_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid claim ID")
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.get("status") != EditRequestStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="This claim has already been reviewed")

    await db.property_claims.update_one(
        {"_id": ObjectId(claim_id)},
        {"$set": {
            "status": EditRequestStatus.REJECTED.value,
            "rejection_reason": data.reason,
            "reviewed_by": str(admin["_id"]),
            "reviewed_at": now_utc(),
        }},
    )

    # Release the hold only if this claimant is the one holding it
    await db.properties.update_one(
        {"_id": ObjectId(claim["property_id"]),
         "claim.status": ClaimStatus.PENDING.value,
         "claim.claimed_by": claim["user_id"]},
        {"$set": {
            "claim.status": ClaimStatus.UNCLAIMED.value,
            "claim.claimed_by": None,
            "claim.claimed_at": None,
            "updated_at": now_utc(),
        }},
    )

    prop = await db.properties.find_one({"_id": ObjectId(claim["property_id"])}, {"title": 1})
    await send_push_notification(
        claim["user_id"],
        "Claim Not Approved",
        f"Your claim on '{(prop or {}).get('title', 'a property')}' was declined: {data.reason}",
        "claim_rejected",
        {"property_id": claim["property_id"]},
    )

    return {"message": "Claim rejected", "success": True}


# ─── Edit request review ───

async def _hydrate_edit_request(db, req: dict) -> dict:
    card: Dict[str, Any] = {}
    try:
        prop = await db.properties.find_one({"_id": ObjectId(req["property_id"])})
        if prop:
            card = await _property_card(prop)
    except Exception:
        pass

    user = None
    try:
        user = await db.users.find_one(
            {"_id": ObjectId(req["user_id"])}, {"full_name": 1, "email": 1, "avatar": 1}
        )
    except Exception:
        pass

    return {
        "id": str(req["_id"]),
        "property_id": req["property_id"],
        "user_id": req["user_id"],
        "user_name": user.get("full_name") if user else None,
        "user_email": user.get("email") if user else None,
        "user_avatar": user.get("avatar") if user else None,
        "status": req.get("status"),
        "diff": req.get("diff", []),
        "changes": req.get("changes", {}),
        "note": req.get("note"),
        "rejection_reason": req.get("rejection_reason"),
        "reviewed_by": req.get("reviewed_by"),
        "reviewed_at": req.get("reviewed_at"),
        "created_at": req.get("created_at"),
        **card,
    }


@router.get("/edit-requests")
async def admin_list_edit_requests(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    admin: dict = Depends(require_admin),
):
    """Property edits submitted by owners, awaiting approval."""
    db = get_database()
    query: Dict[str, Any] = {}
    if status_filter:
        query["status"] = status_filter

    total = await db.property_edit_requests.count_documents(query)
    cursor = db.property_edit_requests.find(query).sort("created_at", -1).skip((page - 1) * limit).limit(limit)

    requests = [await _hydrate_edit_request(db, req) async for req in cursor]
    pending = await db.property_edit_requests.count_documents({"status": EditRequestStatus.PENDING.value})

    return {"edit_requests": requests, "total": total, "pending": pending, "page": page,
            "limit": limit, "total_pages": math.ceil(total / limit) if limit else 0}


@router.put("/edit-requests/{request_id}/approve")
async def approve_edit_request(request_id: str, admin: dict = Depends(require_admin)):
    """Apply an approved edit to the live property."""
    db = get_database()
    try:
        req = await db.property_edit_requests.find_one({"_id": ObjectId(request_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request ID")
    if not req:
        raise HTTPException(status_code=404, detail="Edit request not found")
    if req.get("status") != EditRequestStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="This request has already been reviewed")

    prop = await db.properties.find_one({"_id": ObjectId(req["property_id"])})
    if not prop:
        raise HTTPException(status_code=404, detail="Property no longer exists")

    update = flatten_for_set(req.get("changes", {}))
    update["updated_at"] = now_utc()
    update["has_pending_edit"] = False

    await db.properties.update_one({"_id": ObjectId(req["property_id"])}, {"$set": update})

    await db.property_edit_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {
            "status": EditRequestStatus.APPROVED.value,
            "reviewed_by": str(admin["_id"]),
            "reviewed_at": now_utc(),
        }},
    )

    await send_push_notification(
        req["user_id"],
        "Changes Approved ✅",
        f"Your updates to '{prop.get('title', 'your property')}' are now live.",
        "edit_approved",
        {"property_id": req["property_id"]},
    )

    return {"message": "Changes approved and applied", "fields_updated": len(req.get("diff", [])), "success": True}


@router.put("/edit-requests/{request_id}/reject")
async def reject_edit_request(
    request_id: str, data: EditRequestReject, admin: dict = Depends(require_admin)
):
    """Reject a proposed edit; the live listing is left untouched."""
    db = get_database()
    try:
        req = await db.property_edit_requests.find_one({"_id": ObjectId(request_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request ID")
    if not req:
        raise HTTPException(status_code=404, detail="Edit request not found")
    if req.get("status") != EditRequestStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="This request has already been reviewed")

    await db.property_edit_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {
            "status": EditRequestStatus.REJECTED.value,
            "rejection_reason": data.reason,
            "reviewed_by": str(admin["_id"]),
            "reviewed_at": now_utc(),
        }},
    )
    await db.properties.update_one(
        {"_id": ObjectId(req["property_id"])}, {"$set": {"has_pending_edit": False}}
    )

    prop = await db.properties.find_one({"_id": ObjectId(req["property_id"])}, {"title": 1})
    await send_push_notification(
        req["user_id"],
        "Changes Not Approved",
        f"Your updates to '{(prop or {}).get('title', 'your property')}' were declined: {data.reason}",
        "edit_rejected",
        {"property_id": req["property_id"]},
    )

    return {"message": "Edit request rejected", "success": True}
