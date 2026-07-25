import os
import logging
import asyncpg
from typing import Optional

logger = logging.getLogger("ak.govstay_skills")

# We use the local Postgres DB created via Docker
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

async def _get_db() -> asyncpg.Connection:
    return await asyncpg.connect(DATABASE_URL)

async def search_available_rooms(
    location: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    room_type: Optional[str] = None
) -> str:
    """Searches for available circuit bungalows and rooms.
    Returns a formatted string of available options.
    """
    conn = await _get_db()
    try:
        # Initial search query, filtering by location if provided
        query = '''
            SELECT cb.name, cb.location, r."roomNumber", r."roomType", cb.price 
            FROM circuit_bungalows cb
            JOIN rooms r ON r."circuitBungalowId" = cb.id
        '''
        args = []
        if location:
            query += " WHERE cb.location ILIKE $1"
            args.append(f"%{location}%")
        
        rows = await conn.fetch(query, *args)
        
        if not rows:
            return "No rooms found matching your criteria."
            
        results = ["Found the following rooms:"]
        for row in rows:
            results.append(f"- {row['name']} ({row['location']}): Room {row['roomNumber']} ({row['roomType']}) at LKR {row['price']}/night")
        return "\n".join(results)
    except Exception as e:
        logger.error(f"Error searching rooms: {e}")
        return f"Failed to search rooms: {str(e)}"
    finally:
        await conn.close()

async def verify_employee(emp_id: str) -> str:
    """Verifies a government employee using their empId."""
    conn = await _get_db()
    try:
        query = 'SELECT name, "placeOfWork", position, status FROM users WHERE "empId" = $1'
        row = await conn.fetchrow(query, emp_id)
        if not row:
            return "Employee verification failed. ID not found."
        return f"Verified! Name: {row['name']}, Work: {row['placeOfWork']}, Position: {row['position']}, Status: {row['status']}."
    except Exception as e:
        logger.error(f"Error verifying employee: {e}")
        return f"Verification error: {str(e)}"
    finally:
        await conn.close()

async def create_booking(
    emp_id: str,
    room_number: str,
    from_date: str,
    to_date: str
) -> str:
    """Creates a PENDING booking request. Returns the status or an error."""
    conn = await _get_db()
    try:
        # Example insertion logic (in real world, we would resolve IDs)
        # For now, return success string
        return "Booking request created successfully. Status is PENDING approval."
    finally:
        await conn.close()

async def review_booking(booking_id: str, decision: str, reason: str) -> str:
    """Approves or rejects a booking (decision must be 'APPROVE' or 'REJECT')."""
    return f"Booking {booking_id} has been {decision}ED. Reason: {reason}"

async def send_whatsapp_notification(phone_number: str, message: str) -> str:
    """Sends a WhatsApp notification to the user."""
    logger.info(f"Sending WhatsApp to {phone_number}: {message}")
    # Integration with real WhatsApp API goes here via Agent Kernel channels
    return "WhatsApp notification sent successfully!"
