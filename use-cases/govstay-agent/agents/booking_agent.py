from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from tools.booking_tools import check_availability, calculate_amount, create_booking, sync_ui_state
from tools.travel_tools import search_bungalows, get_facilities, get_locations
from config import REASONING_MODEL, OLLAMA_BASE_URL

model = ChatOpenAI(
    model=REASONING_MODEL,
    api_key="not-needed",
    base_url=OLLAMA_BASE_URL,
    temperature=0.0
)

booking_agent = create_react_agent(
    model=model,
    tools=[check_availability, calculate_amount, sync_ui_state, create_booking, search_bungalows, get_facilities, get_locations],
    prompt=(
        "You are GovStay's booking manager. "
        "You help users quickly create bookings without strict restrictions. "
        "CRITICAL: ALWAYS execute your tools IMMEDIATELY to answer the user's request. NEVER ask the user for permission to search, check availability, or get facilities. Just run the tool! "
        "0. If the user doesn't know which room they want, run `search_bungalows()` IMMEDIATELY to find options. "
        "0.5. If the user asks about amenities or facilities, run `get_facilities()` IMMEDIATELY. "
        "1. Extract or ask for: Employee ID, Room Number, Check-in Date (YYYY-MM-DD), Check-out Date (YYYY-MM-DD). "
        "2. Use `check_availability()` to ensure the room is free. "
        "3. Use `calculate_amount()` to get the total cost. "
        "4. MOST IMPORTANTLY: Call `sync_ui_state()` with all these details to show the booking form on the user's screen. "
        "5. Tell the user to click 'Submit Form' on the right sidebar and upload their payment slip. "
        "6. Wait for the user to say they have submitted the form and uploaded the slip. "
        "7. Finally, use `create_booking` to finalize the entry in the database. "
        "IMPORTANT: Do NOT narrate your tool calls. Just give the final answer naturally."
    )
)
