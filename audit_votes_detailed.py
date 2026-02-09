import asyncio
from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import Vote, User, Team

async def get_vote_details():
    async with async_session_maker() as session:
        # Create a mapping for user IDs to names
        users_res = await session.execute(select(User.user_id, User.full_name))
        user_names = {row.user_id: row.full_name for row in users_res.all()}
        
        # Fetch all votes for game 2
        votes_res = await session.execute(
            select(Vote.voter_id, Vote.target_id, Vote.vote_team)
            .where(Vote.game_id == 2)
            .order_by(Vote.vote_team, Vote.voter_id)
        )
        
        print("\n--- КТО ЗА КОГО ГОЛОСОВАЛ (Матч #2) ---")
        
        current_voter = None
        voter_votes = {}
        
        for voter_id, target_id, team in votes_res.all():
            voter_name = user_names.get(voter_id, f"ID:{voter_id}")
            target_name = user_names.get(target_id, f"ID:{target_id}")
            
            if voter_id not in voter_votes:
                voter_votes[voter_id] = {"name": voter_name, "votes": []}
            
            voter_votes[voter_id]["votes"].append(f"{team.value}: {target_name}")

        for vid, data in voter_votes.items():
            votes_str = " | ".join(data["votes"])
            print(f"👤 {data['name']} проголосовал за:")
            print(f"   {votes_str}")

if __name__ == "__main__":
    asyncio.run(get_vote_details())
