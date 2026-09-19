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

        return JSONResponse(
            content={"status": "received"},
            status_code=200
        )

    except Exception as error:
        print(f"WhatsApp webhook error: {error}")

        # Always return 200 to prevent Meta from repeatedly
        # retrying malformed events.
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
        with urllib.request.urlopen(request, timeout=30) as response:
            response_data = response.read().decode("utf-8")

            print("WhatsApp message sent:")
            print(response_data)

            return True

    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8")

        print("WhatsApp API error:")
        print(error.code)
        print(error_body)

        return False

    except Exception as error:
        print(f"WhatsApp send error: {error}")

        return False