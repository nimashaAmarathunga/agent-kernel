import logging
from pydantic import BaseModel, Field
from database.db_pool import get_pool
from langchain_core.tools import tool
from datetime import date

logger = logging.getLogger("ak.govstay.tools.booking")

class CheckAvailabilityInput(BaseModel):
    room_number: str = Field(description="The room number (e.g. POL-01-AC).")
    start_date: str = Field(description="Check-in date in YYYY-MM-DD format.")
    end_date: str = Field(description="Check-out date in YYYY-MM-DD format.")

@tool("check_availability", args_schema=CheckAvailabilityInput)
async def check_availability(room_number: str, start_date: str, end_date: str) -> dict:
    """Check if a specific room is available for the given dates."""
    logger.info(f"Checking availability for {room_number} from {start_date} to {end_date}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            # Basic implementation for checking overlapping bookings
            rows = await conn.fetch(
                """
                SELECT id FROM bookings
                WHERE "roomId" = (SELECT id FROM rooms WHERE "roomNumber" = $1)
                AND status NOT IN ('REJECTED')
                AND ("fromDate" < $3::date AND "toDate" > $2::date)
                """,
                room_number, start_date, end_date
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

class CreateBookingInput(BaseModel):
    emp_id: str = Field(description="Government employee ID of the user.")
    room_number: str = Field(description="The room number to book.")
    start_date: str = Field(description="Check-in date in YYYY-MM-DD format.")
    end_date: str = Field(description="Check-out date in YYYY-MM-DD format.")
    total_cost: float = Field(description="Calculated total cost.")

@tool("create_booking", args_schema=CreateBookingInput)
async def create_booking(emp_id: str, room_number: str, start_date: str, end_date: str, total_cost: float) -> str:
    """Create a PENDING_PAYMENT booking record."""
    logger.info(f"Creating booking | emp_id={emp_id} room={room_number}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            user = await conn.fetchrow('SELECT id FROM users WHERE "empId" = $1', emp_id)
            if not user:
                return f"Cannot create booking: employee ID '{emp_id}' not found."

            room = await conn.fetchrow(
                """
                SELECT r.id AS room_id, r."circuitBungalowId"
                FROM rooms r
                WHERE r."roomNumber" = $1
                """,
                room_number,
            )
            if not room:
                return f"Cannot create booking: room '{room_number}' not found."

            booking = await conn.fetchrow(
                """
                INSERT INTO bookings (id, "bookingId", "userId", "circuitBungalowId", "roomId",
                                      "fromDate", "toDate", status, "totalCost", "createdAt", "updatedAt")
                VALUES (gen_random_uuid(), gen_random_uuid()::text, $1, $2, $3,
                        $4::date, $5::date, 'PENDING_PAYMENT', $6, now(), now())
                RETURNING "bookingId"
                """,
                user["id"],
                room["circuitBungalowId"],
                room["room_id"],
                start_date,
                end_date,
                total_cost,
            )
            return (
                f"Booking created successfully!\n"
                f"Booking ID: {booking['bookingId']}\n"
                f"Status: PENDING_PAYMENT\n"
                f"Please upload your payment slip to confirm the booking."
            )
        except Exception as exc:
            logger.error(f"Error creating booking: {exc}")
            return f"An error occurred: {exc}"

class SyncUiStateInput(BaseModel):
    emp_id: str = Field(description="Government employee ID of the user.")
    room_number: str = Field(description="The room number.")
    start_date: str = Field(description="Check-in date in YYYY-MM-DD format.")
    end_date: str = Field(description="Check-out date in YYYY-MM-DD format.")
    total_cost: float = Field(description="Calculated total cost.")

@tool("sync_ui_state", args_schema=SyncUiStateInput)
async def sync_ui_state(emp_id: str, room_number: str, start_date: str, end_date: str, total_cost: float) -> dict:
    """Emit the booking form state to the UI so the user can review and submit the booking manually."""
    return {
        "emp_id": emp_id,
        "room_number": room_number,
        "from_date": start_date,
        "to_date": end_date,
        "total_cost": total_cost,
        "step": "pending_submission"
    }
