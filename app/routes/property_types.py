"""
PropertyKING — Property Types Routes (Admin CRUD + Public listing)
"""

from fastapi import APIRouter, HTTPException, status, Depends
from bson import ObjectId
from slugify import slugify

from app.database import get_database
from app.middleware.auth import require_admin
from app.models.property_type import PropertyTypeCreate, PropertyTypeUpdate, PropertyTypeResponse
from app.utils.helpers import now_utc

router = APIRouter(prefix="/property-types", tags=["Property Types"])


@router.get("", response_model=list[PropertyTypeResponse])
async def list_property_types(include_inactive: bool = False):
    """Get all active property types (public)."""
    db = get_database()
    query = {} if include_inactive else {"is_active": True}
    cursor = db.property_types.find(query).sort("order", 1)

    result = []
    async for pt in cursor:
        count = await db.properties.count_documents({"property_type_id": str(pt["_id"]), "status": "active"})
        result.append(PropertyTypeResponse(
            id=str(pt["_id"]), name=pt["name"], slug=pt["slug"],
            icon=pt.get("icon", "🏠"), icon_url=pt.get("icon_url"),
            description=pt.get("description"), is_active=pt.get("is_active", True),
            order=pt.get("order", 0), properties_count=count,
            created_at=pt.get("created_at")
        ))
    return result


@router.post("", response_model=PropertyTypeResponse, status_code=201)
async def create_property_type(data: PropertyTypeCreate, admin: dict = Depends(require_admin)):
    """Create a new property type (admin only)."""
    db = get_database()
    slug = slugify(data.name)

    existing = await db.property_types.find_one({"slug": slug})
    if existing:
        raise HTTPException(status_code=409, detail="Property type already exists")

    doc = {**data.model_dump(), "slug": slug, "created_at": now_utc(), "updated_at": now_utc()}
    result = await db.property_types.insert_one(doc)

    return PropertyTypeResponse(id=str(result.inserted_id), name=data.name, slug=slug,
        icon=data.icon or "🏠", description=data.description, is_active=data.is_active,
        order=data.order, created_at=doc["created_at"])


@router.put("/{type_id}", response_model=PropertyTypeResponse)
async def update_property_type(type_id: str, data: PropertyTypeUpdate, admin: dict = Depends(require_admin)):
    """Update a property type (admin only)."""
    db = get_database()

    try:
        existing = await db.property_types.find_one({"_id": ObjectId(type_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")

    if not existing:
        raise HTTPException(status_code=404, detail="Property type not found")

    update = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if "name" in update:
        update["slug"] = slugify(update["name"])
    update["updated_at"] = now_utc()

    await db.property_types.update_one({"_id": ObjectId(type_id)}, {"$set": update})
    updated = await db.property_types.find_one({"_id": ObjectId(type_id)})

    count = await db.properties.count_documents({"property_type_id": type_id, "status": "active"})
    return PropertyTypeResponse(
        id=str(updated["_id"]), name=updated["name"], slug=updated["slug"],
        icon=updated.get("icon", "🏠"), icon_url=updated.get("icon_url"),
        description=updated.get("description"), is_active=updated.get("is_active", True),
        order=updated.get("order", 0), properties_count=count, created_at=updated.get("created_at"))


@router.delete("/{type_id}")
async def delete_property_type(type_id: str, admin: dict = Depends(require_admin)):
    """Delete a property type (admin only)."""
    db = get_database()
    count = await db.properties.count_documents({"property_type_id": type_id})
    if count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete: {count} properties use this type")

    result = await db.property_types.delete_one({"_id": ObjectId(type_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Property type not found")

    return {"message": "Property type deleted", "success": True}
