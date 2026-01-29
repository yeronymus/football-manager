import asyncio
from unittest.mock import AsyncMock, MagicMock
from aiogram import types
from aiogram.filters import CommandObject
from app.bot.handlers.common import cmd_start
from app.bot.fsm import Registration
from app.db.models import User

async def test_start_in_group_repro():
    # Mocks
    message = AsyncMock(spec=types.Message)
    message.chat.type = "group"
    message.chat.id = -100123456789
    message.from_user.id = 123456789
    message.text = "/start"
    
    command = CommandObject(prefix="/", command="start", args=None)
    state = AsyncMock()
    session = AsyncMock()
    
    # Mock UserService to return None (User not found)
    # We need to patch the UserService instantiation inside cmd_start
    # or better, mock the session execution to return None for the user query
    # But cmd_start instantiates UserService(session).
    # Let's mock the session.execute result.
    
    # In UserService.get_user: result = await session.execute(select(User)...)
    # create_user is not called in start, only get_user.
    
    # Mocking the session.execute result for get_user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None # User not found
    session.execute.return_value = mock_result

    print("--- Running cmd_start in GROUP chat (User generic) ---")
    try:
        await cmd_start(message, command, state, session)
    except Exception as e:
        print(f"Caught expected exception (if any): {e}")

    # Check if state was set
    # The BUG: It sets state to Registration.waiting_for_name even in group chat
    print(f"State set call count: {state.set_state.call_count}")
    
    if state.set_state.called:
        args = state.set_state.call_args[0]
        print(f"State set to: {args[0]}")
        if args[0] == Registration.waiting_for_name:
            print("[FAIL] Bug Reproduced: Registration started in GROUP chat!")
        else:
            print("[INFO] State set to something else.")
    else:
        print("[PASS] Registration NOT started in group chat.")

if __name__ == "__main__":
    asyncio.run(test_start_in_group_repro())
