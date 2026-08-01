import logging
from database.db_pool import get_pool
from config import VISION_MODEL, OLLAMA_BASE_URL

logger = logging.getLogger("ak.govstay.document_ai")

async def run_validation_pipeline(booking_id: str, slip_url: str) -> str:
    """
    Simulates the Document AI OCR Pipeline and Python Validation Engine.
    In a real scenario, this would call {VISION_MODEL} via Ollama to extract {"amount": X}.
    """
    logger.info(f"Running validation pipeline for booking {booking_id} with slip {slip_url}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        booking = await conn.fetchrow('SELECT "totalCost" FROM bookings WHERE "bookingId" = $1', booking_id)
        if not booking:
            return "REJECTED: Booking not found."

        expected_amount = float(booking["totalCost"])
        
        # --- MOCK OCR EXTRACTION ---
        # Assume the vision model successfully extracted the amount from the slip
        extracted_amount = expected_amount # For demonstration, assume they paid correctly
        # ---------------------------

        if extracted_amount >= expected_amount:
            # AUTO_APPROVE logic
            await conn.execute(
                '''
                UPDATE bookings 
                SET status = 'CONFIRMED', "approvalReason" = 'Slip verified successfully.', "confidenceScore" = 0.99 
                WHERE "bookingId" = $1
                ''',
                booking_id
            )
            return "AUTO_APPROVE (Status: CONFIRMED)"
        else:
            # REJECT logic
            await conn.execute(
                '''
                UPDATE bookings 
                SET status = 'REJECTED', "approvalReason" = 'Insufficient amount transferred.', "confidenceScore" = 0.99 
                WHERE "bookingId" = $1
                ''',
                booking_id
            )
            return "REJECTED (Insufficient amount)"
