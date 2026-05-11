"""
PropertyKING — Database Connection
Async MongoDB connection using Motor driver.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

# Global database client and database references
client: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None


async def connect_to_database():
    """Initialize MongoDB connection and create indexes."""
    global client, db

    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]

    # Create indexes for performance
    await create_indexes()

    print(f"[OK] Connected to MongoDB: {settings.DATABASE_NAME}")


async def close_database_connection():
    """Close MongoDB connection."""
    global client
    if client:
        client.close()
        print("[X] MongoDB connection closed")


async def create_indexes():
    """Create database indexes for optimal query performance."""
    # Users indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index([("location.coordinates", "2dsphere")])

    # Properties indexes
    await db.properties.create_index([("location.coordinates.coordinates", "2dsphere")])
    await db.properties.create_index("status")
    await db.properties.create_index("property_type_id")
    await db.properties.create_index("listing_type")
    await db.properties.create_index("price")
    await db.properties.create_index("listed_by")
    await db.properties.create_index("slug", unique=True)
    await db.properties.create_index([
        ("status", 1),
        ("property_type_id", 1),
        ("listing_type", 1),
        ("price", 1)
    ])

    # Property Types
    await db.property_types.create_index("slug", unique=True)
    await db.property_types.create_index("order")

    # Amenities
    await db.amenities.create_index("slug", unique=True)
    await db.amenities.create_index("category")

    # Inquiries
    await db.inquiries.create_index("property_id")
    await db.inquiries.create_index("user_id")
    await db.inquiries.create_index("lister_id")

    # Reviews
    await db.reviews.create_index("property_id")
    await db.reviews.create_index("user_id")

    # Notifications
    await db.notifications.create_index([("user_id", 1), ("is_read", 1)])
    await db.notifications.create_index("created_at")

    # Favorites
    await db.favorites.create_index([("user_id", 1), ("property_id", 1)], unique=True)

    # Saved Searches
    await db.saved_searches.create_index("user_id")

    print("[OK] Database indexes created")


def get_database() -> AsyncIOMotorDatabase:
    """Get database instance."""
    return db
