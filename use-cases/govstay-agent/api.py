from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent import triage_agent
import logging
from security import LLaMAPromptInjectionHook
from agentkernel.core.model import AgentRequestText, AgentReplyText
from agentkernel.core import Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ak.govstay.api")

app = FastAPI(title="GovStay Agent API", description="REST API for the GovStay multi-agent system powered by Local LLaMA")

import re
import json

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default-thread"

class ChatResponse(BaseModel):
    reply: str
    agent_name: str | None = None
    ui_state: dict | None = None

from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk, AIMessage
import asyncio

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    logger.info(f"Received message for thread {request.thread_id}: {request.message}")
    config = {"configurable": {"thread_id": request.thread_id}}
    
    async def event_generator():
        try:
            # Run security check first
            hook = LLaMAPromptInjectionHook()
            session = Session(id=request.thread_id)
            agent_requests = [AgentRequestText(text=request.message, session_id=request.thread_id)]
            
            hook_result = await hook.on_run(session=session, agent=None, requests=agent_requests)
            
            if isinstance(hook_result, AgentReplyText):
                yield f"data: {json.dumps({'text': hook_result.text, 'agent': 'SecurityGuard'})}\n\n"
                return
                
            # Stream from LangGraph
            # We want to buffer chunks so we can intercept [UI_SYNC]
            buffer = ""
            sync_mode = False
            sync_buffer = ""
            last_agent_name = None
            
            async for msg, metadata in triage_agent.astream({"messages": [("user", request.message)]}, config=config, stream_mode="messages"):
                # We only care about AI messages
                if not isinstance(msg, (AIMessage, AIMessageChunk)) or not msg.content:
                    continue
                    
                # The custom_router uses lite_model.invoke() during an edge from the supervisor.
                # LangGraph captures this LLM call. We must ignore it so the user doesn't see "search_agent" printed.
                node_name = metadata.get("langgraph_node")
                valid_nodes = ["greeting_agent", "search_agent", "verification_agent", "booking_agent", "document_agent", "approval_agent", "tool_fixer"]
                if node_name not in valid_nodes:
                    continue
                    
                chunk = str(msg.content)
                agent_name = msg.name if hasattr(msg, "name") and msg.name else node_name
                if agent_name:
                    last_agent_name = agent_name
                
                if not sync_mode:
                    buffer += chunk
                    if "[UI_SYNC]" in buffer:
                        sync_mode = True
                        parts = buffer.split("[UI_SYNC]", 1)
                        visible_text = parts[0]
                        sync_buffer = parts[1] if len(parts) > 1 else ""
                    elif re.search(r"\{\s*\"name\"\s*:", buffer):
                        # Hide raw JSON tool calls from being streamed to the user
                        # The tool_fixer_node will handle executing it later
                        sync_mode = True
                        sync_buffer = "" # We don't need to parse tool calls in the API, so just discard it from view
                    else:
                        # Yield the chunk directly
                        yield f"data: {json.dumps({'text': chunk, 'agent': last_agent_name})}\n\n"
                        # Keep a short buffer for the string matching
                        if len(buffer) > 20:
                            buffer = buffer[-20:]
                else:
                    sync_buffer += chunk

            # After the loop finishes, parse sync_buffer if we were in sync mode
            if sync_mode:
                match = re.search(r"\{.*?\}", sync_buffer, re.DOTALL)
                if match:
                    try:
                        ui_state = json.loads(match.group(0))
                        yield f"data: {json.dumps({'ui_state': ui_state})}\n\n"
                    except Exception as e:
                        logger.error(f"Failed to parse UI_SYNC JSON: {e}")
                        
        except Exception as e:
            logger.error(f"Error processing chat request: {str(e)}")
            yield f"data: {json.dumps({'text': f'Error: {str(e)}'})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    # Run the server on all interfaces so other developers can access it on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8001)
