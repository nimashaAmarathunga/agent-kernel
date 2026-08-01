from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from models.state import ConversationState
from agents.supervisor import supervisor_router
from agents.travel_agent import travel_agent
from agents.booking_agent import booking_agent
from agents.verification_agent import verification_agent
from agents.notification_agent import notification_agent

def supervisor_node(state: ConversationState):
    return state

builder = StateGraph(ConversationState)

# Nodes
builder.add_node("supervisor", supervisor_node)
builder.add_node("travel_agent", travel_agent)
builder.add_node("booking_agent", booking_agent)
builder.add_node("verification_agent", verification_agent)
builder.add_node("notification_agent", notification_agent)

# Edges
builder.add_edge(START, "supervisor")

builder.add_conditional_edges(
    "supervisor",
    supervisor_router,
    {
        "travel_agent": "travel_agent",
        "booking_agent": "booking_agent",
        "verification_agent": "verification_agent",
        "notification_agent": "notification_agent",
    }
)

builder.add_edge("travel_agent", END)
builder.add_edge("booking_agent", END)
builder.add_edge("verification_agent", END)
builder.add_edge("notification_agent", END)

memory = MemorySaver()
triage_agent = builder.compile(checkpointer=memory)
triage_agent.name = "govstay"
travel_agent.name = "travel_agent"
booking_agent.name = "booking_agent"
verification_agent.name = "verification_agent"
notification_agent.name = "notification_agent"

# Export agents for Agent Kernel server.py mapping
AGENTS = [
    triage_agent,
    travel_agent,
    booking_agent,
    verification_agent,
    notification_agent
]
