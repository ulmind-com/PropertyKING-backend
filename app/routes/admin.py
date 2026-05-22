"""
PropertyKING — Admin Routes
Dashboard, property review, user management, broadcast notifications.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
from typing import Optional
import math

from app.database import get_database
from app.middleware.auth import require_admin
from app.models.property import PropertyReject
from app.models.notification import BroadcastNotification
from pydantic import BaseModel
import httpx
import os
from app.services.push_notification import send_push_notification, broadcast_notification
from app.services.email_service import send_property_approved_email, send_property_rejected_email, send_property_deleted_email
from app.utils.helpers import now_utc

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard")
async def admin_dashboard(admin: dict = Depends(require_admin)):
    """Get admin dashboard analytics."""
    db = get_database()

    total_users = await db.users.count_documents({"role": {"$ne": "admin"}})
    total_listers = await db.users.count_documents({"role": "lister"})
    total_properties = await db.properties.count_documents({})
    active_properties = await db.properties.count_documents({"status": "active"})
    pending_properties = await db.properties.count_documents({"status": "pending"})
    rejected_properties = await db.properties.count_documents({"status": "rejected"})
    sold_properties = await db.properties.count_documents({"status": "sold"})
    total_inquiries = await db.inquiries.count_documents({})
    pending_inquiries = await db.inquiries.count_documents({"status": "pending"})
    total_reviews = await db.reviews.count_documents({})
    total_favorites = await db.favorites.count_documents({})

    # Properties by type
    type_pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$property_type_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    type_stats = await db.properties.aggregate(type_pipeline).to_list(20)
    for stat in type_stats:
        if stat["_id"]:
            try:
                pt = await db.property_types.find_one({"_id": ObjectId(stat["_id"])})
                stat["name"] = pt["name"] if pt else "Unknown"
            except Exception:
                stat["name"] = "Unknown"

    # Properties by state
    state_pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$location.state", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 10}
    ]
    state_stats = await db.properties.aggregate(state_pipeline).to_list(10)

    # Listing type distribution
    listing_pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$listing_type", "count": {"$sum": 1}}}
    ]
    listing_stats = await db.properties.aggregate(listing_pipeline).to_list(5)

    return {
        "users": {"total": total_users, "listers": total_listers},
        "properties": {
            "total": total_properties, "active": active_properties,
            "pending": pending_properties, "rejected": rejected_properties, "sold": sold_properties
        },
        "inquiries": {"total": total_inquiries, "pending": pending_inquiries},
        "reviews": total_reviews,
        "favorites": total_favorites,
        "by_type": [{"type": s.get("name", s["_id"]), "count": s["count"]} for s in type_stats],
        "by_state": [{"state": s["_id"], "count": s["count"]} for s in state_stats],
        "by_listing_type": [{"type": s["_id"], "count": s["count"]} for s in listing_stats]
    }


@router.get("/properties")
async def admin_list_properties(
    page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    admin: dict = Depends(require_admin)
):
    """List all properties (admin view)."""
    db = get_database()
    query = {}
    if status_filter:
        query["status"] = status_filter
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"location.city": {"$regex": search, "$options": "i"}}
        ]

    total = await db.properties.count_documents(query)
    skip = (page - 1) * limit
    cursor = db.properties.find(query).sort("updated_at", -1).skip(skip).limit(limit)

    properties = []
    async for prop in cursor:
        lister = None
        lister_id = prop.get("listed_by") or prop.get("lister_id")
        if lister_id:
            try:
                lister = await db.users.find_one({"_id": ObjectId(lister_id)})
            except Exception:
                pass
        pt = None
        if prop.get("property_type_id"):
            try:
                pt = await db.property_types.find_one({"_id": ObjectId(prop["property_type_id"])})
            except Exception:
                pass

        # Handle images (can be list of dicts or list of strings)
        all_images = []
        primary_img = None
        for img in prop.get("images", []):
            if isinstance(img, dict):
                all_images.append(img.get("url"))
                if img.get("is_primary"):
                    primary_img = img.get("url")
            elif isinstance(img, str):
                all_images.append(img)

        if not primary_img and all_images:
            primary_img = all_images[0]

        # Extract location (handle both flat and nested)
        loc = prop.get("location", {})
        city = loc.get("city", "") if isinstance(loc, dict) else ""
        state = loc.get("state", "") if isinstance(loc, dict) else ""
        address = loc.get("address", "") if isinstance(loc, dict) else ""
        zip_code = loc.get("zip_code", "") if isinstance(loc, dict) else ""
        # Flat fields fallback
        if not city:
            city = prop.get("city", "")
        if not state:
            state = prop.get("state", "")
        if not address:
            address = prop.get("address", "")
        if not zip_code:
            zip_code = prop.get("zip_code", "")

        # Coordinates
        coords = loc.get("coordinates", {}) if isinstance(loc, dict) else {}
        lat = None
        lng = None
        if isinstance(coords, dict) and coords.get("coordinates"):
            c = coords["coordinates"]
            lng, lat = c[0], c[1]
        if lat is None:
            lat = prop.get("latitude")
        if lng is None:
            lng = prop.get("longitude")

        # Details (nested or flat)
        details = prop.get("details", {}) or {}
        bedrooms = details.get("bedrooms") or prop.get("bedrooms")
        bathrooms = details.get("bathrooms") or prop.get("bathrooms")
        area = details.get("total_sqft") or prop.get("area_sqft")
        year_built = details.get("year_built") or prop.get("year_built")
        stories = details.get("stories")
        garage = details.get("garage_spaces")
        heating = details.get("heating")
        cooling = details.get("cooling")

        properties.append({
            "id": str(prop["_id"]), "title": prop.get("title", ""), "slug": prop.get("slug", ""),
            "description": prop.get("description", ""),
            "status": prop.get("status", ""), "price": prop.get("price", 0),
            "currency": prop.get("currency", "USD"),
            "listing_type": prop.get("listing_type", ""),
            "property_type": pt.get("name") if pt else (prop.get("property_type_name") or prop.get("property_type")),
            "city": city, "state": state, "address": address, "zip_code": zip_code,
            "country": prop.get("country", ""),
            "latitude": lat, "longitude": lng,
            "bedrooms": bedrooms, "bathrooms": bathrooms, "area_sqft": area,
            "year_built": year_built, "stories": stories, "garage_spaces": garage,
            "heating": heating, "cooling": cooling,
            "amenities": prop.get("amenities", []),
            "image": primary_img,
            "images": all_images,
            "lister_name": lister.get("full_name") if lister else (prop.get("lister_name") or None),
            "lister_email": lister.get("email") if lister else (prop.get("contact_email") or None),
            "lister_phone": lister.get("phone") if lister else (prop.get("contact_phone") or None),
            "lister_avatar": lister.get("avatar") if lister else None,
            "views": prop.get("views_count", 0) or prop.get("views", 0),
            "favorites": prop.get("favorites_count", 0) or prop.get("favorites", 0),
            "inquiries": prop.get("inquiries_count", 0) or prop.get("inquiries", 0),
            "created_at": prop.get("created_at"),
            "updated_at": prop.get("updated_at"),
            "listed_at": prop.get("listed_at"),
            "admin_review": prop.get("admin_review"),
            "video_url": prop.get("video_url"),
            "floor_plan_url": prop.get("floor_plan_url"),
            "floor_plan_urls": prop.get("floor_plan_urls", []),
        })

    return {"properties": properties, "total": total, "page": page, "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0}


@router.get("/properties/count")
async def admin_count_properties(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    admin: dict = Depends(require_admin)
):
    """Get total count of properties for fast loading."""
    db = get_database()
    query = {}
    if status_filter:
        query["status"] = status_filter
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"location.city": {"$regex": search, "$options": "i"}}
        ]
    total = await db.properties.count_documents(query)
    return {"total": total}



@router.put("/properties/{property_id}/approve")
async def approve_property(property_id: str, admin: dict = Depends(require_admin)):
    """Approve a pending property listing."""
    db = get_database()
    try:
        prop = await db.properties.find_one({"_id": ObjectId(property_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid property ID")
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    await db.properties.update_one(
        {"_id": ObjectId(property_id)},
        {"$set": {
            "status": "active", "listed_at": now_utc(), "updated_at": now_utc(),
            "admin_review": {"reviewed_by": admin["_id"], "reviewed_at": now_utc(), "rejection_reason": None}
        }})

    # Notify lister
    lister_id = prop.get("listed_by") or prop.get("lister_id")
    if lister_id:
        await send_push_notification(lister_id, "Listing Approved! ✅",
            f"Your property '{prop.get('title', '')}' is now live!", "property_approved",
            {"property_id": property_id})

        try:
            lister = await db.users.find_one({"_id": ObjectId(lister_id)})
            if lister:
                await send_property_approved_email(lister["email"], lister["full_name"], prop.get("title", ""))
        except Exception:
            pass

    return {"message": "Property approved", "success": True}


@router.put("/properties/{property_id}/reject")
async def reject_property(property_id: str, data: PropertyReject, admin: dict = Depends(require_admin)):
    """Reject a pending property listing."""
    db = get_database()
    try:
        prop = await db.properties.find_one({"_id": ObjectId(property_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid property ID")
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    await db.properties.update_one(
        {"_id": ObjectId(property_id)},
        {"$set": {
            "status": "rejected", "updated_at": now_utc(),
            "admin_review": {"reviewed_by": admin["_id"], "reviewed_at": now_utc(), "rejection_reason": data.reason}
        }})

    lister_id = prop.get("listed_by") or prop.get("lister_id")
    if lister_id:
        await send_push_notification(lister_id, "Listing Needs Changes",
            f"Your property '{prop.get('title', '')}' was not approved.", "property_rejected",
            {"property_id": property_id})

        try:
            lister = await db.users.find_one({"_id": ObjectId(lister_id)})
            if lister:
                await send_property_rejected_email(lister["email"], lister["full_name"], prop.get("title", ""), data.reason)
        except Exception:
            pass

    return {"message": "Property rejected successfully", "property_id": property_id}


@router.delete("/properties/{property_id}")
async def delete_property(
    property_id: str, 
    reason: str = Query(..., min_length=1),
    admin: dict = Depends(require_admin)
):
    """Admin endpoint to permanently delete a property."""
    db = get_database()
    try:
        prop = await db.properties.find_one({"_id": ObjectId(property_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid property ID")
    
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
        
    # Delete the property
    await db.properties.delete_one({"_id": ObjectId(property_id)})
    
    # Send email to lister
    lister_id = prop.get("listed_by") or prop.get("lister_id")
    if lister_id:
        try:
            lister = await db.users.find_one({"_id": ObjectId(lister_id)})
            if lister and lister.get("email"):
                await send_property_deleted_email(lister["email"], lister.get("full_name", ""), prop.get("title", ""), reason)
        except Exception:
            pass
            
    return {"message": "Property deleted successfully", "property_id": property_id, "success": True}


@router.get("/users")
async def admin_list_users(
    page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100),
    role: Optional[str] = None, search: Optional[str] = None,
    admin: dict = Depends(require_admin)
):
    """List all users (admin view)."""
    db = get_database()
    query = {}
    if role:
        query["role"] = role
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]

    total = await db.users.count_documents(query)
    skip = (page - 1) * limit
    cursor = db.users.find(query, {"password_hash": 0}).sort("created_at", -1).skip(skip).limit(limit)

    users = []
    async for user in cursor:
        listings_count = await db.properties.count_documents({"listed_by": str(user["_id"])})
        users.append({
            "id": str(user["_id"]), "full_name": user.get("full_name", ""),
            "email": user.get("email", ""), "phone": user.get("phone"),
            "avatar": user.get("avatar"), "role": user.get("role", "user"),
            "lister_type": user.get("lister_type"), "verified": user.get("verified", False),
            "is_active": user.get("is_active", True), "listings_count": listings_count,
            "location": user.get("location"), "created_at": user.get("created_at")
        })

    return {"users": users, "total": total, "page": page, "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0}


@router.put("/users/{user_id}/status")
async def toggle_user_status(user_id: str, admin: dict = Depends(require_admin)):
    """Activate/Deactivate a user."""
    db = get_database()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_status = not user.get("is_active", True)
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": new_status, "updated_at": now_utc()}})

    return {"message": f"User {'activated' if new_status else 'deactivated'}", "is_active": new_status, "success": True}


@router.put("/users/{user_id}/toggle-admin")
async def toggle_user_admin(user_id: str, admin: dict = Depends(require_admin)):
    """Toggle a user's admin status."""
    db = get_database()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent the main admin from accidentally demoting themselves (if we want)
    # But for now, we just toggle.
    current_role = user.get("role", "user")
    new_role = "user" if current_role == "admin" else "admin"

    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"role": new_role, "updated_at": now_utc()}})
    
    msg = "User is now an admin" if new_role == "admin" else "User admin rights revoked"
    return {"message": msg, "role": new_role, "success": True}


@router.post("/notifications/broadcast")
async def send_broadcast(data: BroadcastNotification, admin: dict = Depends(require_admin)):
    """Broadcast notification to users."""
    count = await broadcast_notification(
        data.title, data.body, data.type, data.data, data.target_roles, data.target_states, data.image_url)
    return {"message": f"Notification sent to {count} users", "recipients": count, "success": True}


class AIGenerateRequest(BaseModel):
    prompt: str
    tone: Optional[str] = "professional"
    type: Optional[str] = "system"

@router.post("/notifications/generate")
async def generate_notification_ai(data: AIGenerateRequest, admin: dict = Depends(require_admin)):
    """Generate a push notification using OpenRouter AI."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured")
    
    system_prompt = f"You are a marketing expert for PropertyKING, a premium real estate app. Write a short, engaging push notification. Tone: {data.tone}. Type: {data.type}. The notification should have a 'title' (max 50 chars) and a 'body' (max 150 chars). Return ONLY a valid JSON object in this format: {{\"title\": \"...\", \"body\": \"...\"}}. Do not include any markdown formatting or other text."
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://propertyking.com",
                    "X-Title": "PropertyKING Admin"
                },
                json={
                    "model": "openrouter/auto",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": data.prompt}
                    ],
                    "response_format": {"type": "json_object"}
                },
                timeout=15.0
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            import json
            parsed = json.loads(content)
            return {"title": parsed.get("title", ""), "body": parsed.get("body", ""), "success": True}
        except Exception as e:
            print("AI Generate Error:", str(e))
            raise HTTPException(status_code=500, detail="Failed to generate AI content. Please try again.")

