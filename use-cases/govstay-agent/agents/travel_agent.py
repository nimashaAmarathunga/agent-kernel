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
        "ALWAYS use `search_bungalows` to find actual data. Do not hallucinate locations or prices. "
        "Filter by the user's requested date, location, or facilities. "
        "IMPORTANT: Do NOT narrate your tool calls or say what functions you are using (e.g. never say 'I will use search_bungalows'). Just give the final answer naturally."
    )
)
