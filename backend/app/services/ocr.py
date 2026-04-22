import asyncio
import base64
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import PIL for image compression
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OCR_PROMPT = (
    "Extract the vehicle license plate from this image. "
    "Return ONLY the alphanumeric plate text, uppercase, no spaces or hyphens "
    "(example: KA01AB1234). "
    "If the plate is partially visible or blurry but legible, return your best reading. "
    "If the plate is completely unreadable or absent, return exactly: UNREADABLE"
)

_PLATE_PATTERN = re.compile(r"^[A-Z0-9]{3,15}$")

# OpenRouter config
_OPENROUTER_MODEL = "google/gemini-2.5-flash-lite"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_MAX_RETRIES = 3
_OPENROUTER_RETRY_DELAY = 1.0


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class OCRFailedException(Exception):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_plate(text: str) -> str:
    return text.strip().upper().replace(" ", "").replace("-", "")


def _is_valid_plate(text: str) -> bool:
    cleaned = _normalize_plate(text)
    return bool(_PLATE_PATTERN.match(cleaned)) and cleaned != "UNREADABLE"


def flip_image_horizontal(image_bytes: bytes) -> bytes:
    """Return a 180°-rotated (camera-corrected) JPEG from raw bytes."""
    if not HAS_PIL:
        logger.warning("[OCR] PIL not available — cannot rotate image")
        return image_bytes
    try:
        img = Image.open(BytesIO(image_bytes))
        img = img.rotate(180)
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=95)
        return buffer.getvalue()
    except Exception as exc:
        logger.error(f"[OCR] Image rotation failed: {exc}")
        return image_bytes


def _compress_image_aggressive(image_bytes: bytes, max_bytes: int = 1_500_000) -> bytes:
    """
    Aggressively compress JPEG for OpenRouter (faster throughput).
    Prioritizes speed over quality for OCR task.

    Args:
        image_bytes: Raw JPEG bytes
        max_bytes: Target maximum size (default 1.5 MB for faster processing)

    Returns:
        Compressed JPEG bytes
    """
    if not HAS_PIL:
        logger.warning("[OCR] PIL not available — using original image")
        return image_bytes

    if len(image_bytes) <= max_bytes:
        return image_bytes

    try:
        img = Image.open(BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Aggressive compression for speed
        quality = 75
        width, height = img.size
        target_width = min(1280, width)  # Cap at 1280px for speed

        if width > target_width:
            ratio = target_width / width
            new_height = int(height * ratio)
            img = img.resize((target_width, new_height), Image.Resampling.LANCZOS)

        # Single-pass compression
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        compressed = buffer.getvalue()

        orig_kb = len(image_bytes) / 1024
        comp_kb = len(compressed) / 1024
        logger.info(f"[OCR] Compressed: {orig_kb:.1f}KB → {comp_kb:.1f}KB (quality={quality})")

        return compressed

    except Exception as exc:
        logger.error(f"[OCR] Compression failed: {exc}")
        return image_bytes


# ---------------------------------------------------------------------------
# OpenRouter client (singleton)
# ---------------------------------------------------------------------------

_openrouter_client = None


def _get_openrouter_client():
    global _openrouter_client
    if _openrouter_client is None:
        try:
            from openai import OpenAI
            _openrouter_client = OpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url=_OPENROUTER_BASE_URL,
            )
            logger.info(f"[OCR] OpenRouter client initialized (model: {_OPENROUTER_MODEL})")
        except ImportError:
            logger.error("[OCR] OpenAI library not installed — cannot use OpenRouter")
            raise
    return _openrouter_client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def extract_license_plate(image_bytes: bytes) -> str:
    """
    Extract license plate from raw JPEG bytes using OpenRouter API.

    Returns a normalized plate string (uppercase, no separators).
    Raises OCRFailedException if extraction fails.
    """
    if not settings.OPENROUTER_API_KEY:
        logger.warning("[OCR] OPENROUTER_API_KEY not set — returning mock plate")
        return "KA01AB1234"

    logger.info(f"[OCR] Incoming image: {len(image_bytes)} bytes")

    # Compress image for faster processing
    compressed_bytes = _compress_image_aggressive(image_bytes)
    b64_image = base64.b64encode(compressed_bytes).decode("utf-8")

    client = _get_openrouter_client()
    last_error: Optional[Exception] = None

    for attempt in range(1, _OPENROUTER_MAX_RETRIES + 1):
        try:
            logger.info(f"[OCR][OpenRouter] Attempt {attempt}/{_OPENROUTER_MAX_RETRIES} ({len(compressed_bytes)} bytes)")

            response = client.chat.completions.create(
                model=_OPENROUTER_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _OCR_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=32,
                temperature=0,
            )

            raw: str = response.choices[0].message.content.strip()
            logger.info(f"[OCR][OpenRouter] Raw response: {raw!r}")

            if raw.upper() == "UNREADABLE":
                logger.warning("[OCR][OpenRouter] Model reports plate unreadable")
                break  # retrying won't help a truly unreadable plate

            normalized = _normalize_plate(raw)
            if _is_valid_plate(normalized):
                logger.info(f"[OCR][OpenRouter] Plate extracted: {normalized}")
                return normalized

            logger.warning(f"[OCR][OpenRouter] Response did not match plate pattern: {raw!r}")

        except Exception as exc:
            last_error = exc
            logger.error(f"[OCR][OpenRouter] Attempt {attempt} error: {exc}")

        if attempt < _OPENROUTER_MAX_RETRIES:
            await asyncio.sleep(_OPENROUTER_RETRY_DELAY)

    raise OCRFailedException(
        f"OpenRouter OCR failed after {_OPENROUTER_MAX_RETRIES} attempts. Last error: {last_error}"
    )


def save_captured_image(image_bytes: bytes, filename: str) -> str:
    """Save image bytes to CAPTURED_IMAGES_DIR. Returns the file path string."""
    dir_path = Path(settings.CAPTURED_IMAGES_DIR)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / filename
    file_path.write_bytes(image_bytes)
    return str(file_path)
