import os
from io import BytesIO

import fitz
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


def pdf_to_text(file_bytes: bytes) -> str:
    _configure_tesseract()
    max_pages = int(os.getenv("PDF_OCR_MAX_PAGES", "3"))
    zoom = float(os.getenv("PDF_OCR_ZOOM", "2"))
    matrix = fitz.Matrix(zoom, zoom)
    extracted_pages = []

    with fitz.open(stream=file_bytes, filetype="pdf") as document:
        for page_index in range(min(len(document), max_pages)):
            page = document.load_page(page_index)
            text = page.get_text("text").strip()
            if not text:
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                img = Image.open(BytesIO(pixmap.tobytes("png")))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                text = pytesseract.image_to_string(img).strip()
            if text:
                extracted_pages.append(text)

    return "\n\n".join(extracted_pages)
