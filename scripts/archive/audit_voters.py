import asyncio
import os
import sys
from sqlalchemy import select, func
from app.db.database import async_session_maker
from app.db.models import Vote, User, Signup, SignupStatus

GAME_ID = 2

async def audit_voters():
    print(f"AUDIT: Checking votes for Game {GAME_ID}...")
    async with async_session_maker() as session:
        # 1. Get List of all ACTIVE players
        res = await session.execute(
            select(User.full_name, User.user_id)
            .join(Signup, Signup.user_id == User.user_id)
            .where(Signup.game_id == GAME_ID, Signup.status == SignupStatus.ACTIVE)
            .order_by(User.full_name)
        )
        all_players = res.all() # [(Name, ID), ...]
        
        # 2. Get List of Voters (Distinct)
        res = await session.execute(
            select(Vote.voter_id, func.count(Vote.id))
            .where(Vote.game_id == GAME_ID)
            .group_by(Vote.voter_id)
        )
        voters_map = {row[0]: row[1] for row in res.all()} # ID -> VoteCount (1 or 2)
        
        print("\n--- VOTING STATUS ---\n")
        voted_count = 0
        for name, uid in all_players:
            count = voters_map.get(uid, 0)
            status = "❌ NOT VOTED"
            if count == 1:
                status = "⚠️ Part (1/2)"
                voted_count += 1
            elif count >= 2:
                status = "✅ DONE (2/2)"
                voted_count += 1
            
            print(f"{status} - {name} (ID: {uid})")
            
        print(f"\nTotal Unique Voters: {voted_count} / {len(all_players)}")
        print(f"Total Vote Rows: {sum(voters_map.values())}")

if __name__ == "__main__":
    asyncio.run(audit_voters())
