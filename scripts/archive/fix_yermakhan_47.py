
import asyncio
import sys
sys.path.append('/app')
from app.db.database import async_session_maker
from app.db.models import User, Signup, SignupStatus
from sqlalchemy import select, or_

async def fix_yermakhan():
    async with async_session_maker() as session:
        # 1. Find User by pattern
        pattern = "%Yer%"
        res = await session.execute(
            select(User)
            .where(
                or_(
                    User.full_name.ilike(pattern),
                    User.username.ilike(pattern)
                )
            )
        )
        users = res.scalars().all()
        
        target_user = None
        print(f"Found {len(users)} users matching '{pattern}':")
        for u in users:
            print(f"- {u.user_id}: {u.full_name} (@{u.username})")
            if "Yermakhan" in (u.full_name or "") or "yermakhan" in (u.username or "").lower():
                target_user = u
        
        if not target_user:
            # Fallback: specific ID check might be needed if name doesn't match
            # But let's assume one of the matches is him.
            # If multiple, pick the one that sounds most like "Yermakhan"
            for u in users:
                if "Yermakhan" in u.full_name:
                    target_user = u
                    break
        
        if not target_user:
            print("Could not identify Yermakhan definitively.")
            return

        print(f"Targeting: {target_user.full_name} ({target_user.user_id})")
        
        # 2. Check Signup for Game 47
        stmt = select(Signup).where(Signup.game_id == 47, Signup.user_id == target_user.user_id)
        res = await session.execute(stmt)
        signup = res.scalar_one_or_none()
        
        if signup:
            print(f"Existing Signup found! Status: {signup.status}, Pos: {signup.position}")
            if signup.status != SignupStatus.ACTIVE:
                print("Setting status to ACTIVE...")
                signup.status = SignupStatus.ACTIVE
                # Ensure position is set
                if not signup.position:
                    signup.position = target_user.player_position or "MID"
                await session.commit()
                print("Updated.")
            else:
                print("User is already ACTIVE. Why not visible?")
                if not signup.position:
                    print("Position is missing! Setting to MID.")
                    signup.position = "MID"
                    await session.commit()
                    print("Updated Position.")
        else:
            print("No Signup found. Creating new ACTIVE signup...")
            new_signup = Signup(
                game_id=47,
                user_id=target_user.user_id,
                status=SignupStatus.ACTIVE,
                position=target_user.player_position or "MID"
            )
            session.add(new_signup)
            await session.commit()
            print("Created.")

if __name__ == "__main__":
    asyncio.run(fix_yermakhan())
