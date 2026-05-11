"""
PropertyKING — Upload Routes
"""

from fastapi import APIRouter, Depends, UploadFile, File
from typing import List

from app.middleware.auth import get_current_user
from app.services.image_upload import upload_image, upload_multiple_images, upload_video

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/image")
async def upload_single_image(
    file: UploadFile = File(...),
    folder: str = "propertyking",
    current_user: dict = Depends(get_current_user)
):
    """Upload a single image."""
    result = await upload_image(file, folder)
    return {"success": True, "image": result}


@router.post("/images")
async def upload_batch_images(
    files: List[UploadFile] = File(...),
    folder: str = "propertyking",
    current_user: dict = Depends(get_current_user)
):
    """Upload multiple images."""
    results = await upload_multiple_images(files, folder)
    return {"success": True, "images": results, "count": len(results)}


@router.post("/video")
async def upload_single_video(
    file: UploadFile = File(...),
    folder: str = "propertyking/videos",
    current_user: dict = Depends(get_current_user)
):
    """Upload a single video."""
    result = await upload_video(file, folder)
    return {"success": True, "video": result}
