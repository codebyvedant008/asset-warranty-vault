import json
import os
import urllib.request
import urllib.error

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, JSONResponse


router = APIRouter(
    prefix="/webhook",
    tags=["WhatsApp"]
)


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

UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


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

        entry = data.get(
            "entry",
            []
        )

        if not entry:

            return JSONResponse(
                content={
                    "status": "received"
                },
                status_code=200
            )

        changes = entry[0].get(
            "changes",
            []
        )

        if not changes:

            return JSONResponse(
                content={
                    "status": "received"
                },
                status_code=200
            )

        value = changes[0].get(
            "value",
            {}
        )

        messages = value.get(
            "messages",
            []
        )

        if not messages:

            return JSONResponse(
                content={
                    "status": "received"
                },
                status_code=200
            )

        message = messages[0]

        message_type = message.get(
            "type"
        )

        sender_phone = message.get(
            "from"
        )

        print(
            f"Message type: {message_type}"
        )

        print(
            f"Sender: {sender_phone}"
        )


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

            print(
                f"Message text: {message_text}"
            )

            reply = (
                "👋 Welcome to Asset & Warranty Vault!\n\n"
                "Send me a receipt or invoice photo and "
                "I'll help extract the asset and warranty details."
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

            media_id = image_data.get(
                "id"
            )

            mime_type = image_data.get(
                "mime_type",
                "image/jpeg"
            )

            # IMPORTANT:
            # Meta's webhook payload already contains
            # a temporary media URL for the image.
            media_url = image_data.get(
                "url"
            )

            print("========================================")
            print("WhatsApp image received")
            print(
                f"Media ID: {media_id}"
            )
            print(
                f"MIME type: {mime_type}"
            )
            print(
                f"Media URL available: {bool(media_url)}"
            )
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

                saved_path = download_whatsapp_media(
                    media_id=media_id,
                    mime_type=mime_type,
                    media_url=media_url
                )

                print("========================================")
                print(
                    "WhatsApp image downloaded successfully"
                )
                print(
                    f"Saved to: {saved_path}"
                )
                print("========================================")


                if sender_phone:

                    send_whatsapp_message(
                        sender_phone,
                        "📄 Receipt received successfully!\n\n"
                        "The image has been downloaded. "
                        "I'm ready to process the receipt."
                    )


            except Exception as error:

                print("========================================")
                print(
                    f"Image download error: {error}"
                )
                print("========================================")


                if sender_phone:

                    send_whatsapp_message(
                        sender_phone,
                        "❌ I received your receipt, "
                        "but could not download the image."
                    )


        # -------------------------------------------------
        # Other message types
        # -------------------------------------------------

        else:

            if sender_phone:

                reply = (
                    "I received your message.\n\n"
                    "Please send a receipt or invoice photo "
                    "to add an asset."
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


# ---------------------------------------------------------
# Download WhatsApp media
# ---------------------------------------------------------

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
    # Step 1:
    # Prefer the media URL already provided by Meta
    # inside the webhook payload.
    # -----------------------------------------------------

    if media_url:

        print(
            "Using media URL supplied by WhatsApp webhook."
        )

    else:

        # -------------------------------------------------
        # Fallback:
        # Retrieve media URL from Meta using media ID.
        #
        # IMPORTANT:
        # Do NOT append phone_number_id to this request.
        # -------------------------------------------------

        metadata_url = (
            f"https://graph.facebook.com/"
            f"{WHATSAPP_API_VERSION}/"
            f"{media_id}"
        )

        metadata_request = urllib.request.Request(
            metadata_url,
            headers={
                "Authorization": (
                    f"Bearer {WHATSAPP_ACCESS_TOKEN}"
                )
            },
            method="GET"
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

            print(
                error.code
            )

            print(
                error_body
            )

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
            "Media URL retrieved from Meta."
        )


    # -----------------------------------------------------
    # Step 2:
    # Download actual image binary.
    # -----------------------------------------------------

    image_bytes = None


    # First attempt:
    # Use Authorization header.

    media_request = urllib.request.Request(
        media_url,
        headers={
            "Authorization": (
                f"Bearer {WHATSAPP_ACCESS_TOKEN}"
            )
        },
        method="GET"
    )


    try:

        with urllib.request.urlopen(
            media_request,
            timeout=60
        ) as response:

            image_bytes = response.read()

            print(
                "Image downloaded using "
                "authenticated request."
            )


    except urllib.error.HTTPError as error:

        print(
            "Authenticated media download failed:"
        )

        print(
            error.code
        )


        # -------------------------------------------------
        # Some WhatsApp lookaside URLs are already signed.
        # Retry without Authorization.
        # -------------------------------------------------

        if error.code in (
            401,
            403
        ):

            print(
                "Retrying media download "
                "without Authorization header..."
            )

            unsigned_request = urllib.request.Request(
                media_url,
                method="GET"
            )

            try:

                with urllib.request.urlopen(
                    unsigned_request,
                    timeout=60
                ) as response:

                    image_bytes = response.read()

                    print(
                        "Image downloaded successfully "
                        "using signed media URL."
                    )

            except urllib.error.HTTPError as retry_error:

                retry_body = (
                    retry_error
                    .read()
                    .decode("utf-8")
                )

                print(
                    "Media download retry failed:"
                )

                print(
                    retry_error.code
                )

                print(
                    retry_body
                )

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

            print(
                error.code
            )

            print(
                error_body
            )

            raise RuntimeError(
                "Media download failed: "
                f"{error.code}"
            )


    # -----------------------------------------------------
    # Make sure we actually received image data.
    # -----------------------------------------------------

    if not image_bytes:

        raise RuntimeError(
            "Downloaded media was empty."
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
        UPLOADS_DIR /
        filename
    )


    with open(
        file_path,
        "wb"
    ) as file:

        file.write(
            image_bytes
        )


    print(
        f"Image saved successfully: {file_path}"
    )

    return str(
        file_path
    )


# ---------------------------------------------------------
# Helper: Send a WhatsApp text message
# ---------------------------------------------------------

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
                f"Bearer {WHATSAPP_ACCESS_TOKEN}"
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

            print(
                response_data
            )

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

        print(
            error.code
        )

        print(
            error_body
        )

        return False


    except Exception as error:

        print(
            f"WhatsApp send error: {error}"
        )

        return False