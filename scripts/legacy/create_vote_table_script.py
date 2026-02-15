import asyncio
import os
import sys
from sqlalchemy import text
from app.db.database import async_session_maker

async def create_vote_table():
    print("CHECKING/CREATING Vote Table...")
    async with async_session_maker() as session:
        # Check if table exists
        try:
            await session.execute(text("SELECT 1 FROM votes LIMIT 1"))
            print("Table 'votes' already exists.")
        except Exception:
            print("Table 'votes' MISSING. Creating...")
            
            # Raw SQL creation to be safe and dependency-free
            create_sql = """
            CREATE TABLE IF NOT EXISTS votes (
                id SERIAL PRIMARY KEY,
                game_id INTEGER NOT NULL,
                voter_id BIGINT NOT NULL,
                target_id BIGINT NOT NULL,
                vote_team VARCHAR(10) NOT NULL,
                CONSTRAINT fk_votes_game FOREIGN KEY (game_id) REFERENCES games(id),
                CONSTRAINT fk_votes_voter FOREIGN KEY (voter_id) REFERENCES users(user_id),
                CONSTRAINT fk_votes_target FOREIGN KEY (target_id) REFERENCES users(user_id),
                CONSTRAINT unique_vote_team UNIQUE (game_id, voter_id, vote_team)
            );
            """
            try:
                await session.execute(text(create_sql))
                await session.commit()
                print("✅ Table 'votes' created successfully!")
            except Exception as e:
                print(f"❌ Failed to create table: {e}")

if __name__ == "__main__":
    asyncio.run(create_vote_table())
