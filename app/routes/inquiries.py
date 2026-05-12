"""
PropertyKING — Inquiry Routes
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
import math

from app.database import get_database
from app.middleware.auth import get_current_user
from app.models.inquiry import InquiryCreate, InquiryRespond, InquiryResponse
from app.services.push_notification import send_push_notification
from app.services.email_service import send_new_inquiry_email
from app.utils.helpers import now_utc

router = APIRouter(prefix="/inquiries", tags=["Inquiries"])


@router.post("", response_model=InquiryResponse, status_code=201)
async def create_inquiry(data: InquiryCreate, current_user: dict = Depends(get_current_user)):
    """Send inquiry about a property."""
    db = get_database()

    try:
        prop = await db.properties.find_one({"_id": ObjectId(data.property_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid property ID")
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if prop["listed_by"] == current_user["_id"]:
        raise HTTPException(status_code=400, detail="Cannot inquire on your own property")

    doc = {
        "property_id": data.property_id,
        "user_id": current_user["_id"],
        "lister_id": prop["listed_by"],
        "message": data.message,
        "inquiry_type": data.inquiry_type,
        "status": "pending",
        "response": None,
        "responded_at": None,
        "contact_phone": data.contact_phone or current_user.get("phone"),
        "preferred_date": data.preferred_date,
        "preferred_time": data.preferred_time,
        "contact_preference": data.contact_preference,
        "created_at": now_utc()
    }

    result = await db.inquiries.insert_one(doc)
    await db.properties.update_one({"_id": ObjectId(data.property_id)}, {"$inc": {"inquiries_count": 1}})

    # Notify lister
    await send_push_notification(
        prop["listed_by"], "New Inquiry!",
        f"{current_user.get('full_name', 'Someone')} is interested in '{prop.get('title', 'your property')}'",
        "new_inquiry", {"property_id": data.property_id}
    )

    # Email lister
    try:
        lister = await db.users.find_one({"_id": ObjectId(prop["listed_by"])})
        if lister:
            await send_new_inquiry_email(
                lister.get("email", ""), lister.get("full_name", ""),
                prop.get("title", ""), current_user.get("full_name", ""), data.message
            )
    except Exception:
        pass

    return InquiryResponse(
        id=str(result.inserted_id), property_id=data.property_id,
        property_title=prop.get("title"), user_id=current_user["_id"],
        user_name=current_user.get("full_name"), lister_id=prop["listed_by"],
        message=data.message, inquiry_type=data.inquiry_type,
        status="pending", contact_phone=data.contact_phone or current_user.get("phone"),
        preferred_date=data.preferred_date, preferred_time=data.preferred_time,
        contact_preference=data.contact_preference, created_at=doc["created_at"])


@router.get("/sent")
async def get_sent_inquiries(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get inquiries sent by current user."""
    db = get_database()
    query = {"user_id": current_user["_id"]}
    total = await db.inquiries.count_documents(query)
    skip = (page - 1) * limit

    cursor = db.inquiries.find(query).sort("created_at", -1).skip(skip).limit(limit)
    inquiries = []

    async for inq in cursor:
        prop = await db.properties.find_one({"_id": ObjectId(inq["property_id"])}) if inq.get("property_id") else None
        primary_img = None
        if prop:
            for img in prop.get("images", []):
                if img.get("is_primary"):
                    primary_img = img["url"]
                    break
            if not primary_img and prop.get("images"):
                primary_img = prop["images"][0].get("url")

        inquiries.append(InquiryResponse(
            id=str(inq["_id"]), property_id=inq.get("property_id", ""),
            property_title=prop.get("title") if prop else None,
            property_image=primary_img, user_id=inq.get("user_id", ""),
            lister_id=inq.get("lister_id", ""), message=inq.get("message", ""),
            inquiry_type=inq.get("inquiry_type", "general"), status=inq.get("status", "pending"),
            response=inq.get("response"), responded_at=inq.get("responded_at"),
            created_at=inq.get("created_at")))

    return {"inquiries": inquiries, "total": total, "page": page, "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0}


@router.get("/received")
async def get_received_inquiries(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    status_filter: str = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user)
):
    """Get inquiries received by current lister."""
    db = get_database()
    query = {"lister_id": current_user["_id"]}
    if status_filter:
        query["status"] = status_filter

    total = await db.inquiries.count_documents(query)
    skip = (page - 1) * limit

    cursor = db.inquiries.find(query).sort("created_at", -1).skip(skip).limit(limit)
    inquiries = []

    async for inq in cursor:
        prop = await db.properties.find_one({"_id": ObjectId(inq["property_id"])}) if inq.get("property_id") else None
        user = await db.users.find_one({"_id": ObjectId(inq["user_id"])}) if inq.get("user_id") else None

        inquiries.append(InquiryResponse(
            id=str(inq["_id"]), property_id=inq.get("property_id", ""),
            property_title=prop.get("title") if prop else None,
            user_id=inq.get("user_id", ""),
            user_name=user.get("full_name") if user else None,
            user_avatar=user.get("avatar") if user else None,
            user_email=user.get("email") if user else None,
            lister_id=inq.get("lister_id", ""), message=inq.get("message", ""),
            inquiry_type=inq.get("inquiry_type", "general"), status=inq.get("status", "pending"),
            response=inq.get("response"), responded_at=inq.get("responded_at"),
            contact_phone=inq.get("contact_phone"), preferred_date=inq.get("preferred_date"),
            created_at=inq.get("created_at")))

    return {"inquiries": inquiries, "total": total, "page": page, "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0}


@router.put("/{inquiry_id}/respond")
async def respond_to_inquiry(inquiry_id: str, data: InquiryRespond, current_user: dict = Depends(get_current_user)):
    """Respond to an inquiry (lister only)."""
    db = get_database()

    try:
        inq = await db.inquiries.find_one({"_id": ObjectId(inquiry_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid inquiry ID")
    if not inq:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    if inq["lister_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.inquiries.update_one(
        {"_id": ObjectId(inquiry_id)},
        {"$set": {"response": data.response, "status": "responded", "responded_at": now_utc()}}
    )

    await send_push_notification(
        inq["user_id"], "Inquiry Response",
        f"You received a response to your inquiry", "inquiry_response",
        {"property_id": inq.get("property_id", "")}
    )

    return {"message": "Response sent", "success": True}
