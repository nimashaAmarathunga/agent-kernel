import os
import logging
import httpx

logger = logging.getLogger("ak.whatsapp_helper")

async def send_whatsapp_message(to_number: str, text: str) -> bool:
    """
    Send a WhatsApp message using the WhatsApp Cloud API.
    If credentials are not found, falls back to logging the message (simulated mode).
    """
    if not to_number or to_number == "UNKNOWN_NUMBER":
        logger.warning("No valid mobile number provided. Skipping notification.")
        return False

    access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    api_version = os.environ.get("WHATSAPP_API_VERSION", "v24.0")

    if not access_token or not phone_number_id:
        logger.info(f"WhatsApp credentials not configured. Simulated message to {to_number}:\n{text}")
        return True

    # Best-effort sanitization of phone number (e.g. remove spaces, plus sign)
    clean_number = "".join(filter(str.isdigit, to_number))
    
    url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_number,
        "type": "text",
        "text": {"body": text}
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"WhatsApp message sent to {clean_number} successfully.")
            return True
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to send WhatsApp message to {clean_number}: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Error sending WhatsApp message to {clean_number}: {e}")
        return False

def format_date(dt):
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m-%d")
    return str(dt).split(" ")[0]

async def notify_booking_confirmed(booking: dict):
    """
    Constructs and sends a structured confirmation message.
    """
    mobile = booking.get("mobileNumber")
    
    message = f"""🏨 *GovStay Booking Confirmed* 🏨

*Booking ID:* {booking.get('bookingId', 'N/A')}
*Property:* {booking.get('bungalow_name', 'N/A')}, {booking.get('location', 'N/A')}
*Room:* {booking.get('roomNumber', 'Entire Bungalow')} ({booking.get('roomType', 'N/A')})
*Dates:* {format_date(booking.get('fromDate'))} to {format_date(booking.get('toDate'))}
*Total Cost:* LKR {booking.get('totalCost', 0)}

*Caretaker Info:*
👤 Name: {booking.get('caretaker_name', 'N/A')}
📞 Phone: {booking.get('caretaker_phone', 'N/A')}

Your payment has been successfully verified. Please present this message at check-in.
"""
    await send_whatsapp_message(mobile, message)

async def notify_booking_rejected(booking: dict, reason: str):
    """
    Constructs and sends a structured rejection message.
    """
    mobile = booking.get("mobileNumber")
    
    message = f"""❌ *GovStay Booking Update* ❌

*Booking ID:* {booking.get('bookingId', 'N/A')}
*Property:* {booking.get('bungalow_name', 'N/A')}, {booking.get('location', 'N/A')}
*Dates:* {format_date(booking.get('fromDate'))} to {format_date(booking.get('toDate'))}

We encountered an issue verifying your payment.
*Reason:* {reason}

Please contact the caretaker or try submitting your booking again.
*Caretaker Info:*
👤 Name: {booking.get('caretaker_name', 'N/A')}
📞 Phone: {booking.get('caretaker_phone', 'N/A')}
"""
    await send_whatsapp_message(mobile, message)
