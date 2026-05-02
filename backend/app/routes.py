import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth import require_api_key
from app.extract import extract_receipt
from app.ocr import image_to_text
from app.schemas import ExtractResponse

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/extract-receipt", response_model=ExtractResponse)
async def extract_receipt_endpoint(
    file: UploadFile = File(..., description="Receipt or invoice image (JPEG/PNG/WebP)"),
    _: str = Depends(require_api_key),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            400,
            f"Unsupported file type: {file.content_type}. Allowed: {sorted(ALLOWED_TYPES)}",
        )

    max_mb = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    content = await file.read()
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {max_mb} MB)")

    try:
        raw_text = image_to_text(content)
    except Exception as e:
        raise HTTPException(500, f"OCR failed: {e}")

    try:
        data = extract_receipt(raw_text)
    except Exception as e:
        raise HTTPException(500, f"Extraction failed: {e}")

    return ExtractResponse(raw_text=raw_text, data=data)
