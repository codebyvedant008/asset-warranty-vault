import os

import pytesseract
from PIL import Image


# ---------------------------------------------------------
# TESSERACT CONFIGURATION
# ---------------------------------------------------------
# Windows:
# Use the installed Tesseract path if it exists.
#
# Cloud Run / Linux:
# Tesseract is installed inside the Docker container and
# is normally available as "tesseract".
# ---------------------------------------------------------

WINDOWS_TESSERACT_PATH = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

if os.path.exists(WINDOWS_TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = (
        WINDOWS_TESSERACT_PATH
    )


# ---------------------------------------------------------
# OCR FUNCTION
# ---------------------------------------------------------

def extract_text_from_image(image_path: str) -> str:
    """
    Extract text from an invoice/receipt image using Tesseract OCR.
    Works on both Windows and Linux/Cloud Run.
    """

    image = Image.open(image_path)

    text = pytesseract.image_to_string(image)

    return text.strip()