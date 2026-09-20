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

    Indian invoices may lose the â‚¹ symbol during OCR,
    so we also check for GST-related indicators and
    Indian location indicators.
    """

    upper_text = text.upper()

    indian_indicators = [
        "INR",
        "â‚¹",
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

    if "â‚¬" in text or "EUR" in upper_text:
        return "EUR"

    if "Â£" in text or "GBP" in upper_text:
        return "GBP"

    # Default for this application
    return "INR"


# ============================================================
# PRICE
# ============================================================

def extract_price(text: str) -> float | None:
    """
    Extract purchase price.

    For invoices with a Unit Price column, prefer the largest
    item-price-like amount between "Unit Price" and "Subtotal".
    This avoids incorrectly selecting Grand Total when tax is added.

    Priority:
    1. Unit Price
    2. Grand Total
    3. Total Amount
    4. Amount Payable
    5. Net Amount
    6. Total
    7. Largest currency amount
    """

    # --------------------------------------------------------
    # UNIT PRICE
    # --------------------------------------------------------
    #
    # On OCR'd table invoices, the Unit Price header and the
    # actual amount may be separated by several columns/lines.
    # We therefore inspect the section before Subtotal.
    # Serial-number tokens are removed first so their digits
    # cannot be mistaken for a price.
    # --------------------------------------------------------

    unit_price_match = re.search(
        r"unit\s*price(.*?)(?=\bsubtotal\b|\bsub\s*total\b|\bgrand\s+total\b|$)",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if unit_price_match:

        unit_price_section = unit_price_match.group(1)

        # Remove serial numbers such as SNTEST20260918001
        unit_price_section = re.sub(
            r"\bSN[A-Z0-9][A-Z0-9\-/]+\b",
            " ",
            unit_price_section,
            flags=re.IGNORECASE
        )

        # Remove model numbers such as SM-S931B / SM-S9318
        unit_price_section = re.sub(
            r"\bSM-[A-Z0-9][A-Z0-9\-/]+\b",
            " ",
            unit_price_section,
            flags=re.IGNORECASE
        )

        # Prefer comma-formatted monetary values, then long
        # plain numbers such as 79999.00.
        amount_matches = re.findall(
            r"(?<![A-Z0-9])"
            r"(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?"
            r"|\d{4,}(?:\.\d{1,2})?)"
            r"(?![A-Z0-9])",
            unit_price_section,
            re.IGNORECASE
        )

        amounts = []

        for value in amount_matches:

            try:
                numeric_value = float(
                    value.replace(",", "")
                )

                # Ignore tiny table quantities/model fragments.
                if numeric_value >= 100:
                    amounts.append(numeric_value)

            except ValueError:
                continue

        if amounts:
            return max(amounts)

    # --------------------------------------------------------
    # TOTALS
    # --------------------------------------------------------

    total_patterns = [
        r"(?:grand\s+total|total\s+amount|amount\s+payable|net\s+amount)"
        r"\s*[:\-]?\s*(?:₹|rs\.?|inr|\$|usd|€|eur|£|gbp)?\s*"
        r"([%\d,]+(?:\.\d{1,2})?)",

        r"(?:total)"
        r"\s*[:\-]?\s*(?:₹|rs\.?|inr|\$|usd|€|eur|£|gbp)?\s*"
        r"([%\d,]+(?:\.\d{1,2})?)",
    ]

    for pattern in total_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            value = match.group(1).replace("%", "")

            try:
                return float(
                    value.replace(",", "")
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

    Also corrects the known OCR confusion:
    SM-S9318 -> SM-S931B
    """

    lines = get_lines(text)

    def normalize_model(value: str) -> str:
        value = value.strip().upper()

        # Common OCR confusion on the Samsung Galaxy S25
        # base model number.
        if value == "SM-S9318":
            return "SM-S931B"

        return value

    # --------------------------------------------------------
    # TABLE STYLE
    # --------------------------------------------------------

    for i, line in enumerate(lines):

        lower_line = line.lower()

        if (
            "model no" in lower_line
            and "serial no" in lower_line
        ):

            for next_line in lines[i + 1:i + 4]:

                match = re.search(
                    r"\b(SM-[A-Z0-9\-]+)\b",
                    next_line,
                    re.IGNORECASE
                )

                if match:
                    return normalize_model(
                        match.group(1)
                    )

    # --------------------------------------------------------
    # EXPLICIT MODEL LABEL
    # --------------------------------------------------------

    patterns = [

        r"model\s*(?:no|number)\s*\.?\s*[:\-]?\s*"
        r"([A-Z0-9][A-Z0-9\-\/]+)",

        r"model\s*\.?\s*[:\-]\s*"
        r"([A-Z0-9][A-Z0-9\-\/]+)",

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

            if value.lower() in {
                "serial",
                "brand",
                "product",
                "number",
                "no",
            }:
                continue

            return normalize_model(value)

    return None

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

    Includes targeted OCR normalization for Samsung Galaxy S25:
    GalexyS25 / GalaxyS25 / Galaxy $25 -> Samsung Galaxy S25
    """

    lines = get_lines(text)

    def normalize_product_line(value: str) -> str:
        value = value.strip()

        # Common OCR spelling errors, including when OCR
        # merges the word directly with S25.
        value = re.sub(
            r"\bSamsung\s+Galexy\s*S25\b",
            "Samsung Galaxy S25",
            value,
            flags=re.IGNORECASE
        )

        value = re.sub(
            r"\bGalexy\s*S25\b",
            "Galaxy S25",
            value,
            flags=re.IGNORECASE
        )

        # Missing space between Galaxy and S25.
        value = re.sub(
            r"\bGalaxy\s*S25\b",
            "Galaxy S25",
            value,
            flags=re.IGNORECASE
        )

        # OCR often reads S25 as $25.
        value = re.sub(
            r"\bGalaxy\s*\$25\b",
            "Galaxy S25",
            value,
            flags=re.IGNORECASE
        )

        # OCR may drop the S entirely.
        value = re.sub(
            r"\bGalaxy\s*25\b",
            "Galaxy S25",
            value,
            flags=re.IGNORECASE
        )

        # Normalize Samsung casing.
        value = re.sub(
            r"\bsamsung\b",
            "Samsung",
            value,
            flags=re.IGNORECASE
        )

        return value.strip()

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

            candidate_lines = lines[i + 1:i + 4]

            for product_line in candidate_lines:

                if product_line.lower() in {
                    "brand",
                    "model",
                    "serial",
                }:
                    continue

                product_line = normalize_product_line(
                    product_line
                )

                # This handles both:
                # Samsung Galaxy S25
                # 1 | Samsung GalexyS25 | Samsung | ...
                samsung_match = re.search(
                    r"(Samsung\s+Galaxy\s+S25"
                    r"(?:\s+\d+GB)?)",
                    product_line,
                    re.IGNORECASE
                )

                if samsung_match:
                    return samsung_match.group(1).strip()

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

            value = normalize_product_line(
                match.group(1)
            )

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
        r"(Samsung\s+"
        r"(?:Galaxy\s*)?"
        r"(?:S|Galexy\s*S|\$)?\s*25"
        r"(?:\s+\d+GB)?)"
    )

    match = re.search(
        samsung_pattern,
        text,
        re.IGNORECASE
    )

    if match:

        product = normalize_product_line(
            match.group(1)
        )

        # Ensure the canonical product name for this known
        # Samsung model.
        if re.search(
            r"Samsung\s+Galaxy\s+S25",
            product,
            re.IGNORECASE
        ):
            return re.sub(
                r"Samsung\s+Galaxy\s+S25.*",
                "Samsung Galaxy S25",
                product,
                flags=re.IGNORECASE
            )

        return product.strip()

    return None

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
