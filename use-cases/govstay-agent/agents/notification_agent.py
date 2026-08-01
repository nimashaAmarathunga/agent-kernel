from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
import logging
from config import REASONING_MODEL, OLLAMA_BASE_URL

logger = logging.getLogger("ak.govstay.agents.notification")

@tool("send_notification")
async def send_notification(emp_id: str, message: str) -> str:
    """Send a Telegram notification to the employee regarding their booking."""
    logger.info(f"MOCK TELEGRAM SEND to {emp_id}: {message}")
    # In production, this uses Agent Kernel's built-in Telegram integration
    return f"Notification sent to {emp_id}."

model = ChatOpenAI(
    model=REASONING_MODEL,
    api_key="not-needed",
    base_url=OLLAMA_BASE_URL,
    temperature=0.0
)

notification_agent = create_react_agent(
    model=model,
    tools=[send_notification],
    prompt=(
        "You are GovStay's notification agent. "
        "After a booking is confirmed or rejected, use `send_notification` "
        "to inform the user via Telegram/Email."
        "IMPORTANT: Do NOT narrate your tool calls or say what functions you are using. Just give the final answer naturally."
    )
)
