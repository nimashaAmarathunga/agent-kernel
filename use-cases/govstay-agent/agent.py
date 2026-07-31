import logging
from dotenv import load_dotenv

load_dotenv()

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.messages import AIMessage
from agentkernel.langgraph import LangGraphToolBuilder

from tool import search_available_rooms, verify_employee, create_booking, verify_document, approve_booking, send_whatsapp_notification

logger = logging.getLogger("ak.govstay")

# Point to your local Ollama / LLaMA REST API
local_llm_url = "http://localhost:11434/v1"

# Initialize the Local LLaMA model
model = ChatOpenAI(
    model="llama3.1",
    api_key="not-needed",
    base_url=local_llm_url,
    temperature=0.1
)

# Use the same model for routing to ensure reliable function calling
lite_model = model

# ==========================================
# SPECIALIZED AGENTS
# ==========================================

search_agent = create_react_agent(
    name="search_agent",
    model=model,
    tools=LangGraphToolBuilder.bind([search_available_rooms]),
    prompt=(
        "You are a Search Agent. You help users find available circuit bungalows using the search_available_rooms tool. "
        "ALWAYS prefix your final response with '[Search Agent] '."
    ),
)

verification_agent = create_react_agent(
    name="verification_agent",
    model=model,
    tools=LangGraphToolBuilder.bind([verify_employee]),
    prompt=(
        "You are a Verification Agent. You verify government employee IDs using the verify_employee tool. "
        "ALWAYS prefix your final response with '[Verification Agent] '."
    ),
)

document_agent = create_react_agent(
    name="document_agent",
    model=model,
    tools=LangGraphToolBuilder.bind([verify_document]),
    prompt=(
        "You are a Document Agent. Your job is to verify uploaded approval slips for bookings. "
        "When a user needs to verify their slip, ask them to upload it if they haven't already. "
        "Use your multimodal capabilities (e.g. analyze_attachments if available) to read the uploaded document, "
        "extract Name, Employee ID, and Dates, and then call verify_document to validate them against the booking. "
        "ALWAYS prefix your final response with '[Document Agent] '."
    ),
)

booking_agent = create_react_agent(
    name="booking_agent",
    model=model,
    tools=LangGraphToolBuilder.bind([create_booking]),
    prompt=(
        "You are a Booking Agent. You create bookings for users using the create_booking tool. "
        "Once a booking is created (it will be in PENDING status), instruct the user to upload their approval slip "
        "and transfer them to the Document Agent for verification. "
        "ALWAYS prefix your final response with '[Booking Agent] '."
    ),
)

approval_agent = create_react_agent(
    name="approval_agent",
    model=model,
    tools=LangGraphToolBuilder.bind([approve_booking, send_whatsapp_notification]),
    prompt=(
        "You are an Approval Agent. Your job is to make the final automated decision on a booking. "
        "If the document_agent verified the slip successfully, you MUST call approve_booking with decision='APPROVED'. "
        "If verification failed, call approve_booking with decision='REJECTED'. "
        "Provide a clear reason and confidence score. "
        "Once the decision is made, you MUST call send_whatsapp_notification to notify the employee of the final outcome. "
        "ALWAYS prefix your final response with '[Approval Agent] '."
    ),
)

# ==========================================
# SUPERVISOR AGENT
# ==========================================

def supervisor_node(state: MessagesState):
    return {"messages": []}

def custom_router(state: MessagesState) -> str:
    last_msg = state["messages"][-1].content
    prompt = f"""You are a router. Based on the user's message, output EXACTLY ONE of the following words and nothing else:
- search_agent (for finding rooms)
- verification_agent (for ID verification)
- booking_agent (for making bookings)
- document_agent (for uploading slips)
- approval_agent (for approving bookings)

User message: {last_msg}"""
    
    response = lite_model.invoke(prompt)
    choice = response.content.strip().lower()
    
    valid_agents = ["search_agent", "verification_agent", "booking_agent", "document_agent", "approval_agent"]
    for agent_name in valid_agents:
        if agent_name in choice:
            return agent_name
            
    return "search_agent" # default fallback

builder = StateGraph(MessagesState)
builder.add_node("supervisor", supervisor_node)
builder.add_node("search_agent", search_agent)
builder.add_node("verification_agent", verification_agent)
builder.add_node("booking_agent", booking_agent)
builder.add_node("document_agent", document_agent)
builder.add_node("approval_agent", approval_agent)

builder.add_edge(START, "supervisor")

builder.add_conditional_edges(
    "supervisor",
    custom_router,
    {
        "search_agent": "search_agent",
        "verification_agent": "verification_agent",
        "booking_agent": "booking_agent",
        "document_agent": "document_agent",
        "approval_agent": "approval_agent",
    }
)

builder.add_edge("search_agent", END)
builder.add_edge("verification_agent", END)
builder.add_edge("booking_agent", END)
builder.add_edge("document_agent", END)
builder.add_edge("approval_agent", END)

triage_agent = builder.compile()
triage_agent.name = "govstay"

AGENTS = [triage_agent, search_agent, verification_agent, booking_agent, document_agent, approval_agent]
