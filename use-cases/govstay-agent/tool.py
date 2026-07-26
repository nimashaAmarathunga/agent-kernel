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
                    SELECT cb.name, cb.location, r."roomNumber", r."roomType", cb.price
                    FROM circuit_bungalows cb
                    JOIN rooms r ON r."circuitBungalowId" = cb.id
                    WHERE cb.location ILIKE $1
                    """,
                    f"%{input_data.location}%",
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT cb.name, cb.location, r."roomNumber", r."roomType", cb.price
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
                SELECT r.id AS room_id, r."circuitBungalowId", cb.price
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
