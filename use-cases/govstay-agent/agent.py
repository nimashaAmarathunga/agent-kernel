import logging
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from agentkernel.cli import CLI
from agentkernel.langgraph import LangGraphModule, LangGraphToolBuilder

from skills.tools import (
    search_available_rooms,
    verify_employee,
    create_booking,
    review_booking,
    send_whatsapp_notification,
)

logger = logging.getLogger("ak.govstay")

SYSTEM_PROMPT = """
You are the GovStay Assistant, a highly efficient AI designed to help users book and manage government circuit bungalows.

Your capabilities:
1. Search for available bungalows and rooms using search_available_rooms.
2. Verify government employee credentials using verify_employee.
3. Create booking requests using create_booking.
4. Review and approve/reject bookings using review_booking.
5. Send notifications via WhatsApp using send_whatsapp_notification.

Rules:
- Be concise and professional.
- Ask for clarification if a user's request is ambiguous.
- Always use the tools provided to fetch real-time data; do not invent or assume availability.
"""

# Initialize the Gemini model
model = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

# Bind tools using Agent Kernel's LangGraph tool builder
tools = LangGraphToolBuilder.bind([
    search_available_rooms,
    verify_employee,
    create_booking,
    review_booking,
    send_whatsapp_notification,
])

# Create the React Agent Graph
govstay_agent = create_react_agent(
    name="govstay",
    model=model,
    tools=tools,
    prompt=SYSTEM_PROMPT,
)

# Register the agent graph with Agent Kernel
LangGraphModule([govstay_agent])

if __name__ == "__main__":
    CLI.main()
