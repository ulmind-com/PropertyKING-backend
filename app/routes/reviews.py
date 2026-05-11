"""
PropertyKING — Review Routes
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
import math

from app.database import get_database
from app.middleware.auth import get_current_user
from app.models.review import ReviewCreate, ReviewResponse
from app.utils.helpers import now_utc

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get("/property/{property_id}")
async def get_property_reviews(property_id: str, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=50)):
    """Get reviews for a property."""
    db = get_database()
    query = {"property_id": property_id, "is_approved": True}
    total = await db.reviews.count_documents(query)
    skip = (page - 1) * limit

    cursor = db.reviews.find(query).sort("created_at", -1).skip(skip).limit(limit)
    reviews = []
    async for rev in cursor:
        user = await db.users.find_one({"_id": ObjectId(rev["user_id"])}) if rev.get("user_id") else None
        reviews.append(ReviewResponse(
            id=str(rev["_id"]), property_id=rev.get("property_id", ""),
            user_id=rev.get("user_id", ""),
            user_name=user.get("full_name") if user else None,
            user_avatar=user.get("avatar") if user else None,
            rating=rev.get("rating", 0), comment=rev.get("comment", ""),
            is_approved=True, created_at=rev.get("created_at")))

    pipeline = [{"$match": query}, {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}}]
    stats = await db.reviews.aggregate(pipeline).to_list(1)
    avg_rating = round(stats[0]["avg"], 1) if stats else 0

    return {"reviews": reviews, "total": total, "page": page, "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0, "average_rating": avg_rating}


@router.post("", response_model=ReviewResponse, status_code=201)
async def create_review(data: ReviewCreate, current_user: dict = Depends(get_current_user)):
    """Submit a review."""
    db = get_database()
    try:
        prop = await db.properties.find_one({"_id": ObjectId(data.property_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid property ID")
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    existing = await db.reviews.find_one({"property_id": data.property_id, "user_id": current_user["_id"]})
    if existing:
        raise HTTPException(status_code=409, detail="Already reviewed")

    doc = {"property_id": data.property_id, "user_id": current_user["_id"], "rating": data.rating,
           "comment": data.comment, "is_approved": True, "created_at": now_utc()}
    result = await db.reviews.insert_one(doc)

    return ReviewResponse(id=str(result.inserted_id), property_id=data.property_id,
        user_id=current_user["_id"], user_name=current_user.get("full_name"),
        rating=data.rating, comment=data.comment, is_approved=True, created_at=doc["created_at"])
