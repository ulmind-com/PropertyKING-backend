"""
PropertyKING — Amenities Routes (Admin CRUD + Public listing)
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
from slugify import slugify
from typing import Optional

from app.database import get_database
from app.middleware.auth import require_admin
from app.models.amenity import AmenityCreate, AmenityUpdate, AmenityResponse
from app.utils.helpers import now_utc

router = APIRouter(prefix="/amenities", tags=["Amenities"])


@router.get("", response_model=list[AmenityResponse])
async def list_amenities(category: Optional[str] = None, include_inactive: bool = False):
    """Get all active amenities (public)."""
    db = get_database()
    query = {} if include_inactive else {"is_active": True}
    if category:
        query["category"] = category

    cursor = db.amenities.find(query).sort("order", 1)
    result = []
    async for amenity in cursor:
        result.append(AmenityResponse(
            id=str(amenity["_id"]), name=amenity["name"], slug=amenity["slug"],
            icon=amenity.get("icon", "✅"), category=amenity.get("category", "indoor"),
            is_active=amenity.get("is_active", True), order=amenity.get("order", 0),
            created_at=amenity.get("created_at")))
    return result


@router.post("", response_model=AmenityResponse, status_code=201)
async def create_amenity(data: AmenityCreate, admin: dict = Depends(require_admin)):
    """Create a new amenity (admin only)."""
    db = get_database()
    slug = slugify(data.name)
    existing = await db.amenities.find_one({"slug": slug})
    if existing:
        raise HTTPException(status_code=409, detail="Amenity already exists")

    doc = {**data.model_dump(), "slug": slug, "created_at": now_utc(), "updated_at": now_utc()}
    result = await db.amenities.insert_one(doc)

    return AmenityResponse(id=str(result.inserted_id), name=data.name, slug=slug,
        icon=data.icon or "✅", category=data.category, is_active=data.is_active,
        order=data.order, created_at=doc["created_at"])


@router.put("/{amenity_id}", response_model=AmenityResponse)
async def update_amenity(amenity_id: str, data: AmenityUpdate, admin: dict = Depends(require_admin)):
    """Update an amenity (admin only)."""
    db = get_database()
    try:
        existing = await db.amenities.find_one({"_id": ObjectId(amenity_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
    if not existing:
        raise HTTPException(status_code=404, detail="Amenity not found")

    update = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if "name" in update:
        update["slug"] = slugify(update["name"])
    update["updated_at"] = now_utc()

    await db.amenities.update_one({"_id": ObjectId(amenity_id)}, {"$set": update})
    updated = await db.amenities.find_one({"_id": ObjectId(amenity_id)})

    return AmenityResponse(
        id=str(updated["_id"]), name=updated["name"], slug=updated["slug"],
        icon=updated.get("icon", "✅"), category=updated.get("category", "indoor"),
        is_active=updated.get("is_active", True), order=updated.get("order", 0),
        created_at=updated.get("created_at"))


@router.delete("/{amenity_id}")
async def delete_amenity(amenity_id: str, admin: dict = Depends(require_admin)):
    """Delete an amenity (admin only)."""
    db = get_database()
    result = await db.amenities.delete_one({"_id": ObjectId(amenity_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Amenity not found")
    return {"message": "Amenity deleted", "success": True}
