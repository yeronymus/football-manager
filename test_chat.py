
import asyncio
from app.bot.main import bot

async def test():
    chat_id = -1003437568976
    print(f"Testing Chat ID: {chat_id}")
    try:
        msg = await bot.send_message(chat_id, "🔔 Test Message (Connectivity Check)")
        print(f"Success! Msg ID: {msg.message_id}")
    except Exception as e:
        print(f"FAILURE: {e}")

if __name__ == "__main__":
    asyncio.run(test())
