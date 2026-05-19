import time
from sqlalchemy import create_engine, select, func, text, Column, Integer, String, BigInteger, ForeignKey, Enum as SQLEnum, Float, Boolean, ARRAY, DateTime
from sqlalchemy.orm import selectinload, declarative_base, relationship, sessionmaker
from app.db.models import Position
import enum

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    player_position = Column(SQLEnum(Position, name="user_position"), nullable=False)
    stats_matches = Column(Integer, default=0)
    stats_mvp = Column(Integer, default=0)
    rating = Column(Integer, default=100)  # ELO Rating
    games_played = Column(Integer, default=0)

    profiles = relationship("PlayerProfile", back_populates="user", cascade="all, delete-orphan")

class Chat(Base):
    __tablename__ = "chats"

    chat_id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String, nullable=False)

    players = relationship("PlayerProfile", back_populates="chat", cascade="all, delete-orphan")

class PlayerProfile(Base):
    __tablename__ = "player_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"), nullable=False, index=True)

    rating = Column(Integer, default=100)
    games_played = Column(Integer, default=0)
    stats_matches = Column(Integer, default=0)
    stats_mvp = Column(Integer, default=0)

    user = relationship("User", back_populates="profiles")
    chat = relationship("Chat", back_populates="players")

engine = create_engine(
    "sqlite:///:memory:",
    echo=False
)

SessionLocal = sessionmaker(
    engine, expire_on_commit=False
)

def setup_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        # Insert 100 users, 100 chats, 1000 player profiles
        users = [User(user_id=i, full_name=f"User {i}", player_position=Position.ST) for i in range(1, 101)]
        chats = [Chat(chat_id=i, title=f"Chat {i}") for i in range(1, 101)]
        session.add_all(users)
        session.add_all(chats)
        session.flush()

        profiles = []
        for i in range(1, 1001):
            profiles.append(PlayerProfile(
                id=i, user_id=(i % 100) + 1, chat_id=((i * 3) % 100) + 1, games_played=5
            ))
        session.add_all(profiles)
        session.commit()

def benchmark_old():
    # simulate the N+1 problem
    start = time.perf_counter()
    with SessionLocal() as session:
        profiles = session.execute(select(PlayerProfile).where(PlayerProfile.games_played >= 1))
        for p in profiles.scalars().all():
            user = session.get(User, p.user_id)
            chat = session.get(Chat, p.chat_id)
            # do something with user and chat
            _ = user.full_name
            _ = chat.title
    return time.perf_counter() - start

def benchmark_new():
    start = time.perf_counter()
    with SessionLocal() as session:
        profiles = session.execute(
            select(PlayerProfile)
            .options(selectinload(PlayerProfile.user), selectinload(PlayerProfile.chat))
            .where(PlayerProfile.games_played >= 1)
        )
        for p in profiles.scalars().all():
            user = p.user
            chat = p.chat
            _ = user.full_name
            _ = chat.title
    return time.perf_counter() - start

def main():
    print("Setting up DB...")
    setup_db()

    print("Warming up...")
    # Warmup
    benchmark_old()
    benchmark_new()

    print("Running benchmarks...")
    t_old = benchmark_old()
    t_new = benchmark_new()

    print(f"Old time: {t_old:.4f}s")
    print(f"New time: {t_new:.4f}s")
    print(f"Improvement: {t_old / t_new:.2f}x faster")

if __name__ == "__main__":
    main()
