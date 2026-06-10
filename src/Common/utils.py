import io
import re
import pytesseract
from PIL import Image


def ocr_numeric_image(image_bytes: bytes) -> str | None:
    """Extract a numeric value from a simple anti-scraping image using Tesseract OCR."""
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert('L')
        text = pytesseract.image_to_string(
            image,
            config='--psm 8 -c tessedit_char_whitelist=0123456789.,'
        )
        cleaned = re.sub(r'[^\d.,]', '', text.strip())
        return cleaned or None
    except Exception:
        return None
