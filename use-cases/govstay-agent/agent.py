import logging
from dotenv import load_dotenv

load_dotenv()

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage
from agentkernel.langgraph import LangGraphToolBuilder

from tool import (
    search_available_rooms, SearchRoomsInput,
    verify_employee, VerifyEmployeeInput,
    create_booking, CreateBookingInput,
    verify_document, VerifyDocumentInput,
    approve_booking, ApproveBookingInput,
    send_whatsapp_notification, SendWhatsAppInput,
    get_bungalow_knowledge, BungalowKnowledgeInput
)
import json
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

greeting_agent = create_react_agent(
    name="greeting_agent",
    model=model,
    tools=[],
    prompt=(
        "You are GovStay, a friendly and polite assistant. "
        "The user is saying hi or making small talk. Greet them warmly and politely ask how you can help them with their circuit bungalow bookings today.\n\n"
        "EXAMPLES:\n"
        "User: hi\n"
        "Assistant: Hello! Welcome to GovStay. How can I help you with your circuit bungalow booking today?\n\n"
        "User: who are you\n"
        "Assistant: I am the GovStay virtual assistant! I'm here to help you find and book government circuit bungalows. What location are you interested in?\n\n"
        "Always keep it short and friendly."
    ),
)

search_agent = create_react_agent(
    name="search_agent",
    model=model,
    tools=LangGraphToolBuilder.bind([search_available_rooms, get_bungalow_knowledge]),
    prompt=(
        "You are an assistant for GovStay. You help users find available circuit bungalows and provide information about them.\n"
        "1. Use `search_available_rooms` if they want to check availability, prices, or room options.\n"
        "2. Use `get_bungalow_knowledge` if they ask about amenities (like A/C, Hot Water), nearby attractions, or general bungalow descriptions.\n\n"
        "EXAMPLES:\n"
        "User: What are the attractions near Polonnaruwa bungalow?\n"
        "Assistant: [Calls get_bungalow_knowledge with location='Polonnaruwa']\n\n"
        "User: Are there rooms in Nuwara Eliya?\n"
        "Assistant: [Calls search_available_rooms with location='Nuwara Eliya']\n\n"
        "Always be conversational and helpful."
    ),
)

verification_agent = create_react_agent(
    name="verification_agent",
    model=model,
    tools=LangGraphToolBuilder.bind([verify_employee]),
    prompt=(
        "You are an assistant for GovStay. You verify government employee IDs using the verify_employee tool. "
        "Provide friendly, concise, and natural conversational responses."
    ),
)

document_agent = create_react_agent(
    name="document_agent",
    model=model,
    tools=LangGraphToolBuilder.bind([verify_document]),
    prompt=(
        "You are an assistant for GovStay. Your job is to verify uploaded approval slips for bookings. "
        "When a user needs to verify their slip, ask them to upload it if they haven't already. "
        "Use your multimodal capabilities (e.g. analyze_attachments if available) to read the uploaded document, "
        "extract Name, Employee ID, and Dates, and then call verify_document to validate them against the booking. "
        "Provide friendly, concise, and natural conversational responses."
    ),
)

booking_agent = create_react_agent(
    name="booking_agent",
    model=model,
    tools=LangGraphToolBuilder.bind([create_booking]),
    prompt=(
        "You are an assistant for GovStay. You create bookings for users using the create_booking tool.\n\n"
        "CRITICAL RULES:\n"
        "1. DO NOT hallucinate or guess any booking details. You MUST gather exactly 4 pieces of information from the user before calling create_booking: Employee ID, Room Number, From Date (YYYY-MM-DD), and To Date (YYYY-MM-DD).\n"
        "2. If ANY of these 4 details are missing, you MUST politely ask the user for them. DO NOT call the tool if anything is missing.\n"
        "3. Whenever you extract or receive any of these 4 details, you MUST output a JSON block exactly like this to update the UI:\n"
        "[UI_SYNC] {\"emp_id\": \"EMP-123\", \"room_number\": \"OLD-101\", \"from_date\": \"2024-03-01\", \"to_date\": \"2024-03-05\"}\n\n"
        "EXAMPLES:\n"
        "User: I want to book room POL-01-AC\n"
        "Assistant: I can help with that! Could you please provide your Employee ID and the dates you'd like to check in and out? [UI_SYNC] {\"room_number\": \"POL-01-AC\"}\n\n"
        "Once a booking is created (it will be in PENDING status), instruct the user to upload their approval slip for verification."
    ),
)

approval_agent = create_react_agent(
    name="approval_agent",
    model=model,
    tools=LangGraphToolBuilder.bind([approve_booking, send_whatsapp_notification]),
    prompt=(
        "You are an assistant for GovStay. Your job is to make the final automated decision on a booking. "
        "If the document was verified successfully, you MUST call approve_booking with decision='APPROVED'. "
        "If verification failed, call approve_booking with decision='REJECTED'. Provide a clear reason. "
        "Once the decision is made, you MUST call send_whatsapp_notification to notify the employee. "
        "Provide friendly, concise, and natural conversational responses."
    ),
)

# ==========================================
# SUPERVISOR AGENT
# ==========================================

def supervisor_node(state: MessagesState):
    return {"messages": []}

async def tool_fixer_node(state: MessagesState):
    messages = state.get("messages", [])
    if not messages: return {"messages": []}
    
    last_msg = messages[-1]
    if not isinstance(last_msg, AIMessage) or not last_msg.content:
        return {"messages": []}
        
    content = str(last_msg.content).strip()
    
    if content.startswith("{") and '"name"' in content and '"parameters"' in content:
        try:
            call_data = None
            # Attempt to fix truncated JSON by adding closing braces
            for i in range(5):
                try:
                    call_data = json.loads(content + "}" * i)
                    break
                except json.JSONDecodeError:
                    pass
            
            if not call_data:
                raise ValueError("Could not parse JSON even after adding braces.")
                
            tool_name = call_data.get("name")
            parameters = call_data.get("parameters", {})
            
            # The model might nest under input_data
            if "input_data" in parameters and len(parameters) == 1:
                parameters = parameters["input_data"]
                
            result = None
            if tool_name == "search_available_rooms":
                result = await search_available_rooms(SearchRoomsInput(**parameters))
            elif tool_name == "get_bungalow_knowledge":
                result = await get_bungalow_knowledge(BungalowKnowledgeInput(**parameters))
            elif tool_name == "verify_employee":
                result = await verify_employee(VerifyEmployeeInput(**parameters))
            elif tool_name == "create_booking":
                result = await create_booking(CreateBookingInput(**parameters))
            elif tool_name == "verify_document":
                result = await verify_document(VerifyDocumentInput(**parameters))
            elif tool_name == "approve_booking":
                result = await approve_booking(ApproveBookingInput(**parameters))
            elif tool_name == "send_whatsapp_notification":
                result = await send_whatsapp_notification(SendWhatsAppInput(**parameters))
                
            if result is not None:
                logger.info(f"Self-corrected JSON tool execution for {tool_name}")
                summary_prompt = (
                    f"The user wanted to do an action. You successfully executed a backend tool ({tool_name}) "
                    f"and got this result: {result}\n"
                    f"Write a friendly conversational response to the user summarizing this. DO NOT use JSON. "
                    f"Just normal text."
                )
                summary_msg = await model.ainvoke(summary_prompt)
                
                # Make sure the name is set so the UI displays correctly
                summary_msg.name = "Assistant"
                
                return {"messages": [summary_msg]}
                
        except Exception as e:
            logger.error(f"Tool fixer failed to parse or execute: {e}")
            
    return {"messages": []}

def custom_router(state: MessagesState) -> str:
    # Convert up to the last 5 messages to text for context
    recent_msgs = state["messages"][-5:]
    history_text = "\n".join([f"{msg.type}: {msg.content}" for msg in recent_msgs if msg.content])
    
    prompt = f"""You are a smart conversational router. Look at the recent conversation history to understand the context of the user's latest message.
Based on what the user is currently trying to do, output EXACTLY ONE of the following words and nothing else:
- greeting_agent (if they are just saying hi, making small talk, or asking a generic non-booking question)
- search_agent (if they want to find, look for, or ask about available rooms/bungalows)
- verification_agent (if they are verifying their employee ID)
- booking_agent (if they want to book a room, are answering booking questions, or confirming a booking)
- document_agent (if they are uploading or talking about an approval slip/document)
- approval_agent (if the document was verified and it is ready for final approval)

Recent Conversation History:
{history_text}

Output only the agent word:"""
    
    response = lite_model.invoke(prompt)
    choice = response.content.strip().lower()
    
    valid_agents = ["greeting_agent", "search_agent", "verification_agent", "booking_agent", "document_agent", "approval_agent"]
    for agent_name in valid_agents:
        if agent_name in choice:
            return agent_name
            
    return "greeting_agent" # default fallback for anything else

builder = StateGraph(MessagesState)
builder.add_node("supervisor", supervisor_node)
builder.add_node("greeting_agent", greeting_agent)
builder.add_node("search_agent", search_agent)
builder.add_node("verification_agent", verification_agent)
builder.add_node("booking_agent", booking_agent)
builder.add_node("document_agent", document_agent)
builder.add_node("approval_agent", approval_agent)

builder.add_node("tool_fixer", tool_fixer_node)

builder.add_edge(START, "supervisor")

builder.add_conditional_edges(
    "supervisor",
    custom_router,
    {
        "greeting_agent": "greeting_agent",
        "search_agent": "search_agent",
        "verification_agent": "verification_agent",
        "booking_agent": "booking_agent",
        "document_agent": "document_agent",
        "approval_agent": "approval_agent",
    }
)

builder.add_edge("greeting_agent", END)
builder.add_edge("search_agent", "tool_fixer")
builder.add_edge("verification_agent", "tool_fixer")
builder.add_edge("booking_agent", "tool_fixer")
builder.add_edge("document_agent", "tool_fixer")
builder.add_edge("approval_agent", "tool_fixer")

builder.add_edge("tool_fixer", END)

memory = MemorySaver()
triage_agent = builder.compile(checkpointer=memory)
triage_agent.name = "govstay"

AGENTS = [triage_agent, greeting_agent, search_agent, verification_agent, booking_agent, document_agent, approval_agent]
