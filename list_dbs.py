import asyncio
from sqlalchemy import text
from app.db.database import get_session

async def list_dbs():
    print("Listing databases...")
    async for session in get_session():
        result = await session.execute(text("SELECT datname FROM pg_database WHERE datistemplate = false;"))
        dbs = result.scalars().all()
        for db in dbs:
            print(f"Database: {db}")

if __name__ == "__main__":
    asyncio.run(list_dbs())
