from langchain_openai import ChatOpenAI
from models.state import ConversationState
from config import ROUTER_MODEL, OLLAMA_BASE_URL

# Fast generation, strictly limited
model = ChatOpenAI(
    model=ROUTER_MODEL,
    api_key="not-needed",
    base_url=OLLAMA_BASE_URL,
    temperature=0.0,
    max_tokens=5,
    tags=["no_stream"]
)

def supervisor_router(state: ConversationState) -> str:
    """
    Lightweight router that returns EXACTLY one word: the agent name.
    """
    messages = state.get("messages", [])
    recent_msgs = messages[-3:]
    history_text = "\n".join([f"{msg.type}: {msg.content}" for msg in recent_msgs if msg.content])
    
    prompt = f"""You are a router.
Available agents:
travel_agent
booking_agent
verification_agent
notification_agent

Conversation History:
{history_text}

Based on the latest user intent, return only the agent name. No explanations."""
    
    response = model.invoke(prompt)
    choice = response.content.strip().lower()
    
    valid_agents = ["travel_agent", "booking_agent", "verification_agent", "notification_agent"]
    for agent_name in valid_agents:
        if agent_name in choice:
            return agent_name
            
    return "travel_agent" # default fallback
