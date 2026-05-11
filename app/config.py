"""
PropertyKING — Application Configuration
Loads all environment variables and provides typed settings.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "PropertyKING"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_VERSION: str = "v1"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:5173,http://localhost:5174"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "propertyking"

    # JWT
    JWT_SECRET_KEY: str = "your-super-secret-jwt-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # Firebase
    FIREBASE_CREDENTIALS_PATH: str = "./firebase-service-account.json"

    # Email Settings
    EMAIL_API_KEY: Optional[str] = None
    FROM_EMAIL: str = "handymanpro1980@gmail.com"

    # Google Maps
    GOOGLE_MAPS_API_KEY: str = ""

    # Admin
    ADMIN_EMAIL: str = "admin@propertyking.com"
    ADMIN_PASSWORD: str = "admin123456"

    # File Upload
    MAX_FILE_SIZE_MB: int = 10
    MAX_IMAGES_PER_PROPERTY: int = 20

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
