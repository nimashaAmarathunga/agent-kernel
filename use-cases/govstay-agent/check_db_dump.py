import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv('c:/Users/USER/Desktop/AI degree/IDEALIZE 2026/agent-kernel/use-cases/govstay-agent/.env')
DB_URL = os.environ.get('DATABASE_URL')

async def main():
    conn = await asyncpg.connect(DB_URL, statement_cache_size=0)
    
    bookings = await conn.fetch('SELECT id, "bookingId", "userId", status, "approvalReason", "totalCost" FROM bookings ORDER BY "createdAt" DESC LIMIT 5')
    for b in bookings:
        print(b)
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
