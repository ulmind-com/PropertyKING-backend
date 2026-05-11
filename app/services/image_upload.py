"""
PropertyKING — Image Upload Service
Handles image upload to Cloudinary.
"""

import cloudinary
import cloudinary.uploader
from fastapi import UploadFile, HTTPException
from app.config import settings
from typing import List

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET
)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # Convert to bytes


async def upload_image(file: UploadFile, folder: str = "propertyking") -> dict:
    """Upload a single image to Cloudinary."""
    # Validate file extension
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds {settings.MAX_FILE_SIZE_MB}MB limit"
        )

    try:
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            content,
            folder=folder,
            resource_type="image",
            transformation=[
                {"quality": "auto", "fetch_format": "auto"},
                {"width": 1920, "height": 1080, "crop": "limit"}
            ]
        )

        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "width": result.get("width"),
            "height": result.get("height"),
            "format": result.get("format"),
            "bytes": result.get("bytes")
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Image upload failed: {str(e)}"
        )


async def upload_multiple_images(files: List[UploadFile], folder: str = "propertyking") -> List[dict]:
    """Upload multiple images to Cloudinary."""
    if len(files) > settings.MAX_IMAGES_PER_PROPERTY:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.MAX_IMAGES_PER_PROPERTY} images allowed"
        )

    results = []
    for file in files:
        result = await upload_image(file, folder)
        results.append(result)

    return results


async def delete_image(public_id: str) -> bool:
    """Delete an image from Cloudinary."""
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"
    except Exception:
        return False


async def upload_video(file: UploadFile, folder: str = "propertyking/videos") -> dict:
    """Upload a video to Cloudinary."""
    allowed_video_ext = {"mp4", "mov", "avi", "webm", "mkv"}
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in allowed_video_ext:
        raise HTTPException(
            status_code=400,
            detail=f"Video type '{ext}' not allowed. Allowed: {', '.join(allowed_video_ext)}"
        )

    content = await file.read()
    max_video_size = 50 * 1024 * 1024  # 50MB limit for videos

    if len(content) > max_video_size:
        raise HTTPException(status_code=400, detail="Video size exceeds 50MB limit")

    try:
        result = cloudinary.uploader.upload(
            content,
            folder=folder,
            resource_type="video",
        )
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "duration": result.get("duration"),
            "format": result.get("format"),
            "bytes": result.get("bytes")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video upload failed: {str(e)}")
