import asyncio
from dotenv import load_dotenv
load_dotenv()

from workflows.graph import triage_agent
from agentkernel.framework.langgraph.langgraph import LangGraphRunner, LangGraphAgent
from agentkernel.core.model import AgentRequestText
from agentkernel.core.runtime import Session

async def main():
    print("Testing triage_agent through LangGraphRunner")
    runner = LangGraphRunner()
    agent_wrapper = LangGraphAgent(name="govstay", runner=runner, agent=triage_agent)
    from langchain_core.messages import HumanMessage
    requests = [HumanMessage(content="Create a booking for EMP-123 in OLD-101 from 2026-09-03 to 2026-09-05")]
    
    async for event in triage_agent.astream_events(
        input={"messages": requests},
        version="v2",
        config={"configurable": {"thread_id": "test"}}
    ):
        print("Event:", event["event"], "Node:", event.get("metadata", {}).get("langgraph_node"), "Name:", event["name"])
        if event["event"] == "on_chat_model_end":
            print(event["data"])

if __name__ == "__main__":
    asyncio.run(main())
