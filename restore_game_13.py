import asyncio
import os
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.models import Game, Signup, User, SignupStatus

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql+asyncpg://postgres:password@db:5432/football"

engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Clean names from user message (removing numbers and potential positions if we can match fuzzily)
# Assuming DB has "Yeldos Ismailov LW (LM, CDM)" as full_name or just "Yeldos Ismailov"
# We will try exact match first, then startswith.
TARGET_NAMES = [
    "Yeldos Ismailov LW (LM, CDM)",
    "Mukhammed Aleumet Askar FWD (LB, RB, CDM)",
    "Yernur Bauyrzhanuly LB (RB)",
    "Aidyn Galymbekov RM (CM, RB)",
    "Said Soltanzade CDM (LW)",
    "Bakyrkhan Daryn CM (CB, LB, RW)",
    "Dias Bekbosyn CAM (CM, FWD, CDM, LW, RW)",
    "Assylbek Nurmagambetov RW (FWD, CAM)",
    "Aldiyar Kazbekov CAM (CM, CDM)",
    "Aktan Abdullaatov RB (GK, CB, LB)",
    "Ansar Tanirbay CDM",
    "Umid Kamilov CB (RB, LB, CDM, FWD, LW)",
    "Zhanibek Xenbek LW (RB, LB, RW, CM)",
    "Miras Mukanov RW (LW, CM)",
    "Bakhtiyar Temirbayev RB",
    "Arsen Kudaibergen CM (CDM, LM, LW, CAM, FWD, RW, RB)",
    "Raimbek Sarzhakov",
    "Vlad Lishanlo"
]

async def restore():
    async with async_session() as session:
        print("--- RESTORING GAME 13 ---")
        
        # 1. Update Game Details
        game = await session.get(Game, 13)
        if not game:
            print("Game 13 not found!")
            return

        print(f"Old Game: Slots={game.max_players}, Date={game.date_time}")
        
        # Set max players to 18
        game.max_players = 18
        
        # Set Date to Today 19:00 (Assuming server time zone? Or just leave it if user said 'today 19:00' and it's 21:00)
        # If we change it, we should ensure it's correct.
        # User said "game happens in the past at 19:00 today".
        # We will iterate 18 players and force them active.
        
        await session.commit()
        print("Updated Game 13 settings.")

        # 2. Restore Players
        print(f"Restoring {len(TARGET_NAMES)} players...")
        
        active_count = 0
        
        for name_raw in TARGET_NAMES:
            # Clean strict matching
            # Filter DB users.
            # Strategy: Get all users, find best match? Or ILIKE.
            
            # Since names are complex, we try to match the BEGINNING of the full_name or EXACT match.
            # Assuming user text dump IS the full_name from DB.
            
            uname = name_raw.strip()
            
            # Find User
            stmt = select(User).where(User.full_name == uname)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            
            if not user:
                # Try partial match (some might not have positions in DB name vs Text)
                # Split and take first 2 words?
                parts = uname.split()
                if len(parts) >= 2:
                    short_name = f"{parts[0]} {parts[1]}"
                    stmt = select(User).where(User.full_name.ilike(f"{short_name}%"))
                    res = await session.execute(stmt)
                    user = res.scalar_one_or_none()
            
            if not user:
                print(f"❌ User NOT FOUND: {uname}")
                continue
                
            print(f"✅ Found User: {user.full_name} (ID: {user.id})")
            
            # Find or Create Signup
            signup = await session.scalar(select(Signup).where(Signup.user_id == user.id, Signup.game_id == 13))
            
            if signup:
                if signup.status != SignupStatus.ACTIVE:
                    print(f"   -> Updating status {signup.status} -> ACTIVE")
                    signup.status = SignupStatus.ACTIVE
                else:
                    print(f"   -> Already ACTIVE")
            else:
                print(f"   -> Creating NEW Signup")
                signup = Signup(
                    user_id=user.id,
                    game_id=13,
                    status=SignupStatus.ACTIVE,
                    is_paid=False,
                    created_at=datetime.utcnow()
                )
                session.add(signup)
            
            active_count += 1
            
        await session.commit()
        print(f"--- RESTORE COMPLETE. Active Players: {active_count}/18 ---")

        # 3. Trigger Dashboard Update?
        # We can try, but simplest is to ask user to run /fix_game 13 again.

if __name__ == "__main__":
    asyncio.run(restore())
