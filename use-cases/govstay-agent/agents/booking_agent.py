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
        "You are GovStay's booking manager. You help users create bookings.\n"
        "IMPORTANT RULES:\n"
        "- If you need to find a room, call `search_bungalows`.\n"
        "- Do NOT ask the user for permission to use tools. Just use them.\n"
        "STEPS:\n"
        "1. Ask for: Employee ID, Room Number, Check-in Date (YYYY-MM-DD), Check-out Date (YYYY-MM-DD).\n"
        "2. Use `check_availability()` to ensure the room is free.\n"
        "3. Use `calculate_amount()` to get the total cost.\n"
        "4. Call `sync_ui_state()` to show the booking form on the user's screen.\n"
        "5. Tell the user to click 'Submit Form' and upload their payment slip.\n"
        "6. When the user confirms, use `create_booking` to finalize."
    )
)
