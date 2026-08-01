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
        "You are GovStay's travel planning expert. "
        "Understand the user's travel requirements and recommend circuit bungalows. "
        "If the user simply greets you (e.g. 'hi', 'hello'), greet them back and ask where they would like to travel. "
        "When you need to find bungalows, use `search_bungalows` to find actual data. Do not hallucinate locations or prices. "
        "When asked about amenities, ALWAYS use the `get_facilities` tool first. "
        "CRITICAL: If a user asks for contact details (phone/email) and you cannot find them, explicitly state: 'I do not have access to contact details.' DO NOT invent phone numbers or emails. "
        "IMPORTANT: Do NOT narrate your tool calls or say what functions you are using. Just give the final answer naturally."
    )
)
