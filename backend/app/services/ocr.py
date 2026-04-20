import re
import time
import logging
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)

_OCR_PROMPT = (
    "You are a license plate OCR engine. "
    "Look at this image and extract ONLY the license plate number/text. "
    "Return ONLY the plate string (e.g. 'KA01AB1234'). "
    "If you cannot read a plate clearly, return exactly: UNREADABLE"
)

_PLATE_PATTERN = re.compile(r"^[A-Z0-9\-\s]{3,15}$")
_MAX_RETRIES = 3
_RETRY_DELAY = 1.5


class OCRFailedException(Exception):
    pass


def _is_valid_plate(text: str) -> bool:
    cleaned = text.strip().upper().replace(" ", "")
    return bool(_PLATE_PATTERN.match(cleaned)) and cleaned != "UNREADABLE"


def _normalize_plate(text: str) -> str:
    return text.strip().upper().replace(" ", "").replace("-", "")


def extract_license_plate(image_bytes: bytes) -> str:
    """
    Calls Gemini Vision to extract a license plate.
    Returns normalized plate string.
    Raises OCRFailedException if all retries fail or result is unreadable.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("[OCR] GEMINI_API_KEY not set — using mock fallback")
        return _mock_fallback()

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    last_error: Optional[Exception] = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info(f"[OCR] Attempt {attempt}/{_MAX_RETRIES}")
            response = model.generate_content(
                [
                    _OCR_PROMPT,
                    {"mime_type": "image/jpeg", "data": image_bytes},
                ]
            )
            raw = response.text.strip()
            logger.info(f"[OCR] Raw response: {raw!r}")

            if _is_valid_plate(raw):
                plate = _normalize_plate(raw)
                logger.info(f"[OCR] Extracted plate: {plate}")
                return plate

            logger.warning(f"[OCR] Invalid plate response: {raw!r}")

        except Exception as exc:
            last_error = exc
            logger.error(f"[OCR] Attempt {attempt} failed: {exc}")

        if attempt < _MAX_RETRIES:
            time.sleep(_RETRY_DELAY)

    raise OCRFailedException(
        f"OCR failed after {_MAX_RETRIES} attempts. Last error: {last_error}"
    )


def _mock_fallback() -> str:
    """Returns a deterministic mock plate for demo/dev when API key missing."""
    return "KA01AB1234"


def save_captured_image(image_bytes: bytes, filename: str) -> str:
    """Saves image to CAPTURED_IMAGES_DIR and returns relative path."""
    dir_path = Path(settings.CAPTURED_IMAGES_DIR)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / filename
    file_path.write_bytes(image_bytes)
    return str(file_path)
