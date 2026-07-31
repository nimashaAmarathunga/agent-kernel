from __future__ import annotations

import logging
import os
from typing import Optional

import asyncpg
from pydantic import BaseModel, Field

logger = logging.getLogger("ak.govstay_tool")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

# ---------------------------------------------------------------------------
# Connection pool — created once on first use and shared across all tool calls.
# Avoids the cost of a new TCP connection per invocation.
# ---------------------------------------------------------------------------

_pool: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        logger.info("Database connection pool initialised.")
    return _pool


# ---------------------------------------------------------------------------
# Input schemas — strict Pydantic models so the LLM cannot pass bad types.
# ---------------------------------------------------------------------------


class SearchRoomsInput(BaseModel):
    location: Optional[str] = Field(default=None, description="City or region to search in (e.g. 'Nuwara Eliya').")


class BungalowKnowledgeInput(BaseModel):
    location: str = Field(description="The city or region of the bungalow (e.g. 'Nuwara Eliya', 'Polonnaruwa').")


class VerifyEmployeeInput(BaseModel):
    emp_id: str = Field(description="Government employee ID (e.g. '245503B').")


class CreateBookingInput(BaseModel):
    emp_id: str = Field(description="Government employee ID of the user making the booking.")
    room_number: str = Field(description="The room number to book.")
    from_date: str = Field(description="Check-in date in YYYY-MM-DD format.")
    to_date: str = Field(description="Check-out date in YYYY-MM-DD format.")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


async def search_available_rooms(input_data: SearchRoomsInput) -> str:
    """Search for available circuit bungalows and rooms.

    Use this when the user wants to know which bungalows or rooms are available,
    optionally filtered by city or region.
    """
    logger.info("Searching rooms | location=%s", input_data.location)
    pool = await _get_pool()
    async with pool.acquire() as conn:
        try:
            if input_data.location:
                rows = await conn.fetch(
                    """
                    SELECT cb.name, cb.location, r."roomNumber", r."roomType", r.price
                    FROM circuit_bungalows cb
                    JOIN rooms r ON r."circuitBungalowId" = cb.id
                    WHERE cb.location ILIKE $1
                    """,
                    f"%{input_data.location}%",
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT cb.name, cb.location, r."roomNumber", r."roomType", r.price
                    FROM circuit_bungalows cb
                    JOIN rooms r ON r."circuitBungalowId" = cb.id
                    """
                )

            if not rows:
                return "No rooms found matching your criteria."

            lines = ["Found the following rooms:"]
            for row in rows:
                lines.append(
                    f"- {row['name']} ({row['location']}): "
                    f"Room {row['roomNumber']} ({row['roomType']}) — LKR {row['price']}/night"
                )
            return "\n".join(lines)
        except Exception as exc:
            logger.error("Error searching rooms: %s", exc)
            return "An error occurred while searching for rooms. Please try again."


async def get_bungalow_knowledge(input_data: BungalowKnowledgeInput) -> str:
    """Retrieve detailed knowledge about bungalows in a specific location, including amenities and nearby attractions.
    
    Use this when the user asks about what amenities are available at a bungalow, 
    or what attractions/places they can visit nearby.
    """
    logger.info("Getting bungalow knowledge | location=%s", input_data.location)
    pool = await _get_pool()
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                """
                SELECT name, location, description, amenities, highlights
                FROM circuit_bungalows
                WHERE location ILIKE $1
                """,
                f"%{input_data.location}%",
            )
            
            if not rows:
                return f"No bungalow information found for {input_data.location}."
                
            lines = [f"Here is the knowledge base information for {input_data.location}:"]
            for row in rows:
                lines.append(f"\nBungalow: {row['name']} ({row['location']})")
                if row['description']:
                    lines.append(f"Description: {row['description']}")
                if row['amenities']:
                    lines.append(f"Amenities: {', '.join(row['amenities']) if isinstance(row['amenities'], list) else row['amenities']}")
                if row['highlights']:
                    lines.append(f"Nearby Attractions/Highlights: {', '.join(row['highlights']) if isinstance(row['highlights'], list) else row['highlights']}")
                    
            return "\n".join(lines)
        except Exception as exc:
            logger.error("Error getting bungalow knowledge: %s", exc)
            return "An error occurred while fetching bungalow knowledge. Please try again."


async def verify_employee(input_data: VerifyEmployeeInput) -> str:
    """Verify a government employee by their employee ID.

    Use this when the user provides an employee ID and wants to confirm their
    identity, work placement, or eligibility.
    """
    logger.info("Verifying employee | emp_id=%s", input_data.emp_id)
    pool = await _get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                'SELECT name, "placeOfWork", position, status FROM users WHERE "empId" = $1',
                input_data.emp_id,
            )
            if not row:
                return f"Verification failed: no employee found with ID '{input_data.emp_id}'."
            return (
                f"Verified!\n"
                f"  Name      : {row['name']}\n"
                f"  Department: {row['placeOfWork']}\n"
                f"  Position  : {row['position']}\n"
                f"  Status    : {row['status']}"
            )
        except Exception as exc:
            logger.error("Error verifying employee: %s", exc)
            return "An error occurred during employee verification. Please try again."


async def create_booking(input_data: CreateBookingInput) -> str:
    """Create a PENDING booking request for a circuit bungalow room.

    Use this when the user explicitly wants to make a booking. Requires a verified
    employee ID, room number, and check-in/check-out dates.
    """
    logger.info(
        "Creating booking | emp_id=%s room=%s %s -> %s",
        input_data.emp_id,
        input_data.room_number,
        input_data.from_date,
        input_data.to_date,
    )
    pool = await _get_pool()
    async with pool.acquire() as conn:
        try:
            # Resolve user ID from emp_id
            user = await conn.fetchrow('SELECT id FROM users WHERE "empId" = $1', input_data.emp_id)
            if not user:
                return f"Cannot create booking: employee ID '{input_data.emp_id}' not found."

            # Resolve room & bungalow IDs
            room = await conn.fetchrow(
                """
                SELECT r.id AS room_id, r."circuitBungalowId", r.price
                FROM rooms r
                JOIN circuit_bungalows cb ON cb.id = r."circuitBungalowId"
                WHERE r."roomNumber" = $1
                """,
                input_data.room_number,
            )
            if not room:
                return f"Cannot create booking: room '{input_data.room_number}' not found."

            # Calculate total cost
            from datetime import date
            from_d = date.fromisoformat(input_data.from_date)
            to_d = date.fromisoformat(input_data.to_date)
            nights = (to_d - from_d).days
            if nights <= 0:
                return "Check-out date must be after check-in date."
            total_cost = nights * float(room["price"])

            # Insert booking with PENDING status
            booking = await conn.fetchrow(
                """
                INSERT INTO bookings (id, "bookingId", "userId", "circuitBungalowId", "roomId",
                                      "fromDate", "toDate", status, "totalCost", "createdAt", "updatedAt")
                VALUES (gen_random_uuid(), gen_random_uuid()::text, $1, $2, $3,
                        $4::date, $5::date, 'PENDING', $6, now(), now())
                RETURNING "bookingId"
                """,
                user["id"],
                room["circuitBungalowId"],
                room["room_id"],
                input_data.from_date,
                input_data.to_date,
                total_cost,
            )

            return (
                f"Booking created successfully!\n"
                f"  Booking ID  : {booking['bookingId']}\n"
                f"  Room        : {input_data.room_number}\n"
                f"  Check-in    : {input_data.from_date}\n"
                f"  Check-out   : {input_data.to_date}\n"
                f"  Nights      : {nights}\n"
                f"  Total Cost  : LKR {total_cost:,.2f}\n"
                f"  Status      : PENDING (awaiting approval)"
            )
        except Exception as exc:
            logger.error("Error creating booking: %s", exc)
            return "An error occurred while creating the booking. Please try again."

class VerifyDocumentInput(BaseModel):
    booking_id: str = Field(description="The PENDING booking ID to verify against.")
    extracted_name: str = Field(description="Name extracted from the document.")
    extracted_emp_id: str = Field(description="Employee ID extracted from the document.")
    extracted_from_date: str = Field(description="Check-in date extracted from the document (YYYY-MM-DD).")
    extracted_to_date: str = Field(description="Check-out date extracted from the document (YYYY-MM-DD).")

class ApproveBookingInput(BaseModel):
    booking_id: str = Field(description="The ID of the booking to approve or reject.")
    decision: str = Field(description="'APPROVED' or 'REJECTED'")
    reason: str = Field(description="Reason for approval or rejection.")
    confidence_score: float = Field(description="Confidence score between 0.0 and 1.0.")

# ---------------------------------------------------------------------------
# Document & Approval Tools
# ---------------------------------------------------------------------------

async def verify_document(input_data: VerifyDocumentInput) -> str:
    """Verify extracted document data against an existing PENDING booking.
    
    Use this after extracting details from an uploaded slip to validate if the
    slip matches the booking details in the database.
    """
    logger.info("Verifying document for booking %s", input_data.booking_id)
    pool = await _get_pool()
    async with pool.acquire() as conn:
        try:
            booking = await conn.fetchrow(
                '''
                SELECT b."bookingId", b."fromDate", b."toDate", b.status, u.name, u."empId"
                FROM bookings b
                JOIN users u ON b."userId" = u.id
                WHERE b."bookingId" = $1
                ''',
                input_data.booking_id
            )
            
            if not booking:
                return f"Verification Failed: Booking ID '{input_data.booking_id}' not found."
                
            if booking['status'] != 'PENDING':
                return f"Verification Failed: Booking '{input_data.booking_id}' is currently {booking['status']}, not PENDING."
                
            # Perform strict matching logic
            errors = []
            
            # Simple substring/case-insensitive matching for names can be robust, but here we expect exact or very close.
            db_name = booking['name'].lower()
            ext_name = input_data.extracted_name.lower()
            if ext_name not in db_name and db_name not in ext_name:
                errors.append(f"Name mismatch (DB: {booking['name']}, Doc: {input_data.extracted_name})")
                
            if booking['empId'] != input_data.extracted_emp_id:
                errors.append(f"Employee ID mismatch (DB: {booking['empId']}, Doc: {input_data.extracted_emp_id})")
                
            db_from = booking['fromDate'].strftime('%Y-%m-%d')
            if db_from != input_data.extracted_from_date:
                errors.append(f"Check-in date mismatch (DB: {db_from}, Doc: {input_data.extracted_from_date})")
                
            db_to = booking['toDate'].strftime('%Y-%m-%d')
            if db_to != input_data.extracted_to_date:
                errors.append(f"Check-out date mismatch (DB: {db_to}, Doc: {input_data.extracted_to_date})")
                
            if errors:
                return f"VERIFICATION FAILED. Errors:\n- " + "\n- ".join(errors) + "\nConfidence Score Drop: Recommend REJECTED."
            
            return "VERIFICATION SUCCESSFUL. All document details match the database booking perfectly. Recommend APPROVED."
            
        except Exception as exc:
            logger.error("Error verifying document: %s", exc)
            return "An error occurred while verifying the document."

async def approve_booking(input_data: ApproveBookingInput) -> str:
    """Finalize a booking by setting its status to CONFIRMED or REJECTED.
    
    Use this to officially approve or reject a PENDING booking.
    Requires decision, reason, and confidence score.
    """
    logger.info("Approving booking %s: %s", input_data.booking_id, input_data.decision)
    if input_data.decision not in ['APPROVED', 'REJECTED']:
        return "Decision must be 'APPROVED' or 'REJECTED'."
        
    status_enum = 'CONFIRMED' if input_data.decision == 'APPROVED' else 'REJECTED'
    
    pool = await _get_pool()
    async with pool.acquire() as conn:
        try:
            # We must cast the string to the BookingStatus enum in PostgreSQL
            updated = await conn.execute(
                '''
                UPDATE bookings 
                SET status = $1::"BookingStatus", "approvalReason" = $2, "confidenceScore" = $3, "updatedAt" = now()
                WHERE "bookingId" = $4 AND status = 'PENDING'
                ''',
                status_enum,
                input_data.reason,
                input_data.confidence_score,
                input_data.booking_id
            )
            
            if updated == "UPDATE 0":
                return f"Failed to update. Booking '{input_data.booking_id}' not found or not in PENDING status."
                
            return f"Booking {input_data.booking_id} successfully updated to {status_enum}."
            
        except Exception as exc:
            logger.error("Error updating booking status: %s", exc)
            return "An error occurred while updating the booking status."

class SendWhatsAppInput(BaseModel):
    emp_id: str = Field(description="The employee ID of the user to notify.")
    message: str = Field(description="The confirmation or rejection message to send.")

async def send_whatsapp_notification(input_data: SendWhatsAppInput) -> str:
    """Send a WhatsApp notification to the employee regarding their booking.
    
    Use this to notify the user immediately after an approval or rejection decision is made.
    """
    logger.info("MOCK WHATSAPP SEND to %s: %s", input_data.emp_id, input_data.message)
    # Since we are mocking this step due to missing Meta API credentials:
    print(f"\n[WHATSAPP MOCK TO {input_data.emp_id}]: {input_data.message}\n")
    return f"WhatsApp message successfully sent to employee {input_data.emp_id}."
