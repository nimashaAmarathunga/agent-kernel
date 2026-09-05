import asyncio
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="llama3.1", 
    base_url="http://localhost:11434/v1", 
    api_key="ollama", 
    temperature=0,
    model_kwargs={"response_format": {"type": "json_object"}}
)

async def test():
    prompt = """You are a data extraction bot. I am giving you the raw text extracted from a bank transfer slip.
Your job is to find the EXACT amount that was transferred.

Raw text from slip:
Bank Transfer Payment Slip 
Date: 2026-08-03
To: GovStay Official Bank Account 
Amount Transferred: 7000 LKR 
Status: SUCCESS

Output a strict JSON object with this exact format, and NOTHING else:
{"found": true, "amount": 1234.50}
If you cannot find any amount, output:
{"found": false, "amount": 0}
"""
    try:
        response = await llm.ainvoke(prompt)
        print("Response:", response.content)
    except Exception as e:
        print("Exception caught:", e)

asyncio.run(test())
