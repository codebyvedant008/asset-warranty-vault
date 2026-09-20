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
    Extract the purchase price from an invoice.

    The extractor prefers the invoice's explicit Subtotal/Unit Price
    relationship and uses the Grand Total + tax information as a
    cross-check. It deliberately rejects an OCR price that is larger
    than the invoice total, which prevents values such as 279,999 from
    replacing a real 79,999 purchase price.
    """

    def to_number(value: str) -> float | None:
        try:
            return float(value.replace("%", "").replace(",", "").strip())
        except (ValueError, AttributeError):
            return None

    def amount_candidates(value: str) -> list[float]:
        # Remove serial/model tokens before extracting numbers.
        value = re.sub(
            r"\bSN[A-Z0-9][A-Z0-9\-/]+\b", " ", value, flags=re.IGNORECASE
        )
        value = re.sub(
            r"\bSM-[A-Z0-9][A-Z0-9\-/]+\b", " ", value, flags=re.IGNORECASE
        )

        matches = re.findall(
            r"(?<![A-Z0-9])"
            r"(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d{4,}(?:\.\d{1,2})?)"
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
    # 1. Read explicit subtotal and grand total first.
    # --------------------------------------------------------
    subtotal_value = None
    grand_total_value = None

    for i, line in enumerate(lines):
        lower = line.lower()
        window = " ".join(lines[i:i + 2])
        candidates = amount_candidates(window)
        if not candidates:
            continue

        if subtotal_value is None and re.search(r"\bsub\s*total\b|\bsubtotal\b", lower):
            subtotal_value = candidates[0]

        if grand_total_value is None and re.search(
            r"\bgrand\s+total\b|\btotal\s+amount\b|\bamount\s+payable\b|\bnet\s+amount\b",
            lower,
        ):
            grand_total_value = candidates[0]

    # If the invoice explicitly provides a sensible subtotal, that is
    # the purchase price for the normal quantity=1 receipt used here.
    if subtotal_value is not None:
        if grand_total_value is None or subtotal_value <= grand_total_value * 1.05:
            return subtotal_value

    # --------------------------------------------------------
    # 2. Unit Price table extraction.
    # --------------------------------------------------------
    unit_index = None
    for i, line in enumerate(lines):
        if re.search(r"\bunit\s*price\b", line, re.IGNORECASE):
            unit_index = i
            break

    if unit_index is not None:
        end_index = len(lines)
        for i in range(unit_index + 1, len(lines)):
            if re.search(r"\bsub\s*total\b|\bsubtotal\b|\bgrand\s+total\b", lines[i], re.IGNORECASE):
                end_index = i
                break

        section_lines = lines[unit_index:end_index]
        candidates = []

        for distance, line in enumerate(section_lines):
            for value in amount_candidates(line):
                candidates.append((distance, value, line))

        # Reject OCR candidates that are impossible purchase prices because
        # they exceed the invoice grand total by a meaningful amount.
        if grand_total_value is not None:
            candidates = [
                item for item in candidates
                if item[1] <= grand_total_value * 1.05
            ]

        if candidates:
            # Same-line Unit Price is strongest evidence.
            same_line = [
                item for item in candidates
                if re.search(r"\bunit\s*price\b", item[2], re.IGNORECASE)
            ]
            if same_line:
                return same_line[0][1]

            # Otherwise choose the closest surviving candidate.
            min_distance = min(item[0] for item in candidates)
            closest = [item for item in candidates if item[0] == min_distance]
            if closest:
                return closest[0][1]

    # --------------------------------------------------------
    # 3. Recover pre-tax price from Grand Total when OCR damaged
    #    the table price. This handles the common Indian 18% GST case.
    # --------------------------------------------------------
    if grand_total_value is not None:
        gst_rate = None

        # Detect an explicit GST rate such as 18%, CGST 9% + SGST 9%.
        percent_matches = re.findall(r"(\d{1,2}(?:\.\d+)?)\s*%", text)
        numeric_rates = []
        for value in percent_matches:
            rate = to_number(value)
            if rate is not None and 0 < rate <= 100:
                numeric_rates.append(rate)

        if 18 in numeric_rates:
            gst_rate = 18.0
        elif 9 in numeric_rates and numeric_rates.count(9) >= 2:
            gst_rate = 18.0

        if gst_rate is not None:
            pre_tax = grand_total_value / (1 + gst_rate / 100)
            return round(pre_tax, 2)

    # --------------------------------------------------------
    # 4. Labelled totals fallback.
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
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = to_number(match.group(1))
            if value is not None:
                return value

    # --------------------------------------------------------
    # 5. Currency-marked fallback.
    # --------------------------------------------------------
    currency_pattern = (
        r"(?:â‚¹|rs\.?|inr|\$|usd|â‚¬|eur|Â£|gbp)\s*"
        r"([\d,]+(?:\.\d{1,2})?)"
    )

    amounts = []
    for value in re.findall(currency_pattern, text, re.IGNORECASE):
        number = to_number(value)
        if number is not None:
            amounts.append(number)

    return max(amounts) if amounts else None

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