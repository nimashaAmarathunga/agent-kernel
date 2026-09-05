import asyncio
import os
import json
import re
import logging
import tempfile
from decimal import Decimal, InvalidOperation

import asyncpg
import fitz  # PyMuPDF
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from supabase import create_client, Client

from telegram_helper import notify_booking_confirmed, notify_booking_rejected

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ak.batch_verifier")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Use Groq for LLM extraction — the model confirmed working for this task
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    max_tokens=200,
)

# ---------------------------------------------------------------------------
# Amount normalization — deterministic, no LLM involvement
# ---------------------------------------------------------------------------

def normalize_amount(raw_value) -> Decimal | None:
    """
    Normalize a raw amount value (from LLM JSON or text) into a canonical Decimal.
    
    Handles formats like:
        5000, 5000.00, "5,000", "5,000.00", "Rs. 5,000.00",
        "LKR 5,000", "Rs 5000/-", "LKR5,000"
    
    Returns None if the value cannot be parsed into a valid monetary amount.
    """
    if raw_value is None:
        return None

    raw_str = str(raw_value).strip()

    if not raw_str:
        return None

    # Strip known currency prefixes/suffixes
    raw_str = re.sub(r'(?i)^(rs\.?|lkr)\s*', '', raw_str)
    raw_str = re.sub(r'/\-?\s*$', '', raw_str)  # trailing /-
    raw_str = raw_str.strip()

    # Remove thousands separators (commas) but keep the decimal point
    raw_str = raw_str.replace(',', '')

    # Remove any remaining non-numeric characters except dot
    raw_str = re.sub(r'[^\d.]', '', raw_str)

    if not raw_str:
        return None

    try:
        amount = Decimal(raw_str)
        # Quantize to 2 decimal places for currency
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


# ---------------------------------------------------------------------------
# Core slip processing
# ---------------------------------------------------------------------------

async def process_slip(conn, booking):
    booking_id = booking['id']
    booking_display_id = booking['bookingId']
    slip_url = booking['storagePath']
    total_cost = booking['totalCost']
    user_mobile = booking.get('mobileNumber') or "UNKNOWN_NUMBER"

    logger.info(f"[BatchVerifier] ====== Processing booking {booking_display_id} ======")
    logger.info(f"[BatchVerifier] Booking UUID: {booking_id}")
    logger.info(f"[BatchVerifier] Storage path: {slip_url}")
    logger.info(f"[BatchVerifier] Expected totalCost: {total_cost}")

    # Normalize the expected amount from the database
    expected_amount = normalize_amount(total_cost)
    if expected_amount is None:
        logger.error(f"[BatchVerifier] Cannot normalize expected totalCost: {total_cost!r}")
        await _set_error(conn, booking_id, "System error: invalid booking total cost")
        return

    logger.info(f"[BatchVerifier] Normalized expected amount: {expected_amount}")

    # 1. Update status to processing
    await conn.execute(
        "UPDATE bookings SET \"approvalReason\" = 'Agent: Waking up to process slip...' WHERE id = $1",
        booking_id
    )

    # ---- STEP 1: Download file from Supabase ----
    try:
        file_bytes = supabase.storage.from_('payment-slips').download(slip_url)
        logger.info(f"[BatchVerifier] Downloaded {len(file_bytes)} bytes from storage")
    except Exception as e:
        logger.error(f"[BatchVerifier] Slip download failed: {e}")
        await _set_error(conn, booking_id, "Slip file not found or download error — will retry")
        return

    # Determine file extension from the storage path
    ext = os.path.splitext(slip_url)[1] or ".pdf"
    temp_fd, temp_path = tempfile.mkstemp(suffix=ext)
    os.write(temp_fd, file_bytes)
    os.close(temp_fd)

    try:
        # ---- STEP 2: Extract text from PDF using PyMuPDF ----
        await conn.execute(
            "UPDATE bookings SET \"approvalReason\" = 'Agent: Extracting text from document...' WHERE id = $1",
            booking_id
        )

        text = ""
        try:
            with fitz.open(temp_path) as doc:
                logger.info(f"[BatchVerifier] Document has {doc.page_count} page(s)")
                for page in doc:
                    text += page.get_text()
        except Exception as e:
            logger.error(f"[BatchVerifier] PyMuPDF failed to open document: {e}")
            await _set_error(conn, booking_id, "Document could not be opened — please re-upload a valid PDF")
            return

        if not text.strip():
            logger.warning(f"[BatchVerifier] No text extracted from document (image-only PDF or corrupt file)")
            await _set_error(conn, booking_id, "DOCUMENT_UNREADABLE: No text could be extracted from the slip. Please upload a text-based PDF.")
            return

        logger.info(f"[BatchVerifier] Extracted {len(text)} characters of text")
        # Log first 300 chars for debugging (avoid sensitive data in production)
        logger.info(f"[BatchVerifier] Text preview: {text[:300]!r}")

        # ---- STEP 3: Send text to Groq LLM for amount extraction ----
        await conn.execute(
            "UPDATE bookings SET \"approvalReason\" = 'Agent: Extracting payment amount via AI...' WHERE id = $1",
            booking_id
        )

        prompt = f"""You are a data extraction bot. I am giving you the raw text extracted from a bank transfer slip.
Your job is to find the EXACT amount that was transferred.

Raw text from slip:
{text}

Output a strict JSON object with this exact format, and NOTHING else:
{{"found": true, "amount": 1234.50}}
If you cannot find any amount, output:
{{"found": false, "amount": 0}}"""

        try:
            response = await llm.ainvoke(prompt)
            content = response.content.strip()
            logger.info(f"[BatchVerifier] LLM raw response: {content!r}")
        except Exception as e:
            logger.error(f"[BatchVerifier] Groq LLM call failed: {e}")
            await _set_error(conn, booking_id, "AI service temporarily unavailable — will retry")
            return

        # ---- STEP 4: Parse LLM JSON response ----
        extracted_data = None
        try:
            # Try direct JSON parse first
            extracted_data = json.loads(content)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown fences or surrounding text
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                try:
                    extracted_data = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

        if extracted_data is None:
            logger.error(f"[BatchVerifier] Failed to parse JSON from LLM response: {content!r}")
            await _set_error(conn, booking_id, "AI response could not be parsed — will retry")
            return

        logger.info(f"[BatchVerifier] Parsed LLM data: {extracted_data}")

        # ---- STEP 5: Validate extracted data ----
        if not extracted_data.get("found"):
            logger.warning(f"[BatchVerifier] LLM reports no amount found in the slip text")
            await _set_error(conn, booking_id, "Could not find a transferred amount in the slip — please upload a clearer document")
            return

        raw_extracted_amount = extracted_data.get("amount")
        extracted_amount = normalize_amount(raw_extracted_amount)

        if extracted_amount is None or extracted_amount <= 0:
            logger.warning(f"[BatchVerifier] Extracted amount is invalid: {raw_extracted_amount!r}")
            await _set_error(conn, booking_id, "Extracted amount is invalid — please upload a clearer document")
            return

        logger.info(f"[BatchVerifier] Extracted amount (normalized): {extracted_amount}")
        logger.info(f"[BatchVerifier] Expected amount (normalized): {expected_amount}")

        # ---- STEP 6: Deterministic amount comparison ----
        amounts_match = (extracted_amount == expected_amount)
        logger.info(f"[BatchVerifier] Amount match: {amounts_match}")

        await conn.execute(
            "UPDATE bookings SET \"approvalReason\" = 'Agent: Comparing extracted amount against booking total...' WHERE id = $1",
            booking_id
        )

        if amounts_match:
            # ---- CONFIRMED ----
            await conn.execute(
                "UPDATE payment_slips SET \"verificationStatus\" = 'VERIFIED' WHERE \"bookingId\" = $1",
                booking_id
            )
            await conn.execute(
                "UPDATE bookings SET status = 'CONFIRMED', \"approvalReason\" = 'Slip verified successfully.', \"confidenceScore\" = 0.99 WHERE id = $1",
                booking_id
            )
            logger.info(f"[BatchVerifier] ✅ Booking {booking_display_id} CONFIRMED (LKR {extracted_amount} == LKR {expected_amount})")
            await notify_booking_confirmed(booking)
        else:
            # ---- REJECTED (genuine amount mismatch) ----
            reason = f"Transferred amount (LKR {extracted_amount}) does not match the total booking cost (LKR {expected_amount})."
            await conn.execute(
                "UPDATE payment_slips SET \"verificationStatus\" = 'REJECTED' WHERE \"bookingId\" = $1",
                booking_id
            )
            await conn.execute(
                "UPDATE bookings SET status = 'REJECTED', \"approvalReason\" = $1, \"confidenceScore\" = 0.99 WHERE id = $2",
                reason, booking_id
            )
            logger.info(f"[BatchVerifier] ❌ Booking {booking_display_id} REJECTED — amount mismatch (LKR {extracted_amount} != LKR {expected_amount})")
            await notify_booking_rejected(booking, reason)

    except Exception as e:
        logger.error(f"[BatchVerifier] Unexpected error processing booking {booking_id}: {e}", exc_info=True)
        await _set_error(conn, booking_id, f"System error during verification — will retry")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


async def _set_error(conn, booking_id: str, reason: str):
    """
    Set a technical error state. The booking stays PENDING so the verifier can retry.
    The payment slip is marked ERROR to distinguish from genuine REJECTED.
    """
    try:
        await conn.execute(
            "UPDATE payment_slips SET \"verificationStatus\" = 'ERROR' WHERE \"bookingId\" = $1",
            booking_id
        )
        await conn.execute(
            "UPDATE bookings SET \"approvalReason\" = $1 WHERE id = $2",
            reason, booking_id
        )
        logger.info(f"[BatchVerifier] Set ERROR state for booking {booking_id}: {reason}")
    except Exception as db_e:
        logger.error(f"[BatchVerifier] Failed to set error state: {db_e}")


async def verify_loop():
    logger.info("[BatchVerifier] Starting batch verification loop...")

    while True:
        try:
            conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)

            # Find pending bookings that have a PENDING slip attached
            # Excludes ERROR slips to prevent infinite retry — they need manual re-upload
            records = await conn.fetch(
                '''
                SELECT 
                    b.id, b."bookingId", b."totalCost", p."storagePath", b."fromDate", b."toDate", b."approvalReason",
                    u."mobileNumber", u.name AS user_name,
                    c.name AS bungalow_name, c.location, c.department,
                    r."roomNumber", r."roomType",
                    ct.name AS caretaker_name, ct."telephoneNo" AS caretaker_phone
                FROM bookings b
                INNER JOIN payment_slips p ON b.id = p."bookingId"
                LEFT JOIN users u ON b."userId" = u.id
                LEFT JOIN circuit_bungalows c ON b."circuitBungalowId" = c.id
                LEFT JOIN rooms r ON b."roomId" = r.id
                LEFT JOIN caretakers ct ON c.id = ct."circuitBungalowId"
                WHERE b.status = $1 AND p."verificationStatus" = 'PENDING'
                ''',
                'PENDING'
            )

            if records:
                logger.info(f"[BatchVerifier] Found {len(records)} pending slip(s) to verify")
            
            for row in records:
                await process_slip(conn, row)

            await conn.close()
        except Exception as e:
            logger.error(f"[BatchVerifier] Database error in verify loop: {e}")

        # Wait 5 seconds before polling again
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(verify_loop())
