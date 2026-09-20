import json
import os
import urllib.request
import urllib.error

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, JSONResponse


router = APIRouter(
    prefix="/webhook",
    tags=["WhatsApp"]
)


WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

WHATSAPP_API_VERSION = "v25.0"


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

    if mode == "subscribe" and verify_token == WHATSAPP_VERIFY_TOKEN:
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
async def receive_whatsapp_webhook(request: Request):

    try:
        data = await request.json()

        print("========================================")
        print("WhatsApp webhook received")
        print(json.dumps(data, indent=2))
        print("========================================")

        # -------------------------------------------------
        # Extract incoming WhatsApp message
        # -------------------------------------------------

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

        print(f"Message type: {message_type}")
        print(f"Sender: {sender_phone}")

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

            print("Invoice/receipt image received.")

            reply = (
                "📄 Receipt received!\n\n"
                "I'm processing the image and will "
                "extract the asset and warranty details."
            )

            if sender_phone:
                send_whatsapp_message(
                    sender_phone,
                    reply
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
            content={"status": "processed"},
            status_code=200
        )

    except Exception as error:

        print("========================================")
        print(f"WhatsApp webhook error: {error}")
        print("========================================")

        # Always return 200 so Meta doesn't repeatedly retry
        # the webhook request.

        return JSONResponse(
            content={"status": "error"},
            status_code=200
        )


# ---------------------------------------------------------
# Helper: Send a WhatsApp text message
# ---------------------------------------------------------

def send_whatsapp_message(
    recipient_phone: str,
    message_text: str
):

    if not WHATSAPP_ACCESS_TOKEN:

        print("WHATSAPP_ACCESS_TOKEN is missing.")

        return False

    if not WHATSAPP_PHONE_NUMBER_ID:

        print("WHATSAPP_PHONE_NUMBER_ID is missing.")

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
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
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

            print("WhatsApp message sent:")
            print(response_data)

            return True

    except urllib.error.HTTPError as error:

        error_body = (
            error
            .read()
            .decode("utf-8")
        )

        print("WhatsApp API error:")
        print(error.code)
        print(error_body)

        return False

    except Exception as error:

        print(f"WhatsApp send error: {error}")

        return False