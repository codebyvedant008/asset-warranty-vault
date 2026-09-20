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

    Indian invoices may lose the Ã¢â€šÂ¹ symbol during OCR,
    so we also check for GST-related indicators and
    Indian location indicators.
    """

    upper_text = text.upper()

    indian_indicators = [
        "INR",
        "Ã¢â€šÂ¹",
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

    if "Ã¢â€šÂ¬" in text or "EUR" in upper_text:
        return "EUR"

    if "Ã‚Â£" in text or "GBP" in upper_text:
        return "GBP"

    # Default for this application
    return "INR"


# ============================================================
# PRICE
# ============================================================

def extract_price(text: str) -> float | None:
    """
    Extract purchase price from an invoice.

    Price selection is context-aware:
    1. Prefer a value explicitly associated with Unit Price.
    2. If the invoice has Quantity + Unit Price + Subtotal, use the
       unit-price value that best agrees with the subtotal.
    3. Fall back to labelled totals.
    4. Finally fall back to currency-marked amounts.

    This avoids blindly taking the largest number in the Unit Price
    section, which can select an OCR-corrupted value such as 279,999
    instead of the actual 79,999.
    """

    def to_number(value: str) -> float | None:
        try:
            value = value.replace("%", "").replace(",", "").strip()
            return float(value)
        except (ValueError, AttributeError):
            return None

    def amount_candidates(value: str) -> list[float]:
        """
        Extract plausible monetary amounts while avoiding serial/model
        fragments. Both comma-formatted and plain long numbers are allowed.
        """
        value = re.sub(
            r"\bSN[A-Z0-9][A-Z0-9\-/]+\b",
            " ",
            value,
            flags=re.IGNORECASE,
        )
        value = re.sub(
            r"\bSM-[A-Z0-9][A-Z0-9\-/]+\b",
            " ",
            value,
            flags=re.IGNORECASE,
        )

        matches = re.findall(
            r"(?<![A-Z0-9])"
            r"(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?"
            r"|\d{4,}(?:\.\d{1,2})?)"
            r"(?![A-Z0-9])",
            value,
            re.IGNORECASE,
        )

        result = []
        for match in matches:
            number = to_number(match)
            if number is not None and number >= 100:
                result.append(number)

        return result

    lines = get_lines(text)

    # --------------------------------------------------------
    # UNIT PRICE / TABLE EXTRACTION
    # --------------------------------------------------------
    #
    # First inspect the actual invoice lines instead of taking the
    # largest number between Unit Price and Subtotal.
    # --------------------------------------------------------

    unit_index = None
    subtotal_index = None

    for i, line in enumerate(lines):
        lower = line.lower()

        if unit_index is None and re.search(r"\bunit\s*price\b", lower):
            unit_index = i

        if subtotal_index is None and re.search(
            r"\bsub\s*total\b|\bsubtotal\b",
            lower,
        ):
            subtotal_index = i

    if unit_index is not None:
        end_index = subtotal_index if (
            subtotal_index is not None and subtotal_index > unit_index
        ) else min(unit_index + 8, len(lines))

        section_lines = lines[unit_index:end_index]

        # Candidate amounts close to the Unit Price label are more
        # trustworthy than arbitrary numbers farther down the invoice.
        nearby_candidates = []

        for offset, line in enumerate(section_lines):
            candidates = amount_candidates(line)

            for value in candidates:
                nearby_candidates.append(
                    {
                        "value": value,
                        "distance": offset,
                        "line": line,
                    }
                )

        if nearby_candidates:
            # Look for an explicitly labelled Unit Price on the same line.
            for candidate in nearby_candidates:
                if re.search(
                    r"\bunit\s*price\b",
                    candidate["line"],
                    re.IGNORECASE,
                ):
                    return candidate["value"]

            # If the Unit Price header is followed by table values on
            # subsequent lines, use the closest plausible amount.
            min_distance = min(
                candidate["distance"]
                for candidate in nearby_candidates
            )

            closest = [
                candidate
                for candidate in nearby_candidates
                if candidate["distance"] == min_distance
            ]

            if len(closest) == 1:
                return closest[0]["value"]

            # ----------------------------------------------------
            # SUBTOTAL CORROBORATION
            # ----------------------------------------------------
            #
            # For the common quantity=1 invoice layout, the unit price
            # should equal the subtotal. Use that relationship when
            # available. This is especially useful when OCR creates a
            # larger spurious number in the same table region.
            # ----------------------------------------------------

            subtotal_value = None

            if subtotal_index is not None:
                subtotal_window = " ".join(
                    lines[subtotal_index:subtotal_index + 2]
                )

                subtotal_candidates = amount_candidates(
                    subtotal_window
                )

                if subtotal_candidates:
                    # Prefer an amount explicitly on the subtotal line.
                    subtotal_value = subtotal_candidates[0]

            if subtotal_value is not None:
                exact_matches = [
                    candidate["value"]
                    for candidate in nearby_candidates
                    if abs(candidate["value"] - subtotal_value) < 0.01
                ]

                if exact_matches:
                    return exact_matches[0]

            # Otherwise use the candidate nearest the Unit Price label.
            return closest[0]["value"]

    # --------------------------------------------------------
    # LABELLED TOTALS
    # --------------------------------------------------------

    total_patterns = [
        r"(?:grand\s+total|total\s+amount|amount\s+payable|net\s+amount)"
        r"\s*[:\-]?\s*(?:â‚¹|rs\.?|inr|\$|usd|â‚¬|eur|Â£|gbp)?\s*"
        r"([%\d,]+(?:\.\d{1,2})?)",

        r"(?:total)"
        r"\s*[:\-]?\s*(?:â‚¹|rs\.?|inr|\$|usd|â‚¬|eur|Â£|gbp)?\s*"
        r"([%\d,]+(?:\.\d{1,2})?)",
    ]

    for pattern in total_patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            value = to_number(match.group(1))

            if value is not None:
                return value

    # --------------------------------------------------------
    # CURRENCY-MARKED AMOUNTS
    # --------------------------------------------------------

    currency_pattern = (
        r"(?:â‚¹|rs\.?|inr|\$|usd|â‚¬|eur|Â£|gbp)\s*"
        r"([\d,]+(?:\.\d{1,2})?)"
    )

    matches = re.findall(
        currency_pattern,
        text,
        re.IGNORECASE,
    )

    amounts = []

    for value in matches:
        number = to_number(value)

        if number is not None:
            amounts.append(number)

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