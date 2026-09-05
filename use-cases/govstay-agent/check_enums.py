import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv('c:/Users/USER/Desktop/AI degree/IDEALIZE 2026/agent-kernel/use-cases/govstay-agent/.env')
DB_URL = os.environ.get('DATABASE_URL')

async def main():
    conn = await asyncpg.connect(DB_URL, statement_cache_size=0)
    types = await conn.fetch("SELECT enumlabel FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid WHERE t.typname = 'BookingStatus'")
    print('Booking statuses:', types)
    ptypes = await conn.fetch("SELECT enumlabel FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid WHERE t.typname = 'VerificationStatus'")
    print('Payment slip statuses:', ptypes)
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
