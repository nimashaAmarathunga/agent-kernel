import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv('c:/Users/USER/Desktop/AI degree/IDEALIZE 2026/agent-kernel/use-cases/govstay-agent/.env')
DB_URL = os.environ.get('DATABASE_URL')

async def main():
    conn = await asyncpg.connect(DB_URL)
    
    b_records = await conn.fetch('SELECT id, "bookingId", status, "approvalReason", "totalCost" FROM bookings WHERE "bookingId" ILIKE \'%245503B%\' OR id::text ILIKE \'%245503B%\'')
    print("Bookings:", b_records)
    
    for b in b_records:
        slip = await conn.fetch('SELECT * FROM payment_slips WHERE "bookingId" = $1', b['id'])
        print(f"Slip for {b['bookingId']}:", slip)
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
