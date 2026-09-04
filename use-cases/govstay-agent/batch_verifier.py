import asyncio
import os
import json
import logging
import asyncpg
import fitz  # PyMuPDF
from pydantic import BaseModel
from dotenv import load_dotenv

from telegram_helper import notify_booking_confirmed, notify_booking_rejected

# Use LangChain Ollama for text parsing
from langchain_openai import ChatOpenAI

from supabase import create_client, Client
import tempfile

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ak.batch_verifier")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Use our local LLaMA
llm = ChatOpenAI(
    model="llama3.1", 
    base_url="http://localhost:11434/v1", 
    api_key="ollama", 
    temperature=0,
    model_kwargs={"response_format": {"type": "json_object"}}
)

async def process_slip(conn, booking):
    booking_id = booking['id']
    slip_url = booking['storagePath']
    total_cost = booking['totalCost']
    user_mobile = booking['mobileNumber'] or "UNKNOWN_NUMBER"
    
    logger.info(f"Processing booking {booking['bookingId']} with slip {slip_url}")
    
    # 1. Update status to waking up
    await conn.execute("UPDATE bookings SET \"approvalReason\" = 'Agent: Waking up to process slip...' WHERE id = $1", booking_id)
    
    # Download file from Supabase securely
    try:
        response = supabase.storage.from_('payment-slips').download(slip_url)
    except Exception as e:
        logger.error(f"Slip file not found or download error: {e}")
        await conn.execute("UPDATE payment_slips SET \"verificationStatus\" = 'REJECTED' WHERE \"bookingId\" = $1", booking_id)
        await conn.execute("UPDATE bookings SET status = 'REJECTED', \"approvalReason\" = 'Slip file not found in secure storage' WHERE id = $1", booking_id)
        await notify_booking_rejected(booking, "Slip file not found in secure storage.")
        return

    # Write to a temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    os.write(temp_fd, response)
    os.close(temp_fd)
        
    try:
        # 2. Update status to extracting text
        await conn.execute("UPDATE bookings SET \"approvalReason\" = 'Agent: Extracting text from PDF using OCR...' WHERE id = $1", booking_id)
        
        # Extract text using PyMuPDF
        text = ""
        with fitz.open(temp_path) as doc:
            for page in doc:
                text += page.get_text()
                
        if not text.strip():
            logger.warning("Could not extract text from PDF. (Might be an image-only PDF)")
            await conn.execute("UPDATE payment_slips SET \"verificationStatus\" = 'REJECTED' WHERE \"bookingId\" = $1", booking_id)
            await conn.execute("UPDATE bookings SET status = 'REJECTED', \"approvalReason\" = 'Failed to extract text from slip. Please upload a text-based PDF.' WHERE id = $1", booking_id)
            await notify_booking_rejected(booking, "Failed to extract text from slip. Please upload a text-based PDF.")
            return
        # Ask LLaMA to extract the amount
        prompt = f"""You are a data extraction bot. I am giving you the raw text extracted from a bank transfer slip.
Your job is to find the EXACT amount that was transferred.

Raw text from slip:
{text}

Output a strict JSON object with this exact format, and NOTHING else:
{{"found": true, "amount": 1234.50}}
If you cannot find any amount, output:
{{"found": false, "amount": 0}}
"""
        # 3. Update status to LLM validating
        await conn.execute("UPDATE bookings SET \"approvalReason\" = 'Agent: Passing text to LLaMA to validate payment amount...' WHERE id = $1", booking_id)
        
        try:
            response = await llm.ainvoke(prompt)
            
            # Parse LLaMA response
            content = response.content.strip()
            import json
            import re
            try:
                # Extract json using regex in case LLM outputs conversational text
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
                extracted_data = json.loads(content)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON from LLM: {content}")
                await conn.execute("UPDATE payment_slips SET \"verificationStatus\" = 'REJECTED' WHERE \"bookingId\" = $1", booking_id)
                await conn.execute("UPDATE bookings SET status = 'REJECTED', \"approvalReason\" = 'Failed to extract amount from slip automatically' WHERE id = $1", booking_id)
                await notify_booking_rejected(booking, "Failed to extract amount from slip automatically.")
                return
        except Exception as e:
            logger.error(f"LLM connection error: {e}")
            await conn.execute("UPDATE payment_slips SET \"verificationStatus\" = 'REJECTED' WHERE \"bookingId\" = $1", booking_id)
            await conn.execute("UPDATE bookings SET status = 'REJECTED', \"approvalReason\" = 'Verification failed due to LLM processing error' WHERE id = $1", booking_id)
            await notify_booking_rejected(booking, "Verification failed due to AI processing error.")
            return
            
        if not extracted_data.get("found"):
            logger.warning("LLM could not find amount in the slip text.")
            await conn.execute("UPDATE payment_slips SET \"verificationStatus\" = 'REJECTED' WHERE \"bookingId\" = $1", booking_id)
            await conn.execute("UPDATE bookings SET status = 'REJECTED', \"approvalReason\" = 'Could not find a valid transferred amount in the slip' WHERE id = $1", booking_id)
            await notify_booking_rejected(booking, "Could not find a valid transferred amount in the slip.")
            return
            
        # Robustly parse amount
        raw_amt = extracted_data.get("amount", 0)
        if isinstance(raw_amt, str):
            raw_amt = raw_amt.replace(",", "").strip()
            
        try:
            amount = float(raw_amt)
        except (ValueError, TypeError):
            amount = 0.0
        
        logger.info(f"Booking cost: {total_cost}, Slip amount: {amount}")
        
        if amount >= total_cost:
            # Payment sufficient! Confirm the booking.
            await conn.execute("UPDATE payment_slips SET \"verificationStatus\" = 'VERIFIED' WHERE \"bookingId\" = $1", booking_id)
            await conn.execute(
                "UPDATE bookings SET status = 'CONFIRMED', \"approvalReason\" = 'Slip verified successfully.', \"confidenceScore\" = 0.99 WHERE id = $1", 
                booking_id
            )
            logger.info(f"Booking {booking['bookingId']} CONFIRMED.")
            
            await notify_booking_confirmed(booking)
        else:
            # Payment insufficient!
            reason = f"Transferred amount (LKR {amount}) is less than total cost (LKR {total_cost})."
            await conn.execute("UPDATE payment_slips SET \"verificationStatus\" = 'REJECTED' WHERE \"bookingId\" = $1", booking_id)
            await conn.execute(
                "UPDATE bookings SET status = 'REJECTED', \"approvalReason\" = $1, \"confidenceScore\" = 0.99 WHERE id = $2", 
                reason,
                booking_id
            )
            logger.info(f"Booking {booking['bookingId']} REJECTED due to insufficient funds.")
            await notify_booking_rejected(booking, reason)
            
    except Exception as e:
        logger.error(f"Error processing slip for booking {booking_id}: {e}")
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
async def verify_loop():
    logger.info("Starting batch verification loop...")
    
    # Run indefinitely
    while True:
        try:
            conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
            
            # Find pending bookings that have a slip attached
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
            
            for row in records:
                # We need to process this booking
                await process_slip(conn, row)
                
            await conn.close()
        except Exception as e:
            logger.error(f"Database error in verify loop: {e}")
            
        # Wait 5 seconds before polling again
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(verify_loop())
