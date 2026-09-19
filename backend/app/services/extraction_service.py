import re
from datetime import datetime


def clean_text(text: str) -> str:
    """
    Clean OCR text while keeping useful characters.
    """

    text = text.replace("\r", "\n")

    # Normalize spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Normalize excessive blank lines
    text = re.sub(r"\n+", "\n", text)

    return text.strip()


def get_lines(text: str) -> list[str]:
    """
    Return cleaned non-empty OCR lines.
    """

    return [
        line.strip()
        for line in clean_text(text).split("\n")
        if line.strip()
    ]


# ============================================================
# CURRENCY
# ============================================================

def extract_currency(text: str) -> str:
    """
    Detect invoice currency.

    Indian invoices may lose the ₹ symbol during OCR,
    so we also check for GST-related indicators and
    Indian location indicators.
    """

    upper_text = text.upper()

    indian_indicators = [
        "INR",
        "₹",
        "RS.",
        "RS ",
        "CGST",
        "SGST",
        "GSTIN",
        "GST",
        "MUMBAI",
        "MAHARASHTRA",
    ]

    for indicator in indian_indicators:
        if indicator in upper_text:
            return "INR"

    if "$" in text or "USD" in upper_text:
        return "USD"

    if "€" in text or "EUR" in upper_text:
        return "EUR"

    if "£" in text or "GBP" in upper_text:
        return "GBP"

    # Default for this application
    return "INR"


# ============================================================
# PRICE
# ============================================================

def extract_price(text: str) -> float | None:
    """
    Extract purchase price.

    Priority:
    1. Grand Total
    2. Total Amount
    3. Amount Payable
    4. Net Amount
    5. Total
    6. Largest currency amount
    """

    total_patterns = [
        r"(?:grand\s+total|total\s+amount|amount\s+payable|net\s+amount)"
        r"\s*[:\-]?\s*(?:₹|rs\.?|inr|\$|usd|€|eur|£|gbp)?\s*"
        r"([\d,]+(?:\.\d{1,2})?)",

        r"(?:total)"
        r"\s*[:\-]?\s*(?:₹|rs\.?|inr|\$|usd|€|eur|£|gbp)?\s*"
        r"([\d,]+(?:\.\d{1,2})?)",
    ]

    for pattern in total_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            try:
                return float(
                    match.group(1).replace(",", "")
                )

            except ValueError:
                pass

    # Currency marked amounts
    currency_pattern = (
        r"(?:₹|rs\.?|inr|\$|usd|€|eur|£|gbp)\s*"
        r"([\d,]+(?:\.\d{1,2})?)"
    )

    matches = re.findall(
        currency_pattern,
        text,
        re.IGNORECASE
    )

    amounts = []

    for value in matches:

        try:
            amounts.append(
                float(value.replace(",", ""))
            )

        except ValueError:
            continue

    if amounts:
        return max(amounts)

    return None


# ============================================================
# DATE
# ============================================================

def extract_date(text: str) -> str | None:
    """
    Extract invoice/purchase date.

    Supported:
    DD/MM/YYYY
    DD-MM-YYYY
    DD.MM.YYYY
    """

    patterns = [
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
        r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b",
        r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if match:

            day, month, year = match.groups()

            try:

                date_obj = datetime(
                    int(year),
                    int(month),
                    int(day)
                )

                return date_obj.strftime(
                    "%Y-%m-%d"
                )

            except ValueError:
                continue

    return None


# ============================================================
# INVOICE NUMBER
# ============================================================

def extract_invoice_number(text: str) -> str | None:
    """
    Extract invoice number.

    Examples:
    INV-TEST-2026-0918
    INV/2026/001
    Invoice No: ABC123
    """

    patterns = [

        r"(?:invoice\s*(?:no|number|#)?\.?)"
        r"\s*[:\-]?\s*"
        r"([A-Z0-9][A-Z0-9\-\/]+)",

        r"\b(INV[-\/][A-Z0-9\-\/]+)\b",
    ]

    invalid_values = {
        "NO",
        "NUMBER",
        "DATE",
        "PRICE",
        "TOTAL",
        "INVOICE",
        "VAT",
        "GST",
        "TECH",
        "VATECH",
    }

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            re.IGNORECASE
        )

        for value in matches:

            value = value.strip()

            if value.upper() in invalid_values:
                continue

            # Invoice numbers should normally contain a digit.
            if any(
                char.isdigit()
                for char in value
            ):
                return value

    return None


# ============================================================
# WARRANTY
# ============================================================

def extract_warranty(text: str) -> int | None:
    """
    Extract warranty duration in months.
    """

    patterns = [

        r"warranty\s*(?:period)?\s*[:\-]?\s*"
        r"(\d+)\s*months?",

        r"(\d+)\s*months?\s*warranty",

        r"warranty\s*[:\-]?\s*(\d+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return int(
                match.group(1)
            )

    return None


# ============================================================
# SERIAL NUMBER
# ============================================================

def extract_serial_number(text: str) -> str | None:
    """
    Extract complete serial number.

    Handles:
    Serial No: SN123456
    S/N: SN123456
    SN: SN123456
    Table-style invoice serial numbers
    """

    lines = get_lines(text)

    # --------------------------------------------------------
    # TABLE STYLE
    # --------------------------------------------------------

    for line in lines:

        # Typical serial number format
        match = re.search(
            r"\b(SN[A-Z0-9][A-Z0-9\-\/]+)\b",
            line,
            re.IGNORECASE
        )

        if match:

            return match.group(1).upper()

    # --------------------------------------------------------
    # EXPLICIT SERIAL LABEL
    # --------------------------------------------------------

    patterns = [

        r"serial\s*(?:no|number|#)?\.?\s*[:\-]?\s*"
        r"(SN[A-Z0-9][A-Z0-9\-\/]+)",

        r"\bS\/N\s*[:\-]?\s*"
        r"(SN[A-Z0-9][A-Z0-9\-\/]+)",

        r"\bSN\s*[:\-]?\s*"
        r"(SN[A-Z0-9][A-Z0-9\-\/]+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            return match.group(1).upper()

    return None


# ============================================================
# MODEL NUMBER
# ============================================================

def extract_model_number(text: str) -> str | None:
    """
    Extract model number.

    Handles:
    Model No: SM-S931B
    Model Number: SM-S931B
    Model: SM-S931B
    Samsung-style SM-XXXX model numbers
    """

    lines = get_lines(text)

    # --------------------------------------------------------
    # TABLE STYLE
    # --------------------------------------------------------

    for i, line in enumerate(lines):

        lower_line = line.lower()

        if (
            "model no" in lower_line
            and "serial no" in lower_line
        ):

            # Search following lines
            for next_line in lines[i + 1:i + 4]:

                match = re.search(
                    r"\b(SM-[A-Z0-9\-]+)\b",
                    next_line,
                    re.IGNORECASE
                )

                if match:

                    return match.group(1).upper()

    # --------------------------------------------------------
    # EXPLICIT MODEL LABEL
    # --------------------------------------------------------

    patterns = [

        r"model\s*(?:no|number)\s*\.?\s*[:\-]?\s*"
        r"([A-Z0-9][A-Z0-9\-\/]+)",

        r"model\s*\.?\s*[:\-]\s*"
        r"([A-Z0-9][A-Z0-9\-\/]+)",

        # Samsung model fallback
        r"\b(SM-[A-Z0-9\-]+)\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            value = match.group(1).strip()

            # Don't return OCR header words
            if value.lower() in {
                "serial",
                "brand",
                "product",
                "number",
                "no",
            }:
                continue

            return value.upper()

    return None


# ============================================================
# BRAND
# ============================================================

def extract_brand(text: str) -> str | None:
    """
    Detect common product brands.
    """

    brands = [

        "Samsung",
        "Apple",
        "Sony",
        "LG",
        "Dell",
        "HP",
        "Lenovo",
        "Asus",
        "Acer",
        "OnePlus",
        "Xiaomi",
        "Google",
        "Microsoft",
        "Canon",
        "Nikon",
        "Bosch",
        "Philips",
        "Panasonic",
        "Whirlpool",
        "Haier",
        "Oppo",
        "Vivo",
        "Realme",
        "Nothing",
    ]

    lower_text = text.lower()

    for brand in brands:

        if brand.lower() in lower_text:
            return brand

    return None


# ============================================================
# SELLER
# ============================================================

def extract_seller(text: str) -> str | None:
    """
    Extract seller/company name.

    First checks explicit seller labels.
    Then checks the beginning of the invoice.
    """

    lines = get_lines(text)

    # --------------------------------------------------------
    # EXPLICIT SELLER LABEL
    # --------------------------------------------------------

    patterns = [
        r"(?:seller|vendor|store|merchant)"
        r"\s*[:\-]\s*(.+)",
    ]

    for line in lines:

        for pattern in patterns:

            match = re.search(
                pattern,
                line,
                re.IGNORECASE
            )

            if match:

                value = match.group(1).strip()

                if value:
                    return value

    # --------------------------------------------------------
    # COMPANY NAME NEAR TOP
    # --------------------------------------------------------

    ignored = {
        "sample",
        "not a real invoice",
        "tax invoice",
        "invoice",
        "customer",
        "invoice no",
        "invoice date",
    }

    for line in lines[:8]:

        lower_line = line.lower()

        if any(
            word in lower_line
            for word in ignored
        ):
            continue

        # Skip address lines
        if re.search(
            r"\b\d{6}\b",
            line
        ):
            continue

        # Skip email
        if "@" in line:
            continue

        # Skip phone numbers
        if re.search(
            r"\+?\d[\d\s\-]{8,}",
            line
        ):
            continue

        # Skip table headers
        if any(
            word in lower_line
            for word in [
                "product",
                "brand",
                "model",
                "serial",
                "quantity",
                "unit price",
            ]
        ):
            continue

        if len(line) >= 3:

            return line.strip()

    return None


# ============================================================
# PRODUCT NAME
# ============================================================

def extract_product_name(text: str) -> str | None:
    """
    Extract product name from normal and table-style invoices.
    """

    lines = get_lines(text)

    # --------------------------------------------------------
    # TABLE STYLE INVOICE
    # --------------------------------------------------------

    for i, line in enumerate(lines):

        lower_line = line.lower()

        if (
            "product" in lower_line
            and "brand" in lower_line
            and "model" in lower_line
            and "serial" in lower_line
        ):

            # Product information is normally
            # on the next one or two lines.

            for product_line in lines[i + 1:i + 3]:

                # Ignore obvious table headers
                if product_line.lower() in {
                    "brand",
                    "model",
                    "serial",
                }:
                    continue

                # OCR correction:
                # Galaxy $25 -> Galaxy S25
                product_line = re.sub(
                    r"\bGalaxy\s+\$25\b",
                    "Galaxy S25",
                    product_line,
                    flags=re.IGNORECASE
                )

                # OCR correction:
                # Galaxy 25 -> Galaxy S25
                product_line = re.sub(
                    r"\bGalaxy\s+25\b",
                    "Galaxy S25",
                    product_line,
                    flags=re.IGNORECASE
                )

                # If the line contains Samsung Galaxy,
                # extract only the product name.
                samsung_match = re.search(
                    r"(Samsung\s+Galaxy\s+"
                    r"(?:S|\$)?25"
                    r"(?:\s+\d+GB)?)",
                    product_line,
                    re.IGNORECASE
                )

                if samsung_match:

                    product = samsung_match.group(1)

                    product = re.sub(
                        r"\$25",
                        "S25",
                        product,
                        flags=re.IGNORECASE
                    )

                    return product.strip()

                # If it looks like a product line,
                # return it instead of returning "Brand".
                if (
                    len(product_line) >= 5
                    and product_line.lower()
                    not in {
                        "brand",
                        "model",
                        "serial",
                        "quantity",
                        "unit price",
                    }
                ):

                    # Don't return pure numbers
                    if not re.fullmatch(
                        r"[\d\s.,]+",
                        product_line
                    ):
                        return product_line.strip()

    # --------------------------------------------------------
    # EXPLICIT PRODUCT LABEL
    # --------------------------------------------------------

    patterns = [

        r"product\s*[:\-]\s*"
        r"([A-Za-z0-9][A-Za-z0-9 .+\-]+?)"
        r"(?=\s+(?:brand|model|serial|quantity|qty|unit|price)\b|$)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            value = match.group(1).strip()

            if value.lower() in {
                "brand",
                "model",
                "serial",
                "quantity",
                "price",
            }:
                continue

            return value

    # --------------------------------------------------------
    # SAMSUNG FALLBACK
    # --------------------------------------------------------

    samsung_pattern = (
        r"(Samsung\s+Galaxy\s+"
        r"(?:S|\$)?25"
        r"(?:\s+\d+GB)?)"
    )

    match = re.search(
        samsung_pattern,
        text,
        re.IGNORECASE
    )

    if match:

        product = match.group(1)

        product = re.sub(
            r"\$25",
            "S25",
            product,
            flags=re.IGNORECASE
        )

        return product.strip()

    return None


# ============================================================
# MAIN EXTRACTION FUNCTION
# ============================================================

def extract_asset_fields(text: str) -> dict:
    """
    Convert OCR text into structured asset information.
    """

    text = clean_text(text)

    return {
        "product_name": extract_product_name(text),
        "brand": extract_brand(text),
        "model_number": extract_model_number(text),
        "serial_number": extract_serial_number(text),
        "purchase_date": extract_date(text),
        "purchase_price": extract_price(text),
        "currency": extract_currency(text),
        "seller": extract_seller(text),
        "invoice_number": extract_invoice_number(text),
        "warranty_months": extract_warranty(text),
    }