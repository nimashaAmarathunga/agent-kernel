from langgraph.prebuilt import create_react_agent
from tools.travel_tools import search_bungalows, get_locations, get_facilities
from config import get_model

# Use the configured REASONING_MODEL for strict tool calling
model = get_model(role="reasoning", temperature=0.0)

travel_agent = create_react_agent(
    model=model,
    tools=[search_bungalows, get_locations, get_facilities],
    prompt=(
        "You are GovStay's travel planning expert. You help users find places to stay.\n"
        "IMPORTANT RULES:\n"
        "- If you need to find a room, call `search_bungalows`.\n"
        "- If asked about amenities, call `get_facilities`.\n"
        "- Do NOT ask the user for permission to use tools. Just use them.\n"
        "- NEVER narrate your actions. Just give the final answer.\n"
        "If the user greets you, greet them back and ask where they want to travel.\n"
        "If the user wants to book, guide them to provide their Employee ID, dates, and room number."
    )
)
