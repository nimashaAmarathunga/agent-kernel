import asyncio
from dotenv import load_dotenv
load_dotenv()

from agents.booking_agent import booking_agent
from langchain_core.messages import HumanMessage

async def main():
    print("Testing booking_agent stream events")
    messages = [HumanMessage(content="Create a booking for 245503B in OLD-101 from 2026-09-03 to 2026-09-05")]
    async for event in booking_agent.astream_events(
        input={"messages": messages},
        version="v2"
    ):
        if event["event"] == "on_tool_end":
            print("on_tool_end event:", event["name"])
            print("data output type:", type(event["data"].get("output")))
            print("data output:", repr(event["data"].get("output")))
            
            output = event["data"].get("output")
            if hasattr(output, "content"):
                output = output.content
            print("content:", repr(output))

if __name__ == "__main__":
    asyncio.run(main())
