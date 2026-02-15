
import asyncio
import os
from sqlalchemy import text
from app.db.database import async_session_maker

async def main():
    async with async_session_maker() as session:
        result = await session.execute(text("SELECT full_name, username FROM users ORDER BY full_name"))
        users = result.fetchall()
        print(f"Total Users: {len(users)}")
        print("Explicit List:")
        for u in users:
            print(f"- {u.full_name} (@{u.username})")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
