import logging
import json
from pydantic import BaseModel, Field
from database.db_pool import get_pool
from langchain_core.tools import tool
from datetime import date
from agentkernel.core import ToolContext

logger = logging.getLogger("ak.govstay.tools.booking")

class CheckAvailabilityInput(BaseModel):
    room_number: str = Field(description="The room number (e.g. POL-01-AC).")
    start_date: str = Field(description="Check-in date in YYYY-MM-DD format.")
    end_date: str = Field(description="Check-out date in YYYY-MM-DD format.")

@tool("check_availability", args_schema=CheckAvailabilityInput)
async def check_availability(room_number: str, start_date: str, end_date: str, ctx: ToolContext) -> dict:
    """Check if a specific room is available for the given dates."""
    logger.info(f"Checking availability for {room_number} from {start_date} to {end_date}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            # Convert strings to datetime.date for asyncpg serialization
            from_d = date.fromisoformat(start_date)
            to_d = date.fromisoformat(end_date)
            
            user_id = ctx.user.id if ctx.user else None
            
            if user_id:
                rows = await conn.fetch(
                    """
                    SELECT id FROM bookings
                    WHERE "roomId" = (SELECT id FROM rooms WHERE "roomNumber" = $1)
                    AND (status = 'CONFIRMED' OR (status = 'PENDING' AND "userId" != $4))
                    AND ("fromDate" < $3::date AND "toDate" > $2::date)
                    """,
                    room_number, from_d, to_d, user_id
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id FROM bookings
                    WHERE "roomId" = (SELECT id FROM rooms WHERE "roomNumber" = $1)
                    AND status NOT IN ('REJECTED')
                    AND ("fromDate" < $3::date AND "toDate" > $2::date)
                    """,
                    room_number, from_d, to_d
                )
                
            if rows:
                return {"available": False, "error": "Room is already booked for these dates."}
            return {"available": True}
        except Exception as exc:
            logger.error(f"Error checking availability: {exc}")
            return {"available": False, "error": str(exc)}

class CalculateAmountInput(BaseModel):
    room_number: str = Field(description="The room number.")
    start_date: str = Field(description="Check-in date in YYYY-MM-DD format.")
    end_date: str = Field(description="Check-out date in YYYY-MM-DD format.")

@tool("calculate_amount", args_schema=CalculateAmountInput)
async def calculate_amount(room_number: str, start_date: str, end_date: str) -> dict:
    """Calculate the total booking amount based on the number of nights and room price."""
    logger.info(f"Calculating amount for {room_number}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            room = await conn.fetchrow('SELECT price FROM rooms WHERE "roomNumber" = $1', room_number)
            if not room:
                return {"error": f"Room {room_number} not found."}
            
            from_d = date.fromisoformat(start_date)
            to_d = date.fromisoformat(end_date)
            nights = (to_d - from_d).days
            
            if nights <= 0:
                return {"error": "Check-out date must be after check-in date."}
                
            total = nights * float(room["price"])
            return {"nights": nights, "price_per_night": float(room["price"]), "total_amount": total}
        except Exception as exc:
            logger.error(f"Error calculating amount: {exc}")
            return {"error": str(exc)}

import json

class CreateBookingInput(BaseModel):
    room_number: str = Field(description="The room number to book.")
    start_date: str = Field(description="Check-in date in YYYY-MM-DD format.")
    end_date: str = Field(description="Check-out date in YYYY-MM-DD format.")

@tool("create_booking", args_schema=CreateBookingInput)
async def create_booking(room_number: str, start_date: str, end_date: str) -> str:
    """Create the booking in the database and return the Booking ID and UI state for the summary."""
    try:
        context = ToolContext.get()
    except RuntimeError:
        context = None
    user_data = None
    if context:
        for req in context.requests:
            if getattr(req, "name", None) == "user" and req.content:
                user_data = req.content
                break
                
    if not user_data or not user_data.get("authenticated"):
        return "System Error: The user is not authenticated. Do not create a booking. Instruct the user to log in or register."
        
    user_id = user_data["id"]
    emp_id = user_data.get("empId", "")
    
    logger.warning(f"CREATE BOOKING TRIGGERED for {user_id} {room_number}")
    try:
        cost_info = await calculate_amount.ainvoke({"room_number": room_number, "start_date": start_date, "end_date": end_date})
        if "error" in cost_info:
            return f"Error calculating cost: {cost_info['error']}"
        total_cost = cost_info["total_amount"]

        pool = await get_pool()
        async with pool.acquire() as conn:
            # Verify user exists in the backend by their actual ID
            user = await conn.fetchrow("SELECT id FROM users WHERE id = $1", user_id)
            if not user:
                return f"Error: Authenticated user ID {user_id} not found in the system."
            
            # Verify room exists
            room = await conn.fetchrow("SELECT id as room_id, \"circuitBungalowId\" FROM rooms WHERE \"roomNumber\" = $1", room_number)
            if not room:
                return f"Error: Room {room_number} not found."

            # Convert strings to datetime.date for asyncpg
            from_d = date.fromisoformat(start_date)
            to_d = date.fromisoformat(end_date)

            # Look for an existing PENDING booking for this user and room
            existing_booking = await conn.fetchrow(
                """
                SELECT id, "bookingId" FROM bookings 
                WHERE "userId" = $1 AND "roomId" = $2 AND status = 'PENDING'
                """,
                user["id"], room["room_id"]
            )

            if existing_booking:
                booking = await conn.fetchrow(
                    """
                    UPDATE bookings 
                    SET "fromDate" = $1::date, "toDate" = $2::date, "totalCost" = $3, "updatedAt" = now()
                    WHERE id = $4
                    RETURNING "bookingId"
                    """,
                    from_d, to_d, total_cost, existing_booking["id"]
                )
            else:
                booking = await conn.fetchrow(
                    """
                    INSERT INTO bookings (id, "bookingId", "userId", "circuitBungalowId", "roomId",
                                          "fromDate", "toDate", status, "totalCost", "paymentSlipUrl", "createdAt", "updatedAt")
                    VALUES (gen_random_uuid(), gen_random_uuid()::text, $1, $2, $3,
                            $4::date, $5::date, 'PENDING', $6, $7, now(), now())
                    RETURNING "bookingId"
                    """,
                    user["id"],
                    room["circuitBungalowId"],
                    room["room_id"],
                    from_d,
                    to_d,
                    total_cost,
                    None
                )
            
            ui_state = {
                "emp_id": emp_id,
                "room_number": room_number,
                "from_date": start_date,
                "to_date": end_date,
                "total_cost": total_cost,
                "booking_id": booking['bookingId']
            }
            
            return json.dumps({
                "emp_id": emp_id,
                "room_number": room_number,
                "from_date": start_date,
                "to_date": end_date,
                "total_cost": total_cost,
                "booking_id": booking['bookingId'],
                "status": "PENDING",
                "_llm_instruction": "Booking created successfully. Instruct the user to review the summary and explicitly ask them to upload their payment slip using the UI upload button."
            })
    except Exception as exc:
        logger.error(f"Error creating booking: {exc}")
        return f"An error occurred: {exc}"

class UploadSlipInput(BaseModel):
    booking_id: str = Field(description="The Booking ID (Reference Number) returned from create_booking.")
    payment_slip_url: str = Field(description="URL of the uploaded payment slip.")

@tool("upload_payment_slip", args_schema=UploadSlipInput)
async def upload_payment_slip(booking_id: str, payment_slip_url: str) -> str:
    """Associate the uploaded payment slip with the existing booking and trigger verification."""
    try:
        context = ToolContext.get()
    except RuntimeError:
        context = None
    user_data = None
    if context:
        for req in context.requests:
            if getattr(req, "name", None) == "user" and req.content:
                user_data = req.content
                break
                
    if not user_data or not user_data.get("authenticated"):
        return "System Error: The user is not authenticated. Do not upload the payment slip. Instruct the user to log in."
        
    logger.warning(f"UPLOAD SLIP TRIGGERED for {booking_id}")
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # The Next.js API /api/upload handles the actual insertion into payment_slips
            slip = await conn.fetchrow(
                """
                SELECT id FROM payment_slips 
                WHERE "bookingId" = (SELECT id FROM bookings WHERE "bookingId" = $1)
                """,
                booking_id
            )
            
            if slip:
                return json.dumps({
                    "status": "success",
                    "message": "Payment slip verified in database. The background worker will process it.",
                    "_llm_instruction": "Acknowledge the payment slip upload and tell the user it is pending verification."
                })
            else:
                return "Error: Could not find the uploaded payment slip metadata in the database."
    except Exception as exc:
        logger.error(f"Error uploading slip: {exc}")
        return f"An error occurred: {exc}"

class SyncUiStateInput(BaseModel):
    room_number: str = Field(default="", description="The room number.")
    start_date: str = Field(default="", description="Check-in date in YYYY-MM-DD format.")
    end_date: str = Field(default="", description="Check-out date in YYYY-MM-DD format.")

@tool("sync_ui_state", args_schema=SyncUiStateInput)
async def sync_ui_state(room_number: str = "", start_date: str = "", end_date: str = "") -> str:
    """Emit the booking form state to the UI so the user can review and submit the booking manually."""
    
    try:
        context = ToolContext.get()
    except RuntimeError:
        context = None
    user_data = None
    if context:
        for req in context.requests:
            if getattr(req, "name", None) == "user" and req.content:
                user_data = req.content
                break
                
    emp_id = user_data.get("empId", "") if user_data else ""
    
    logger.warning(f"SYNC UI STATE TRIGGERED for {emp_id} {room_number}")
    
    total_cost = None
    if room_number and start_date and end_date:
        # 1. Check Availability
        avail = await check_availability.ainvoke({"room_number": room_number, "start_date": start_date, "end_date": end_date})
        if not avail.get("available", False):
            return f"Room is not available: {avail.get('error', 'Already booked')}"
            
        # 2. Calculate Amount
        cost_info = await calculate_amount.ainvoke({"room_number": room_number, "start_date": start_date, "end_date": end_date})
        if "error" in cost_info:
            return f"Error calculating cost: {cost_info['error']}"
        total_cost = cost_info["total_amount"]

    return json.dumps({
        "emp_id": emp_id,
        "room_number": room_number,
        "from_date": start_date,
        "to_date": end_date,
        "total_cost": total_cost,
        "step": "pending_submission"
    })

