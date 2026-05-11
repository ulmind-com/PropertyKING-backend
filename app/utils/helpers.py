"""
PropertyKING — Helper Utilities
Common helper functions used across the application.
"""

from bson import ObjectId
from datetime import datetime, timezone
from slugify import slugify
import math
import re


def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    # Convert any remaining ObjectId fields
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            doc[key] = value.isoformat()
    return doc


def serialize_docs(docs: list) -> list:
    """Convert list of MongoDB documents to JSON-serializable list."""
    return [serialize_doc(doc) for doc in docs]


def generate_slug(text: str, existing_slugs: list = None) -> str:
    """Generate a URL-friendly slug from text."""
    base_slug = slugify(text, max_length=100)

    if existing_slugs is None:
        return base_slug

    slug = base_slug
    counter = 1
    while slug in existing_slugs:
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


async def generate_unique_slug(collection, text: str) -> str:
    """Generate a unique slug for a MongoDB collection."""
    base_slug = slugify(text, max_length=100)
    slug = base_slug
    counter = 1

    while await collection.find_one({"slug": slug}):
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def now_utc() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def calculate_pagination(total: int, page: int, limit: int) -> dict:
    """Calculate pagination metadata."""
    total_pages = math.ceil(total / limit) if limit > 0 else 0
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }


def miles_to_meters(miles: float) -> float:
    """Convert miles to meters for MongoDB geo queries."""
    return miles * 1609.344


def validate_object_id(id_str: str) -> bool:
    """Check if a string is a valid MongoDB ObjectId."""
    try:
        ObjectId(id_str)
        return True
    except Exception:
        return False


def sanitize_phone(phone: str) -> str:
    """Sanitize phone number to standard format."""
    digits = re.sub(r'[^\d+]', '', phone)
    if not digits.startswith('+'):
        if len(digits) == 10:
            digits = '+1' + digits
        elif len(digits) == 11 and digits.startswith('1'):
            digits = '+' + digits
    return digits


def format_price(price: float, currency: str = "USD") -> str:
    """Format price for display."""
    if currency == "USD":
        if price >= 1_000_000:
            return f"${price / 1_000_000:.1f}M"
        elif price >= 1_000:
            return f"${price / 1_000:.0f}K"
        else:
            return f"${price:,.0f}"
    return f"{price:,.2f} {currency}"
