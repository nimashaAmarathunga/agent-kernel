import logging
from pydantic import BaseModel, Field
from database.db_pool import get_pool
from langchain_core.tools import tool

logger = logging.getLogger("ak.govstay.tools.travel")

class SearchBungalowsInput(BaseModel):
    location: str | None = Field(default=None, description="City or region to search in (e.g. 'Nuwara Eliya').")

@tool("search_bungalows", args_schema=SearchBungalowsInput)
async def search_bungalows(location: str | None = None) -> str:
    """Search for available circuit bungalows and rooms.
    Use this when the user wants to know which bungalows or rooms are available.
    """
    logger.info(f"Searching bungalows | location={location}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            if location:
                rows = await conn.fetch(
                    """
                    SELECT cb.name, cb.location, r."roomNumber", r."roomType", r.price
                    FROM circuit_bungalows cb
                    JOIN rooms r ON r."circuitBungalowId" = cb.id
                    WHERE cb.location ILIKE $1
                    """,
                    f"%{location}%",
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
                return f"No rooms found matching '{location or 'all'}' criteria."

            lines = ["Found the following rooms:"]
            for row in rows:
                lines.append(
                    f"- {row['name']} ({row['location']}): "
                    f"Room {row['roomNumber']} ({row['roomType']}) — LKR {row['price']}/night"
                )
            return "\n".join(lines)
        except Exception as exc:
            logger.error(f"Error searching rooms: {exc}")
            return "An error occurred while searching for bungalows."

class GetLocationsInput(BaseModel):
    pass

@tool("get_locations", args_schema=GetLocationsInput)
async def get_locations() -> str:
    """Get a list of all locations where circuit bungalows are available."""
    logger.info("Getting locations")
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch("SELECT DISTINCT location FROM circuit_bungalows")
            locations = [row["location"] for row in rows if row["location"]]
            if not locations:
                return "No locations currently available."
            return "Bungalows are available in: " + ", ".join(locations)
        except Exception as exc:
            logger.error(f"Error getting locations: {exc}")
            return "Error retrieving locations."

class GetFacilitiesInput(BaseModel):
    bungalow_name: str = Field(description="Name of the bungalow to check facilities for")

@tool("get_facilities", args_schema=GetFacilitiesInput)
async def get_facilities(bungalow_name: str) -> str:
    """Get the facilities and amenities for a specific bungalow."""
    logger.info(f"Getting facilities for {bungalow_name}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "SELECT amenities FROM circuit_bungalows WHERE name ILIKE $1",
                f"%{bungalow_name}%"
            )
            if not row or not row["amenities"]:
                return f"No facility information found for '{bungalow_name}'."
            amenities = row["amenities"]
            if isinstance(amenities, list):
                amenities = ", ".join(amenities)
            return f"Facilities at {bungalow_name}: {amenities}"
        except Exception as exc:
            logger.error(f"Error getting facilities: {exc}")
            return "Error retrieving facilities."
