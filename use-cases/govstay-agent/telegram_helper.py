import os
import logging
import httpx

logger = logging.getLogger("ak.telegram_helper")

async def send_telegram_message(text: str) -> bool:
    """
    Send a notification using ntfy.sh to bypass ISP blocks.
    The user can view these at https://ntfy.sh/govstay_idealize_2026
    """
    # Using a public topic for the hackathon project
    topic = "govstay_idealize_2026"
    url = f"https://ntfy.sh/{topic}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data=text.encode('utf-8'),
                headers={"Title": "GovStay Agent Update"}
            )
            response.raise_for_status()
            logger.info(f"Notification sent to https://ntfy.sh/{topic} successfully.")
            return True
    except Exception as e:
        logger.exception(f"Error sending notification to {topic}:")
        return False

def format_date(dt):
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m-%d")
    return str(dt).split(" ")[0]

async def notify_booking_confirmed(booking: dict):
    """
    Constructs and sends a structured confirmation message.
    """
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
    await send_telegram_message(message)

async def notify_booking_rejected(booking: dict, reason: str):
    """
    Constructs and sends a structured rejection message.
    """
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
    await send_telegram_message(message)
