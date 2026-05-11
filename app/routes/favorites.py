"""
PropertyKING — Favorites Routes
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
import math

from app.database import get_database
from app.middleware.auth import get_current_user
from app.utils.helpers import now_utc

router = APIRouter(prefix="/favorites", tags=["Favorites"])


@router.get("")
async def get_favorites(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get user's favorite properties."""
    db = get_database()
    query = {"user_id": current_user["_id"]}

    total = await db.favorites.count_documents(query)
    skip = (page - 1) * limit

    cursor = db.favorites.find(query).sort("created_at", -1).skip(skip).limit(limit)
    favorites = []

    async for fav in cursor:
        try:
            prop = await db.properties.find_one({"_id": ObjectId(fav["property_id"])})
            if prop:
                primary_image = None
                for img in prop.get("images", []):
                    if img.get("is_primary"):
                        primary_image = img["url"]
                        break
                if not primary_image and prop.get("images"):
                    primary_image = prop["images"][0].get("url")

                favorites.append({
                    "id": str(fav["_id"]),
                    "property_id": fav["property_id"],
                    "property_title": prop.get("title", ""),
                    "property_slug": prop.get("slug", ""),
                    "property_image": primary_image,
                    "property_price": prop.get("price", 0),
                    "property_location": f"{prop.get('location', {}).get('city', '')}, {prop.get('location', {}).get('state', '')}",
                    "property_bedrooms": prop.get("details", {}).get("bedrooms", 0),
                    "property_bathrooms": prop.get("details", {}).get("bathrooms", 0),
                    "property_sqft": prop.get("details", {}).get("total_sqft"),
                    "property_status": prop.get("status", ""),
                    "created_at": fav.get("created_at")
                })
        except Exception:
            continue

    return {
        "favorites": favorites, "total": total, "page": page, "limit": limit,
        "total_pages": math.ceil(total / limit) if limit > 0 else 0
    }


@router.post("/{property_id}")
async def add_to_favorites(property_id: str, current_user: dict = Depends(get_current_user)):
    """Add a property to favorites."""
    db = get_database()

    try:
        prop = await db.properties.find_one({"_id": ObjectId(property_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid property ID")
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    existing = await db.favorites.find_one({"user_id": current_user["_id"], "property_id": property_id})
    if existing:
        raise HTTPException(status_code=409, detail="Already in favorites")

    await db.favorites.insert_one({
        "user_id": current_user["_id"],
        "property_id": property_id,
        "created_at": now_utc()
    })

    await db.properties.update_one({"_id": ObjectId(property_id)}, {"$inc": {"favorites_count": 1}})
    return {"message": "Added to favorites", "success": True}


@router.delete("/{property_id}")
async def remove_from_favorites(property_id: str, current_user: dict = Depends(get_current_user)):
    """Remove a property from favorites."""
    db = get_database()

    result = await db.favorites.delete_one({"user_id": current_user["_id"], "property_id": property_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not in favorites")

    await db.properties.update_one({"_id": ObjectId(property_id)}, {"$inc": {"favorites_count": -1}})
    return {"message": "Removed from favorites", "success": True}
