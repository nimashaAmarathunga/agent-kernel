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
                    SELECT cb.name, cb.location, r."roomNumber", r."roomType", r.price, r.capacity, r.bed_count
                    FROM circuit_bungalows cb
                    JOIN rooms r ON r."circuitBungalowId" = cb.id
                    WHERE cb.location ILIKE $1
                    """,
                    f"%{location}%",
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT cb.name, cb.location, r."roomNumber", r."roomType", r.price, r.capacity, r.bed_count
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
                    f"Room {row['roomNumber']} ({row['roomType']}) — LKR {row['price']}/night "
                    f"[Capacity: {row['capacity']} people, Physical Beds: {row['bed_count']}]"
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
            # Support searching by room number OR bungalow name keywords
            keywords = bungalow_name.replace('-', ' ').split()
            
            # 1. First try to match if the user provided a room number directly
            query_by_room = """
                SELECT cb.name, cb.amenities 
                FROM circuit_bungalows cb
                JOIN rooms r ON r."circuitBungalowId" = cb.id
                WHERE r."roomNumber" ILIKE $1
                LIMIT 1
            """
            
            # The input might be "OLD-101" or "Room OLD-101"
            # We look for any word that matches a room number pattern
            possible_rooms = [k for k in bungalow_name.split() if '-' in k or k.isdigit()]
            
            row = None
            if possible_rooms:
                row = await conn.fetchrow(query_by_room, f"%{possible_rooms[0]}%")
                
            if not row:
                # 2. If no room match, fallback to the keyword match on bungalow name
                conditions = " AND ".join([f"cb.name ILIKE ${i+1}" for i in range(len(keywords))])
                params = [f"%{k}%" for k in keywords]
                query_by_name = f"SELECT cb.name, cb.amenities FROM circuit_bungalows cb WHERE {conditions} LIMIT 1"
                row = await conn.fetchrow(query_by_name, *params)
            
            if not row or not row["amenities"]:
                return f"No facility information found for '{bungalow_name}'."
            amenities = row["amenities"]
            if isinstance(amenities, list):
                amenities = ", ".join(amenities)
            return f"Facilities at {row['name']}: {amenities}"
        except Exception as exc:
            logger.error(f"Error getting facilities: {exc}")
            return "Error retrieving facilities."
