from typing import Annotated, TypedDict
from langgraph.graph.message import AnyMessage, add_messages

class ConversationState(TypedDict):
    """
    State for the LangGraph workflow augmented with custom fields.
    """
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str | None
    session_id: str
    booking_id: str | None
    extracted_information: dict
    tool_results: dict
