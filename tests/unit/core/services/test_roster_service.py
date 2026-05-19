import pytest
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.uow import UnitOfWork
from app.core.services.roster import RosterService
from app.db.models import Game, User, Signup, Position, Team, SignupStatus, GameStatus, GameType, Chat

@pytest.mark.asyncio
async def test_update_teams(session: AsyncSession):
    # 1. Setup base structures (creator user, chat, game)
    creator = User(
        user_id=1,
        username="creator",
        full_name="Creator User",
        player_position=Position.MID,
        alt_positions=[]
    )
    chat = Chat(chat_id=-1001, title="Test Chat")
    session.add_all([creator, chat])
    await session.commit()

    game = Game(
        id=1,
        chat_id=chat.chat_id,
        created_by=creator.user_id,
        date_time=datetime.now() + timedelta(days=1),
        location="Strahov Pitch",
        max_players=10,
        status=GameStatus.OPEN,
        game_type=GameType.REGULAR
    )
    session.add(game)
    await session.commit()

    # 2. Add players to the game:
    # 4 players: 2 active, 2 in reserve
    p1 = User(user_id=101, username="p1", full_name="Player 1", player_position=Position.DEF, alt_positions=[])
    p2 = User(user_id=102, username="p2", full_name="Player 2", player_position=Position.MID, alt_positions=[])
    p3 = User(user_id=103, username="p3", full_name="Player 3", player_position=Position.FWD, alt_positions=[])
    p4 = User(user_id=104, username="p4", full_name="Player 4", player_position=Position.GK, alt_positions=[])
    session.add_all([p1, p2, p3, p4])
    await session.commit()

    s1 = Signup(game_id=game.id, user_id=p1.user_id, status=SignupStatus.ACTIVE)
    s2 = Signup(game_id=game.id, user_id=p2.user_id, status=SignupStatus.ACTIVE)
    s3 = Signup(game_id=game.id, user_id=p3.user_id, status=SignupStatus.RESERVE)
    s4 = Signup(game_id=game.id, user_id=p4.user_id, status=SignupStatus.RESERVE)
    session.add_all([s1, s2, s3, s4])
    await session.commit()

    # 3. Initialize UnitOfWork and RosterService
    uow = UnitOfWork(session=session)
    await uow.__aenter__()
    service = RosterService(uow)

    # 4. Call update_teams:
    # team_a: [101, 103 (reserve promoted)]
    # team_b: [102, 104 (reserve promoted)]
    # positions mapping: CB for 101, GK for 104
    positions = {"101": "CB", "104": "GK"}
    
    promoted = await service.update_teams(
        game_id=game.id,
        team_a=[101, 103],
        team_b=[102, 104],
        team_c=[],
        unassigned=[],
        reserve=[],
        positions=positions
    )

    # Commit updates using the unit of work to persist database changes
    await uow.commit()

    # Verify that the two reserve players were promoted to active
    assert set(promoted) == {103, 104}

    # Refresh signups from session to assert their state
    await session.refresh(s1)
    await session.refresh(s2)
    await session.refresh(s3)
    await session.refresh(s4)

    assert s1.team == Team.A
    assert s1.position == Position.CB
    assert s1.status == SignupStatus.ACTIVE

    assert s2.team == Team.B
    assert s2.status == SignupStatus.ACTIVE

    assert s3.team == Team.A
    assert s3.status == SignupStatus.ACTIVE # Promoted!

    assert s4.team == Team.B
    assert s4.position == Position.GK
    assert s4.status == SignupStatus.ACTIVE # Promoted!
