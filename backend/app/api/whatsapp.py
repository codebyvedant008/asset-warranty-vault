import json
import os
import urllib.request
import urllib.error

from datetime import date
from calendar import monthrange
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from backend.app.db.session import SessionLocal
from backend.app.models.assets import Asset
from backend.app.services.ocr_service import extract_text_from_image
from backend.app.services.extraction_service import extract_asset_fields


router = APIRouter(
    prefix="/webhook",
    tags=["WhatsApp"]
)


# ---------------------------------------------------------
# Environment variables
# ---------------------------------------------------------

WHATSAPP_ACCESS_TOKEN = os.getenv(
    "WHATSAPP_ACCESS_TOKEN",
    ""
)

WHATSAPP_PHONE_NUMBER_ID = os.getenv(
    "WHATSAPP_PHONE_NUMBER_ID",
    ""
)

WHATSAPP_VERIFY_TOKEN = os.getenv(
    "WHATSAPP_VERIFY_TOKEN",
    ""
)

WHATSAPP_API_VERSION = "v25.0"


# ---------------------------------------------------------
# Upload directory
# ---------------------------------------------------------

UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# WhatsApp webhook deduplication
# ---------------------------------------------------------
#
# Meta can retry the same webhook event.
# We store already-processing message IDs here.
#
# IMPORTANT:
# The ID is added BEFORE OCR/database processing.
# Therefore, if the same event arrives again while the
# first request is still processing, it will be ignored.
# ---------------------------------------------------------

PROCESSED_MESSAGE_IDS = set()


# ---------------------------------------------------------
# GET /webhook/whatsapp
# Meta uses this endpoint to verify our webhook.
# ---------------------------------------------------------

@router.get("/whatsapp")
async def verify_whatsapp_webhook(
    request: Request
):
    params = request.query_params

    mode = params.get("hub.mode")
    verify_token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if (
        mode == "subscribe"
        and verify_token == WHATSAPP_VERIFY_TOKEN
    ):
        return PlainTextResponse(
            content=challenge or "",
            status_code=200
        )

    return PlainTextResponse(
        content="Forbidden",
        status_code=403
    )


# ---------------------------------------------------------
# POST /webhook/whatsapp
# Meta sends incoming WhatsApp events here.
# ---------------------------------------------------------

@router.post("/whatsapp")
async def receive_whatsapp_webhook(
    request: Request
):

    try:

        data = await request.json()

        print("========================================")
        print("WhatsApp webhook received")
        print(json.dumps(data, indent=2))
        print("========================================")

        entry = data.get("entry", [])

        if not entry:
            return JSONResponse(
                content={"status": "received"},
                status_code=200
            )

        changes = entry[0].get("changes", [])

        if not changes:
            return JSONResponse(
                content={"status": "received"},
                status_code=200
            )

        value = changes[0].get("value", {})

        messages = value.get("messages", [])

        if not messages:
            return JSONResponse(
                content={"status": "received"},
                status_code=200
            )

        message = messages[0]

        message_type = message.get("type")
        sender_phone = message.get("from")

        # -------------------------------------------------
        # UNIQUE WHATSAPP MESSAGE ID
        # -------------------------------------------------

        message_id = message.get("id")

        print(f"Message type: {message_type}")
        print(f"Sender: {sender_phone}")
        print(f"Message ID: {message_id}")

        # -------------------------------------------------
        # DUPLICATE WEBHOOK PROTECTION
        # -------------------------------------------------

        if message_id:

            if message_id in PROCESSED_MESSAGE_IDS:

                print("========================================")
                print(
                    "DUPLICATE WHATSAPP MESSAGE DETECTED"
                )
                print(f"Message ID: {message_id}")
                print(
                    "Ignoring duplicate event."
                )
                print("========================================")

                return JSONResponse(
                    content={
                        "status": "duplicate_ignored",
                        "message_id": message_id
                    },
                    status_code=200
                )

            # IMPORTANT:
            # Mark the message as processed BEFORE doing
            # OCR, extraction, database work, or replying.
            PROCESSED_MESSAGE_IDS.add(message_id)

            print("========================================")
            print(
                "New WhatsApp message ID registered."
            )
            print(f"Message ID: {message_id}")
            print("========================================")

        # -------------------------------------------------
        # Handle text messages
        # -------------------------------------------------

        if message_type == "text":

            message_text = (
                message
                .get("text", {})
                .get("body", "")
                .strip()
            )

            print(f"Message text: {message_text}")

            reply = (
                "👋 Welcome to Asset & Warranty Vault!\n\n"
                "Send me a receipt or invoice photo and "
                "I'll automatically extract the asset "
                "and warranty details."
            )

            if sender_phone:

                send_whatsapp_message(
                    sender_phone,
                    reply
                )

        # -------------------------------------------------
        # Handle image messages
        # -------------------------------------------------

        elif message_type == "image":

            image_data = message.get(
                "image",
                {}
            )

            media_id = image_data.get("id")

            mime_type = image_data.get(
                "mime_type",
                "image/jpeg"
            )

            # Some WhatsApp webhook payloads may contain
            # a direct temporary URL.
            media_url = image_data.get("url")

            print("========================================")
            print("WhatsApp image received")
            print(f"Media ID: {media_id}")
            print(f"MIME type: {mime_type}")
            print(f"Direct media URL: {bool(media_url)}")
            print("========================================")

            if not media_id:

                if sender_phone:

                    send_whatsapp_message(
                        sender_phone,
                        "❌ I received the image, "
                        "but could not find its media ID."
                    )

                return JSONResponse(
                    content={
                        "status": "missing_media_id"
                    },
                    status_code=200
                )

            try:

                # -------------------------------------------------
                # STEP 1: Download image
                # -------------------------------------------------

                saved_path = download_whatsapp_media(
                    media_id,
                    mime_type,
                    media_url
                )

                print("========================================")
                print(
                    "WhatsApp image downloaded successfully"
                )
                print(f"Saved to: {saved_path}")
                print("========================================")

                # -------------------------------------------------
                # STEP 2: OCR
                # -------------------------------------------------

                if sender_phone:

                    send_whatsapp_message(
                        sender_phone,
                        "🔎 Receipt received!\n\n"
                        "I'm reading the invoice and "
                        "extracting the asset details..."
                    )

                ocr_text = run_ocr(
                    saved_path
                )

                print("========================================")
                print("OCR COMPLETED")
                print("========================================")
                print(ocr_text)
                print("========================================")

                if not ocr_text.strip():

                    raise RuntimeError(
                        "OCR returned empty text."
                    )

                # -------------------------------------------------
                # STEP 3: Extract structured fields
                # -------------------------------------------------

                extracted = run_extraction(
                    ocr_text
                )

                print("========================================")
                print("EXTRACTED ASSET DATA")
                print(
                    json.dumps(
                        extracted,
                        indent=2,
                        default=str
                    )
                )
                print("========================================")

                # -------------------------------------------------
                # STEP 4: Save asset to database
                # -------------------------------------------------

                asset = save_asset_to_database(
                    extracted,
                    saved_path
                )

                # -------------------------------------------------
                # STEP 5: Send result to WhatsApp
                # -------------------------------------------------

                if sender_phone:

                    reply = format_asset_reply(
                        extracted,
                        asset
                    )

                    send_whatsapp_message(
                        sender_phone,
                        reply
                    )

            except Exception as error:

                print("========================================")
                print(
                    f"WhatsApp image processing error: {error}"
                )
                print("========================================")

                if sender_phone:

                    send_whatsapp_message(
                        sender_phone,
                        "❌ I received your receipt, "
                        "but something went wrong while "
                        "processing it.\n\n"
                        f"Error: {str(error)[:500]}"
                    )

        # -------------------------------------------------
        # Other message types
        # -------------------------------------------------

        else:

            if sender_phone:

                reply = (
                    "I received your message.\n\n"
                    "Please send a receipt or invoice "
                    "photo to add an asset."
                )

                send_whatsapp_message(
                    sender_phone,
                    reply
                )

        return JSONResponse(
            content={
                "status": "processed"
            },
            status_code=200
        )

    except Exception as error:

        print("========================================")
        print(
            f"WhatsApp webhook error: {error}"
        )
        print("========================================")

        return JSONResponse(
            content={
                "status": "error"
            },
            status_code=200
        )


# =========================================================
# OCR
# =========================================================

def run_ocr(
    image_path: str
) -> str:

    print("Starting OCR...")

    text = extract_text_from_image(
        image_path
    )

    return text or ""


# =========================================================
# EXTRACTION
# =========================================================

def run_extraction(
    ocr_text: str
) -> dict:

    print("Starting structured extraction...")

    result = extract_asset_fields(
        ocr_text
    )

    if result is None:

        raise RuntimeError(
            "Extraction returned no data."
        )

    if not isinstance(result, dict):

        raise RuntimeError(
            "Extraction service must return a dictionary."
        )

    return result


# =========================================================
# DATE HELPERS
# =========================================================

def parse_date_value(
    value
):

    if value is None:
        return None

    if isinstance(value, date):
        return value

    value = str(value).strip()

    if not value:
        return None

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%Y/%m/%d",
        "%d-%m-%y",
        "%d/%m/%y"
    ]

    for fmt in formats:

        try:

            return (
                date.fromisoformat(value)
                if fmt == "%Y-%m-%d"
                else __import__("datetime")
                .datetime
                .strptime(value, fmt)
                .date()
            )

        except ValueError:
            continue

    return None


def add_months(
    original_date: date,
    months: int
) -> date:

    month_index = (
        original_date.month - 1
        + months
    )

    year = (
        original_date.year
        + month_index // 12
    )

    month = (
        month_index % 12
    ) + 1

    day = min(
        original_date.day,
        monthrange(
            year,
            month
        )[1]
    )

    return date(
        year,
        month,
        day
    )


# =========================================================
# SAVE ASSET TO DATABASE
# =========================================================

def save_asset_to_database(
    extracted: dict,
    receipt_path: str
):

    db = SessionLocal()

    try:

        product_name = (
            extracted.get("product_name")
            or "Unknown Product"
        )

        brand = extracted.get(
            "brand"
        )

        model_number = extracted.get(
            "model_number"
        )

        serial_number = extracted.get(
            "serial_number"
        )

        purchase_date = parse_date_value(
            extracted.get("purchase_date")
        )

        purchase_price = extracted.get(
            "purchase_price"
        )

        currency = (
            extracted.get("currency")
            or "INR"
        )

        warranty_months = extracted.get(
            "warranty_months"
        )

        seller = extracted.get(
            "seller"
        )

        invoice_number = extracted.get(
            "invoice_number"
        )

        # -------------------------------------------------
        # Convert numeric values safely.
        # -------------------------------------------------

        if purchase_price is not None:

            try:

                purchase_price = float(
                    purchase_price
                )

            except (
                TypeError,
                ValueError
            ):

                purchase_price = None

        if warranty_months is not None:

            try:

                warranty_months = int(
                    float(warranty_months)
                )

            except (
                TypeError,
                ValueError
            ):

                warranty_months = None

        # -------------------------------------------------
        # Calculate warranty expiry.
        # -------------------------------------------------

        warranty_expiry = None

        if (
            purchase_date
            and warranty_months
            and warranty_months > 0
        ):

            warranty_expiry = add_months(
                purchase_date,
                warranty_months
            )

        # -------------------------------------------------
        # Prevent obvious duplicate entries.
        # -------------------------------------------------

        existing = None

        if serial_number:

            existing = (
                db.query(Asset)
                .filter(
                    Asset.serial_number
                    == serial_number
                )
                .first()
            )

        if (
            existing is None
            and invoice_number
        ):

            existing = (
                db.query(Asset)
                .filter(
                    Asset.invoice_number
                    == invoice_number
                )
                .first()
            )

        # -------------------------------------------------
        # If already exists, update receipt path only.
        # -------------------------------------------------

        if existing:

            print(
                f"Existing asset found: "
                f"ID {existing.id}"
            )

            existing.receipt_path = (
                receipt_path
            )

            db.commit()
            db.refresh(existing)

            return existing

        # -------------------------------------------------
        # Create new asset.
        # -------------------------------------------------

        asset = Asset(
            product_name=product_name,
            brand=brand,
            model_number=model_number,
            serial_number=serial_number,
            purchase_date=purchase_date,
            purchase_price=purchase_price,
            currency=currency,
            warranty_months=warranty_months,
            warranty_expiry=warranty_expiry,
            seller=seller,
            invoice_number=invoice_number,
            receipt_path=receipt_path
        )

        db.add(asset)

        db.commit()

        db.refresh(asset)

        print(
            f"Asset saved successfully. "
            f"Database ID: {asset.id}"
        )

        return asset

    except Exception:

        db.rollback()

        raise

    finally:

        db.close()


# =========================================================
# FORMAT WHATSAPP RESPONSE
# =========================================================

def format_asset_reply(
    extracted: dict,
    asset
) -> str:

    product_name = (
        extracted.get("product_name")
        or "Not detected"
    )

    brand = (
        extracted.get("brand")
        or "Not detected"
    )

    model_number = (
        extracted.get("model_number")
        or "Not detected"
    )

    serial_number = (
        extracted.get("serial_number")
        or "Not detected"
    )

    purchase_date = (
        extracted.get("purchase_date")
        or "Not detected"
    )

    purchase_price = extracted.get(
        "purchase_price"
    )

    currency = (
        extracted.get("currency")
        or "INR"
    )

    warranty_months = (
        extracted.get("warranty_months")
        or "Not detected"
    )

    seller = (
        extracted.get("seller")
        or "Not detected"
    )

    invoice_number = (
        extracted.get("invoice_number")
        or "Not detected"
    )

    # -----------------------------------------------------
    # Format price.
    # -----------------------------------------------------

    if purchase_price is not None:

        try:

            numeric_price = float(
                purchase_price
            )

            if currency.upper() == "INR":

                price_text = (
                    f"₹{numeric_price:,.2f}"
                )

            else:

                price_text = (
                    f"{currency} "
                    f"{numeric_price:,.2f}"
                )

        except (
            TypeError,
            ValueError
        ):

            price_text = str(
                purchase_price
            )

    else:

        price_text = "Not detected"

    # -----------------------------------------------------
    # Warranty expiry.
    # -----------------------------------------------------

    expiry = getattr(
        asset,
        "warranty_expiry",
        None
    )

    if expiry:

        expiry_text = expiry.strftime(
            "%d-%m-%Y"
        )

    else:

        expiry_text = "Not calculated"

    # -----------------------------------------------------
    # Final WhatsApp message.
    # -----------------------------------------------------

    return (
        "✅ *Asset Added Successfully!*\n\n"

        "📦 *Asset Details*\n"
        f"Product: {product_name}\n"
        f"Brand: {brand}\n"
        f"Model: {model_number}\n"
        f"Serial: {serial_number}\n\n"

        "🧾 *Purchase Details*\n"
        f"Purchase Date: {purchase_date}\n"
        f"Price: {price_text}\n"
        f"Seller: {seller}\n"
        f"Invoice: {invoice_number}\n\n"

        "🛡️ *Warranty Details*\n"
        f"Warranty: {warranty_months} months\n"
        f"Warranty Expiry: {expiry_text}\n\n"

        f"💾 Asset ID: {asset.id}\n\n"

        "Your receipt has been processed and "
        "the asset is now saved in "
        "Asset & Warranty Vault."
    )


# =========================================================
# DOWNLOAD WHATSAPP MEDIA
# =========================================================

def download_whatsapp_media(
    media_id: str,
    mime_type: str,
    media_url: str | None = None
):

    if not WHATSAPP_ACCESS_TOKEN:

        raise RuntimeError(
            "WHATSAPP_ACCESS_TOKEN is missing."
        )

    if not WHATSAPP_PHONE_NUMBER_ID:

        raise RuntimeError(
            "WHATSAPP_PHONE_NUMBER_ID is missing."
        )

    # -----------------------------------------------------
    # STEP 1
    #
    # Use the URL supplied by the webhook if available.
    # Otherwise retrieve the temporary media URL from Meta.
    # -----------------------------------------------------

    if not media_url:

        metadata_url = (
            f"https://graph.facebook.com/"
            f"{WHATSAPP_API_VERSION}/"
            f"{media_id}"
        )

        metadata_request = (
            urllib.request.Request(
                metadata_url,
                headers={
                    "Authorization": (
                        f"Bearer "
                        f"{WHATSAPP_ACCESS_TOKEN}"
                    )
                },
                method="GET"
            )
        )

        try:

            with urllib.request.urlopen(
                metadata_request,
                timeout=30
            ) as response:

                metadata = json.loads(
                    response
                    .read()
                    .decode("utf-8")
                )

        except urllib.error.HTTPError as error:

            error_body = (
                error
                .read()
                .decode("utf-8")
            )

            print(
                "Meta media metadata error:"
            )
            print(error.code)
            print(error_body)

            raise RuntimeError(
                "Meta media metadata request "
                f"failed: {error.code}"
            )

        media_url = metadata.get(
            "url"
        )

        if not media_url:

            raise RuntimeError(
                "Meta did not return a media URL."
            )

        print(
            "Media URL retrieved successfully."
        )

    else:

        print(
            "Using media URL supplied "
            "by WhatsApp webhook."
        )

    # -----------------------------------------------------
    # STEP 2
    # Download actual image binary.
    # -----------------------------------------------------

    media_request = (
        urllib.request.Request(
            media_url,
            headers={
                "Authorization": (
                    f"Bearer "
                    f"{WHATSAPP_ACCESS_TOKEN}"
                )
            },
            method="GET"
        )
    )

    try:

        with urllib.request.urlopen(
            media_request,
            timeout=60
        ) as response:

            image_bytes = response.read()

    except urllib.error.HTTPError as error:

        print(
            "Authorized media download failed:"
        )
        print(error.code)

        # -------------------------------------------------
        # Some Meta signed media URLs can be downloaded
        # without explicitly sending the Authorization
        # header. Retry once without it.
        # -------------------------------------------------

        if error.code in (
            401,
            403
        ):

            print(
                "Retrying media download "
                "without Authorization header..."
            )

            unsigned_request = (
                urllib.request.Request(
                    media_url,
                    method="GET"
                )
            )

            try:

                with urllib.request.urlopen(
                    unsigned_request,
                    timeout=60
                ) as response:

                    image_bytes = response.read()

            except urllib.error.HTTPError as retry_error:

                error_body = (
                    retry_error
                    .read()
                    .decode("utf-8")
                )

                print(
                    "Meta media download error:"
                )
                print(
                    retry_error.code
                )
                print(error_body)

                raise RuntimeError(
                    "Media download failed: "
                    f"{retry_error.code}"
                )

        else:

            error_body = (
                error
                .read()
                .decode("utf-8")
            )

            print(
                "Meta media download error:"
            )
            print(error.code)
            print(error_body)

            raise RuntimeError(
                "Media download failed: "
                f"{error.code}"
            )

    # -----------------------------------------------------
    # Determine file extension.
    # -----------------------------------------------------

    extension_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp"
    }

    extension = extension_map.get(
        mime_type,
        ".jpg"
    )

    # -----------------------------------------------------
    # Save image.
    # -----------------------------------------------------

    filename = (
        f"whatsapp_{media_id}"
        f"{extension}"
    )

    file_path = (
        UPLOADS_DIR
        / filename
    )

    with open(
        file_path,
        "wb"
    ) as file:

        file.write(
            image_bytes
        )

    print(
        f"Image saved: {file_path}"
    )

    return str(file_path)


# =========================================================
# SEND WHATSAPP TEXT MESSAGE
# =========================================================

def send_whatsapp_message(
    recipient_phone: str,
    message_text: str
):

    if not WHATSAPP_ACCESS_TOKEN:

        print(
            "WHATSAPP_ACCESS_TOKEN is missing."
        )

        return False

    if not WHATSAPP_PHONE_NUMBER_ID:

        print(
            "WHATSAPP_PHONE_NUMBER_ID is missing."
        )

        return False

    url = (
        f"https://graph.facebook.com/"
        f"{WHATSAPP_API_VERSION}/"
        f"{WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {
            "body": message_text
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(
            payload
        ).encode("utf-8"),
        headers={
            "Authorization": (
                f"Bearer "
                f"{WHATSAPP_ACCESS_TOKEN}"
            ),
            "Content-Type": (
                "application/json"
            )
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            response_data = (
                response
                .read()
                .decode("utf-8")
            )

            print(
                "WhatsApp message sent:"
            )
            print(response_data)

            return True

    except urllib.error.HTTPError as error:

        error_body = (
            error
            .read()
            .decode("utf-8")
        )

        print(
            "WhatsApp API error:"
        )
        print(error.code)
        print(error_body)

        return False

    except Exception as error:

        print(
            f"WhatsApp send error: {error}"
        )

        return False