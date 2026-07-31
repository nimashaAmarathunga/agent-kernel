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

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    logger.info(f"Received message for thread {request.thread_id}: {request.message}")
    config = {"configurable": {"thread_id": request.thread_id}}
    
    try:
        # Run security check first
        hook = LLaMAPromptInjectionHook()
        # Mocking session and request for the hook
        session = Session(id=request.thread_id)
        agent_requests = [AgentRequestText(text=request.message, session_id=request.thread_id)]
        
        hook_result = await hook.on_run(session=session, agent=None, requests=agent_requests)
        
        # If the hook returns an AgentReplyText, it means it blocked the request
        if isinstance(hook_result, AgentReplyText):
            return ChatResponse(
                reply=hook_result.text,
                agent_name="SecurityGuard"
            )
            
        # Run the langgraph agent
        response = await triage_agent.ainvoke(
            {"messages": [("user", request.message)]}, 
            config=config
        )
        
        # Extract the last message from the agent
        last_message = response["messages"][-1]
        reply_text = last_message.content
        
        # Parse [UI_SYNC]
        ui_state = None
        sync_match = re.search(r"\[UI_SYNC\]\s*(\{.*?\})", reply_text, re.DOTALL)
        if sync_match:
            try:
                ui_state = json.loads(sync_match.group(1))
                # Remove it from the text so it doesn't show to the user
                reply_text = reply_text.replace(sync_match.group(0), "").strip()
            except Exception as e:
                logger.error(f"Failed to parse UI_SYNC JSON: {e}")
        
        # We can extract the agent's name if we want to know who responded
        agent_name = last_message.name if hasattr(last_message, "name") else None
        
        return ChatResponse(
            reply=reply_text,
            agent_name=agent_name,
            ui_state=ui_state
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Run the server on all interfaces so other developers can access it on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8001)
