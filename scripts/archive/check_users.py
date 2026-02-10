import asyncio
from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import User

async def main():
    try:
        async with async_session_maker() as session:
            result = await session.execute(select(User).order_by(User.created_at.desc()).limit(20))
            users = result.scalars().all()
            print(f"{'ID':<12} | {'Name':<25} | {'Username':<15} | {'Created At'}")
            print("-" * 75)
            for u in users:
                c = u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "N/A"
                print(f"{u.user_id:<12} | {u.full_name[:25]:<25} | {str(u.username)[:15]:<15} | {c}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
