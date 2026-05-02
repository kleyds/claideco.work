import os
from io import BytesIO

import pytesseract
from PIL import Image


def _configure_tesseract() -> None:
    cmd = os.getenv("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def image_to_text(file_bytes: bytes) -> str:
    _configure_tesseract()
    img = Image.open(BytesIO(file_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    return pytesseract.image_to_string(img)
