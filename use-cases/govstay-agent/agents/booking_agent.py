from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from tools.booking_tools import check_availability, calculate_amount, create_booking, sync_ui_state
from config import REASONING_MODEL, OLLAMA_BASE_URL

model = ChatOpenAI(
    model=REASONING_MODEL,
    api_key="not-needed",
    base_url=OLLAMA_BASE_URL,
    temperature=0.0
)

booking_agent = create_react_agent(
    model=model,
    tools=[check_availability, calculate_amount, sync_ui_state, create_booking],
    prompt=(
        "You are GovStay's booking manager. "
        "You manage the booking lifecycle. Follow these steps strictly: "
        "1. Ask the user for their Employee ID, Room Number, and Dates (if not provided). "
        "2. Use `check_availability()` to ensure the room is free. "
        "3. Use `calculate_amount()` to get the total cost. "
        "4. Use `sync_ui_state()` to emit the booking details to the user's UI. "
        "5. Tell the user to review the form on the right, click 'Submit Form', and upload a payment slip for verification. "
        "6. DO NOT call `create_booking` until the user explicitly confirms they have submitted the form and uploaded the payment slip. "
        "7. ONLY AFTER the user confirms submission and payment, call `create_booking` and inform them the booking is complete. "
        "IMPORTANT: Do NOT narrate your tool calls or say what functions you are using."
    )
)
