"""
PropertyKING — FastAPI Main Application
Entry point for the backend server.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slugify import slugify

from app.config import settings
from app.database import connect_to_database, close_database_connection, get_database
from app.utils.constants import DEFAULT_PROPERTY_TYPES, DEFAULT_AMENITIES
from app.utils.helpers import now_utc
from app.middleware.auth import hash_password
from app.services.push_notification import init_firebase

# Import all route modules
from app.routes import auth, users, properties, property_types, amenities
from app.routes import favorites, inquiries, reviews, notifications, upload, admin


async def seed_defaults():
    """Seed default property types, amenities, and admin user on first run."""
    db = get_database()

    # Seed property types
    existing_types = await db.property_types.count_documents({})
    if existing_types == 0:
        for pt in DEFAULT_PROPERTY_TYPES:
            pt["slug"] = slugify(pt["name"])
            pt["is_active"] = True
            pt["created_at"] = now_utc()
            pt["updated_at"] = now_utc()
        await db.property_types.insert_many(DEFAULT_PROPERTY_TYPES)
        print(f"[OK] Seeded {len(DEFAULT_PROPERTY_TYPES)} default property types")

    # Seed amenities
    existing_amenities = await db.amenities.count_documents({})
    if existing_amenities == 0:
        for am in DEFAULT_AMENITIES:
            am["slug"] = slugify(am["name"])
            am["is_active"] = True
            am["created_at"] = now_utc()
            am["updated_at"] = now_utc()
        await db.amenities.insert_many(DEFAULT_AMENITIES)
        print(f"[OK] Seeded {len(DEFAULT_AMENITIES)} default amenities")

    # Seed admin user
    existing_admin = await db.users.find_one({"role": "admin"})
    if not existing_admin:
        admin_doc = {
            "full_name": "PropertyKING Admin",
            "email": settings.ADMIN_EMAIL,
            "phone": None,
            "password_hash": hash_password(settings.ADMIN_PASSWORD),
            "avatar": None,
            "role": "admin",
            "lister_type": None,
            "license_number": None,
            "company_name": "PropertyKING",
            "bio": "Platform Administrator",
            "verified": True,
            "fcm_token": None,
            "location": None,
            "favorites": [],
            "created_at": now_utc(),
            "updated_at": now_utc(),
            "is_active": True
        }
        await db.users.insert_one(admin_doc)
        print(f"[OK] Admin user created: {settings.ADMIN_EMAIL}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    # Startup
    await connect_to_database()
    await seed_defaults()
    init_firebase()
    print(f"[OK] PropertyKING API is ready! (env: {settings.APP_ENV})")

    yield

    # Shutdown
    await close_database_connection()


# Create FastAPI app
app = FastAPI(
    title="PropertyKING API",
    description="US Market Premium Property Listing Platform API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
API_PREFIX = f"/api/{settings.API_VERSION}"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(properties.router, prefix=API_PREFIX)
app.include_router(property_types.router, prefix=API_PREFIX)
app.include_router(amenities.router, prefix=API_PREFIX)
app.include_router(favorites.router, prefix=API_PREFIX)
app.include_router(inquiries.router, prefix=API_PREFIX)
app.include_router(reviews.router, prefix=API_PREFIX)
app.include_router(notifications.router, prefix=API_PREFIX)
app.include_router(upload.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check with DB status."""
    db = get_database()
    try:
        await db.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy",
        "database": db_status,
        "environment": settings.APP_ENV
    }
