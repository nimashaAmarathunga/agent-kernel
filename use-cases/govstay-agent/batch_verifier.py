import asyncio
import os
import json
import logging
import asyncpg
import fitz  # PyMuPDF
from pydantic import BaseModel
from dotenv import load_dotenv

# Use LangChain Ollama for text parsing
from langchain_openai import ChatOpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ak.batch_verifier")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
NEXT_JS_PUBLIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "govstay-ai", "public"))

# Use our local LLaMA
llm = ChatOpenAI(
    model="llama3.1", 
    base_url="http://localhost:11434/v1", 
    api_key="ollama", 
    temperature=0
)

async def process_slip(conn, booking):
    booking_id = booking['id']
    slip_url = booking['paymentSlipUrl']
    total_cost = booking['totalCost']
    user_mobile = booking['mobileNumber'] or "UNKNOWN_NUMBER"
    
    logger.info(f"Processing booking {booking['bookingId']} with slip {slip_url}")
    
    # 1. Update status to waking up
    await conn.execute("UPDATE bookings SET \"approvalReason\" = 'Agent: Waking up to process slip...' WHERE id = $1", booking_id)
    await asyncio.sleep(2)
    
    # Construct full file path
    # slip_url is likely something like "/uploads/slips/slip-123.pdf"
    if slip_url.startswith("/"):
        slip_url = slip_url[1:]
    
    file_path = os.path.join(NEXT_JS_PUBLIC_DIR, slip_url.replace("/", os.sep))
    
    if not os.path.exists(file_path):
        logger.error(f"Slip file not found: {file_path}")
        await conn.execute("UPDATE bookings SET status = 'REJECTED', \"approvalReason\" = 'Slip file not found' WHERE id = $1", booking_id)
        return
        
    try:
        # 2. Update status to extracting text
        await conn.execute("UPDATE bookings SET \"approvalReason\" = 'Agent: Extracting text from PDF using OCR...' WHERE id = $1", booking_id)
        await asyncio.sleep(2)
        
        # Extract text using PyMuPDF
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text()
                
        if not text.strip():
            logger.warning("Could not extract text from PDF. (Might be an image-only PDF)")
            await conn.execute("UPDATE bookings SET status = 'REJECTED', \"approvalReason\" = 'Could not read text from uploaded slip' WHERE id = $1", booking_id)
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
        await asyncio.sleep(3)
        
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
            await conn.execute("UPDATE bookings SET status = 'REJECTED', \"approvalReason\" = 'Failed to extract amount from slip automatically' WHERE id = $1", booking_id)
            return
            
        if not extracted_data.get("found"):
            logger.warning("LLM could not find amount in the slip text.")
            await conn.execute("UPDATE bookings SET status = 'REJECTED', \"approvalReason\" = 'Could not find a valid transferred amount in the slip' WHERE id = $1", booking_id)
            return
            
        amount = float(extracted_data.get("amount", 0))
        
        logger.info(f"Booking cost: {total_cost}, Slip amount: {amount}")
        
        if amount >= total_cost:
            # Payment sufficient! Confirm the booking.
            await conn.execute(
                "UPDATE bookings SET status = 'CONFIRMED', \"approvalReason\" = 'Slip verified successfully.', \"confidenceScore\" = 0.99 WHERE id = $1", 
                booking_id
            )
            logger.info(f"Booking {booking['bookingId']} CONFIRMED.")
            
            # SIMULATED WHATSAPP NOTIFICATION
            whatsapp_msg = f"""
=================================================
📱 [WHATSAPP MESSAGE SENT TO {user_mobile}]
=================================================
*GovStay Booking Confirmed!* ✅

Booking ID: {booking['bookingId']}
Amount Paid: LKR {total_cost}

Your government accommodation has been secured.
Please present this confirmation at check-in.
=================================================
"""
            logger.info(whatsapp_msg)
        else:
            # Payment insufficient!
            await conn.execute(
                "UPDATE bookings SET status = 'REJECTED', \"approvalReason\" = $1, \"confidenceScore\" = 0.99 WHERE id = $2", 
                f"Transferred amount (LKR {amount}) is less than total cost (LKR {total_cost}).",
                booking_id
            )
            logger.info(f"Booking {booking['bookingId']} REJECTED due to insufficient funds.")
            
    except Exception as e:
        logger.error(f"Error processing slip for booking {booking_id}: {e}")
        
async def verify_loop():
    logger.info("Starting batch verification loop...")
    
    # Run indefinitely
    while True:
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            
            # Find pending bookings that have a slip attached
            records = await conn.fetch(
                '''
                SELECT b.id, b."bookingId", b."totalCost", b."paymentSlipUrl", u."mobileNumber" 
                FROM bookings b
                LEFT JOIN users u ON b."userId" = u.id
                WHERE b.status = $1 AND b."paymentSlipUrl" IS NOT NULL
                ''',
                'PENDING'
            )
            
            for row in records:
                # We need to process this booking
                await process_slip(conn, row)
                
            await conn.close()
        except Exception as e:
            logger.error(f"Database error in verify loop: {e}")
            
        # Wait 30 seconds before polling again
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(verify_loop())
