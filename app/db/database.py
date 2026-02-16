from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.debug)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed initial chats
    async with async_session_maker() as session:
        await seed_chats(session)

async def seed_chats(session: AsyncSession):
    from app.db.models import Chat
    from sqlalchemy import select
    
    for chat_data in settings.initial_chats:
        chat_id = chat_data["id"]
        title = chat_data["title"]
        
        # Check if exists
        chat = await session.get(Chat, chat_id)
        if not chat:
            print(f"Adding initial chat: {title} ({chat_id})")
            chat = Chat(chat_id=chat_id, title=title)
            session.add(chat)
    
    await session.commit()
