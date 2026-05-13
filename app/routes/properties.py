"""
PropertyKING — Property Routes
CRUD, search, filtering, geo-based queries, recommendations.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from bson import ObjectId
from typing import Optional, List
import math

from app.database import get_database
from app.middleware.auth import get_current_user, get_current_user_optional, require_lister
from app.models.property import (
    PropertyCreate, PropertyUpdate, PropertyResponse,
    PropertyListResponse, PropertyStatus
)
from app.utils.helpers import now_utc, generate_unique_slug, miles_to_meters
from app.services.geocoding import geocode_address

router = APIRouter(prefix="/properties", tags=["Properties"])


async def enrich_property(prop: dict, current_user_id: str = None) -> dict:
    """Enrich a property document with type name, lister info, favorite status."""
    db = get_database()

    # Property type name
    if prop.get("property_type_id"):
        try:
            pt = await db.property_types.find_one({"_id": ObjectId(prop["property_type_id"])})
            prop["property_type_name"] = pt["name"] if pt else None
        except Exception:
            prop["property_type_name"] = None

    # Amenity names
    if prop.get("amenities"):
        amenity_ids = []
        for aid in prop["amenities"]:
            try:
                amenity_ids.append(ObjectId(aid))
            except Exception:
                pass
        if amenity_ids:
            cursor = db.amenities.find({"_id": {"$in": amenity_ids}})
            prop["amenity_names"] = [a["name"] async for a in cursor]
        else:
            prop["amenity_names"] = []

    # Lister info
    if prop.get("listed_by"):
        try:
            lister = await db.users.find_one({"_id": ObjectId(prop["listed_by"])})
            if lister:
                prop["lister_name"] = lister.get("full_name")
                prop["lister_avatar"] = lister.get("avatar")
                prop["lister_type"] = lister.get("lister_type")
        except Exception:
            pass

    # Favorite status
    prop["is_favorited"] = False
    if current_user_id:
        fav = await db.favorites.find_one({
            "user_id": current_user_id,
            "property_id": str(prop["_id"])
        })
        prop["is_favorited"] = fav is not None

    return prop


def build_property_response(prop: dict) -> PropertyResponse:
    """Build PropertyResponse from enriched DB doc."""
    return PropertyResponse(
        id=str(prop["_id"]),
        title=prop.get("title", ""),
        slug=prop.get("slug", ""),
        description=prop.get("description", ""),
        property_type_id=prop.get("property_type_id", ""),
        property_type_name=prop.get("property_type_name"),
        listing_type=prop.get("listing_type", "sale"),
        status=prop.get("status", "pending"),
        price=prop.get("price", 0),
        price_unit=prop.get("price_unit", "total"),
        currency=prop.get("currency", "USD"),
        details=prop.get("details", {}),
        amenities=prop.get("amenities", []),
        amenity_names=prop.get("amenity_names", []),
        location=prop.get("location", {}),
        images=prop.get("images", []),
        video_url=prop.get("video_url"),
        floor_plan_url=prop.get("floor_plan_url"),
        floor_plan_urls=prop.get("floor_plan_urls", []),
        listed_by=prop.get("listed_by", ""),
        lister_name=prop.get("lister_name"),
        lister_avatar=prop.get("lister_avatar"),
        lister_type=prop.get("lister_type"),
        contact_phone=prop.get("contact_phone"),
        contact_email=prop.get("contact_email"),
        admin_review=prop.get("admin_review"),
        views_count=prop.get("views_count", 0),
        favorites_count=prop.get("favorites_count", 0),
        inquiries_count=prop.get("inquiries_count", 0),
        is_favorited=prop.get("is_favorited", False),
        listed_at=prop.get("listed_at"),
        created_at=prop.get("created_at"),
        updated_at=prop.get("updated_at")
    )


@router.get("", response_model=PropertyListResponse)
async def list_properties(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    property_type_id: Optional[str] = None,
    listing_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms_min: Optional[int] = None,
    bathrooms_min: Optional[float] = None,
    min_sqft: Optional[int] = None,
    max_sqft: Optional[int] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """List active properties with filters, search, and pagination."""
    db = get_database()
    query = {"status": "active"}

    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"location.city": {"$regex": search, "$options": "i"}},
            {"location.neighborhood": {"$regex": search, "$options": "i"}}
        ]
    if property_type_id:
        query["property_type_id"] = property_type_id
    if listing_type:
        query["listing_type"] = listing_type
    if min_price is not None:
        query["price"] = query.get("price", {})
        query["price"]["$gte"] = min_price
    if max_price is not None:
        query["price"] = query.get("price", {})
        query["price"]["$lte"] = max_price
    if bedrooms_min is not None:
        query["details.bedrooms"] = {"$gte": bedrooms_min}
    if bathrooms_min is not None:
        query["details.bathrooms"] = {"$gte": bathrooms_min}
    if min_sqft is not None:
        query["details.total_sqft"] = query.get("details.total_sqft", {})
        query["details.total_sqft"]["$gte"] = min_sqft
    if max_sqft is not None:
        query["details.total_sqft"] = query.get("details.total_sqft", {})
        query["details.total_sqft"]["$lte"] = max_sqft
    if city:
        query["location.city"] = {"$regex": city, "$options": "i"}
    if state:
        query["location.state"] = state.upper()
    if zip_code:
        query["location.zip_code"] = zip_code

    sort_field = sort_by if sort_by in ["price", "created_at", "details.total_sqft", "views_count"] else "created_at"
    sort_dir = -1 if sort_order == "desc" else 1

    total = await db.properties.count_documents(query)
    skip = (page - 1) * limit

    cursor = db.properties.find(query).sort(sort_field, sort_dir).skip(skip).limit(limit)
    properties = []
    current_user_id = current_user["_id"] if current_user else None

    async for prop in cursor:
        prop = await enrich_property(prop, current_user_id)
        properties.append(build_property_response(prop))

    return PropertyListResponse(
        properties=properties,
        total=total,
        page=page,
        limit=limit,
        total_pages=math.ceil(total / limit) if limit > 0 else 0
    )


@router.get("/nearby", response_model=PropertyListResponse)
async def nearby_properties(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_miles: float = Query(25, ge=0.1, le=100),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    property_type_id: Optional[str] = None,
    listing_type: Optional[str] = None,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Get properties near a location."""
    db = get_database()

    query = {
        "status": "active",
        "location.coordinates": {
            "$nearSphere": {
                "$geometry": {"type": "Point", "coordinates": [lng, lat]},
                "$maxDistance": miles_to_meters(radius_miles)
            }
        }
    }

    if property_type_id:
        query["property_type_id"] = property_type_id
    if listing_type:
        query["listing_type"] = listing_type

    # count_documents doesn't support $nearSphere, so we fetch and count
    cursor = db.properties.find(query).limit(limit * page)
    all_results = []
    current_user_id = current_user["_id"] if current_user else None

    async for prop in cursor:
        all_results.append(prop)

    total = len(all_results)
    skip = (page - 1) * limit
    paged = all_results[skip:skip + limit]

    properties = []
    for prop in paged:
        prop = await enrich_property(prop, current_user_id)
        properties.append(build_property_response(prop))

    return PropertyListResponse(
        properties=properties, total=total, page=page, limit=limit,
        total_pages=math.ceil(total / limit) if limit > 0 else 0
    )


@router.get("/my-listings", response_model=PropertyListResponse)
async def my_listings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get properties listed by current user."""
    db = get_database()
    query = {"listed_by": {"$in": [str(current_user["_id"]), current_user["_id"]]}}

    total = await db.properties.count_documents(query)
    skip = (page - 1) * limit

    cursor = db.properties.find(query).sort("created_at", -1).skip(skip).limit(limit)
    properties = []

    async for prop in cursor:
        prop = await enrich_property(prop, current_user["_id"])
        properties.append(build_property_response(prop))

    return PropertyListResponse(
        properties=properties,
        total=total,
        page=page,
        limit=limit,
        total_pages=math.ceil(total / limit) if limit > 0 else 0
    )


@router.get("/top-viewed", response_model=PropertyListResponse)
async def top_viewed_properties(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    exclude_ids: Optional[str] = Query(None, description="Comma-separated property IDs to exclude"),
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Get properties sorted by most views, excluding specified IDs."""
    db = get_database()
    query = {"status": "active"}

    if exclude_ids:
        ids_to_exclude = [eid.strip() for eid in exclude_ids.split(",") if eid.strip()]
        obj_ids = []
        for eid in ids_to_exclude:
            try:
                obj_ids.append(ObjectId(eid))
            except Exception:
                pass
        query["_id"] = {"$nin": obj_ids + [ObjectId(e) for e in ids_to_exclude if len(e) == 24]}

    total = await db.properties.count_documents(query)
    skip = (page - 1) * limit

    cursor = db.properties.find(query).sort("views_count", -1).skip(skip).limit(limit)
    properties = []
    current_user_id = current_user["_id"] if current_user else None

    async for prop in cursor:
        prop = await enrich_property(prop, current_user_id)
        properties.append(build_property_response(prop))

    return PropertyListResponse(
        properties=properties, total=total, page=page, limit=limit,
        total_pages=math.ceil(total / limit) if limit > 0 else 0
    )


@router.get("/recommendations", response_model=PropertyListResponse)
async def recommended_properties(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    exclude_ids: Optional[str] = Query(None, description="Comma-separated property IDs to exclude"),
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Get recommended/featured properties, excluding specified IDs."""
    db = get_database()
    query = {"status": "active"}

    if exclude_ids:
        ids_to_exclude = [eid.strip() for eid in exclude_ids.split(",") if eid.strip()]
        obj_ids = []
        for eid in ids_to_exclude:
            try:
                obj_ids.append(ObjectId(eid))
            except Exception:
                pass
        query["_id"] = {"$nin": obj_ids + [ObjectId(e) for e in ids_to_exclude if len(e) == 24]}

    total = await db.properties.count_documents(query)
    skip = (page - 1) * limit

    cursor = db.properties.find(query).sort([
        ("favorites_count", -1), ("created_at", -1)
    ]).skip(skip).limit(limit)

    properties = []
    current_user_id = current_user["_id"] if current_user else None

    async for prop in cursor:
        prop = await enrich_property(prop, current_user_id)
        properties.append(build_property_response(prop))

    return PropertyListResponse(
        properties=properties, total=total, page=page, limit=limit,
        total_pages=math.ceil(total / limit) if limit > 0 else 0
    )





@router.get("/{slug}", response_model=PropertyResponse)
async def get_property(slug: str, current_user: Optional[dict] = Depends(get_current_user_optional)):
    """Get property details by slug."""
    db = get_database()

    prop = await db.properties.find_one({"slug": slug})
    if not prop:
        try:
            prop = await db.properties.find_one({"_id": ObjectId(slug)})
        except Exception:
            pass

    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Increment views
    await db.properties.update_one({"_id": prop["_id"]}, {"$inc": {"views_count": 1}})

    # Track who viewed (logged-in users only, don't track lister viewing own property)
    current_user_id = current_user["_id"] if current_user else None
    if current_user_id and str(current_user_id) != str(prop.get("listed_by")):
        await db.property_views.update_one(
            {"property_id": str(prop["_id"]), "user_id": current_user_id},
            {"$set": {
                "property_id": str(prop["_id"]),
                "user_id": current_user_id,
                "user_name": current_user.get("full_name"),
                "user_email": current_user.get("email"),
                "user_phone": current_user.get("phone"),
                "user_avatar": current_user.get("avatar"),
                "last_viewed_at": now_utc(),
            }, "$inc": {"view_count": 1}, "$setOnInsert": {"first_viewed_at": now_utc()}},
            upsert=True
        )

    prop = await enrich_property(prop, current_user_id)

    return build_property_response(prop)


@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(data: PropertyCreate, current_user: dict = Depends(get_current_user)):
    """Create a new property listing."""
    db = get_database()

    # Validate property type exists
    try:
        pt = await db.property_types.find_one({"_id": ObjectId(data.property_type_id), "is_active": True})
    except Exception:
        pt = None
    if not pt:
        raise HTTPException(status_code=400, detail="Invalid property type")

    # Generate unique slug
    slug = await generate_unique_slug(db.properties, data.title)

    # Geocode address if coordinates not provided
    location_data = data.location.model_dump()
    coords = location_data.get("coordinates", {}).get("coordinates", [0, 0])
    if coords == [0, 0] or coords == [0.0, 0.0]:
        geo = await geocode_address(
            data.location.address, data.location.city,
            data.location.state, data.location.zip_code
        )
        if geo:
            location_data["coordinates"] = {
                "type": "Point",
                "coordinates": [geo["lng"], geo["lat"]]
            }

    prop_doc = {
        "title": data.title,
        "slug": slug,
        "description": data.description,
        "property_type_id": data.property_type_id,
        "listing_type": data.listing_type,
        "status": "pending",
        "price": data.price,
        "price_unit": data.price_unit,
        "currency": "USD",
        "details": data.details.model_dump(),
        "amenities": data.amenities,
        "location": location_data,
        "images": [img.model_dump() for img in data.images],
        "video_url": data.video_url,
        "floor_plan_url": data.floor_plan_url,
        "floor_plan_urls": data.floor_plan_urls or [],
        "listed_by": current_user["_id"],
        "contact_phone": data.contact_phone or current_user.get("phone"),
        "contact_email": data.contact_email or current_user.get("email"),
        "admin_review": None,
        "views_count": 0,
        "favorites_count": 0,
        "inquiries_count": 0,
        "listed_at": None,
        "created_at": now_utc(),
        "updated_at": now_utc()
    }

    result = await db.properties.insert_one(prop_doc)
    prop_doc["_id"] = result.inserted_id

    prop_doc = await enrich_property(prop_doc, current_user["_id"])
    return build_property_response(prop_doc)


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(property_id: str, data: PropertyUpdate, current_user: dict = Depends(get_current_user)):
    """Update a property listing."""
    db = get_database()

    try:
        prop = await db.properties.find_one({"_id": ObjectId(property_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid property ID")

    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Only owner or admin can update
    if str(prop.get("listed_by")) != str(current_user["_id"]) and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    update_data = {}
    for field, value in data.model_dump(exclude_none=True).items():
        if field == "details" and value:
            update_data["details"] = value
        elif field == "location" and value:
            update_data["location"] = value
        elif field == "images" and value:
            update_data["images"] = [img if isinstance(img, dict) else img.model_dump() for img in value]
        else:
            update_data[field] = value

    update_data["updated_at"] = now_utc()

    await db.properties.update_one(
        {"_id": ObjectId(property_id)},
        {"$set": update_data}
    )

    updated = await db.properties.find_one({"_id": ObjectId(property_id)})
    updated = await enrich_property(updated, current_user["_id"])
    return build_property_response(updated)


@router.delete("/{property_id}", response_model=dict)
async def delete_property(property_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a property listing."""
    db = get_database()

    try:
        prop = await db.properties.find_one({"_id": ObjectId(property_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid property ID")

    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if prop["listed_by"] != current_user["_id"] and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.properties.delete_one({"_id": ObjectId(property_id)})
    await db.favorites.delete_many({"property_id": property_id})
    await db.inquiries.delete_many({"property_id": property_id})
    await db.reviews.delete_many({"property_id": property_id})
    await db.property_views.delete_many({"property_id": property_id})

    return {"message": "Property deleted", "success": True}


@router.get("/{property_id}/viewers")
async def get_property_viewers(
    property_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get users who viewed a property (leads). Only property owner or admin can see."""
    db = get_database()

    try:
        prop = await db.properties.find_one({"_id": ObjectId(property_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid property ID")

    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if str(prop.get("listed_by")) != str(current_user["_id"]) and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view leads")

    total = await db.property_views.count_documents({"property_id": property_id})
    skip = (page - 1) * limit

    cursor = db.property_views.find({"property_id": property_id}).sort("last_viewed_at", -1).skip(skip).limit(limit)
    viewers = []

    async for v in cursor:
        viewers.append({
            "user_id": v.get("user_id"),
            "user_name": v.get("user_name"),
            "user_email": v.get("user_email"),
            "user_phone": v.get("user_phone"),
            "user_avatar": v.get("user_avatar"),
            "view_count": v.get("view_count", 1),
            "first_viewed_at": v.get("first_viewed_at"),
            "last_viewed_at": v.get("last_viewed_at"),
        })

    return {
        "viewers": viewers,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": math.ceil(total / limit) if limit > 0 else 0
    }
