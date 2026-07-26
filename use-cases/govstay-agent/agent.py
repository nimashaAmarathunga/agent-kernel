import logging
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from agentkernel.langgraph import LangGraphToolBuilder

from tool import search_available_rooms, verify_employee, create_booking

logger = logging.getLogger("ak.govstay")

# Initialize the Gemini models
# Full model for specialist agents that need reasoning
model = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
# Lite model for routing and security to conserve rate limits
lite_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite")

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

booking_agent = create_react_agent(
    name="booking_agent",
    model=model,
    tools=LangGraphToolBuilder.bind([create_booking]),
    prompt=(
        "You are a Booking Agent. You create bookings for users using the create_booking tool. "
        "ALWAYS prefix your final response with '[Booking Agent] '."
    ),
)

# ==========================================
# SUPERVISOR AGENT
# ==========================================

triage_agent = create_supervisor(
    model=lite_model,
    agents=[search_agent, verification_agent, booking_agent],
    prompt=(
        "You are the GovStay Supervisor Agent. Your ONLY job is to invoke the appropriate routing tool to send the user to:\n"
        "- search_agent: For finding available rooms and bungalows.\n"
        "- verification_agent: For checking employee IDs.\n"
        "- booking_agent: For creating or managing bookings.\n"
        "IMPORTANT: NEVER generate conversational text like 'I have transferred you' or 'I will help you'. "
        "ONLY invoke the tool to transfer the user, and return exactly what the specialist agent says."
    ),
).compile(name="govstay")

AGENTS = [triage_agent, search_agent, verification_agent, booking_agent]
