from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from tools.booking_tools import check_availability, calculate_amount, create_booking
from config import REASONING_MODEL, OLLAMA_BASE_URL

model = ChatOpenAI(
    model=REASONING_MODEL,
    api_key="not-needed",
    base_url=OLLAMA_BASE_URL,
    temperature=0.0
)

booking_agent = create_react_agent(
    model=model,
    tools=[check_availability, calculate_amount, create_booking],
    prompt=(
        "You are GovStay's booking manager. "
        "You manage the booking lifecycle. "
        "1. Use `check_availability()` to ensure the room is free. "
        "2. Use `calculate_amount()` to get the total cost. "
        "3. Wait for the user to confirm. "
        "4. Use `create_booking()` to finalize it. "
        "IMPORTANT: Do NOT narrate your tool calls or say what functions you are using. Just give the final answer naturally."
    )
)
