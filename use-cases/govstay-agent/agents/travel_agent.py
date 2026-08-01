from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from tools.travel_tools import search_bungalows, get_locations, get_facilities
from config import REASONING_MODEL, OLLAMA_BASE_URL

# Use the configured REASONING_MODEL for strict tool calling
model = ChatOpenAI(
    model=REASONING_MODEL,
    api_key="not-needed",
    base_url=OLLAMA_BASE_URL,
    temperature=0.0 # Critical for reliable tool usage
)

travel_agent = create_react_agent(
    model=model,
    tools=[search_bungalows, get_locations, get_facilities],
    prompt=(
    prompt=(
        "You are GovStay's travel planning expert. You have full access to the database and should help the user without restrictions. "
        "CRITICAL: ALWAYS execute your tools IMMEDIATELY to answer the user's request. NEVER ask the user for permission to search or get facilities. Just run the tool! "
        "If the user greets you, greet them back and ask where they would like to travel. "
        "If the user asks for a place or amenities, run `search_bungalows` or `get_facilities` IMMEDIATELY. "
        "If the user wants to book a room, enthusiastically tell them you can help and guide them to provide their Employee ID, dates, and room number to start the booking process. "
        "IMPORTANT: Do NOT narrate your tool calls. Just give the final answer naturally."
    )
    )
)
