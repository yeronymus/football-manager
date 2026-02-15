
import asyncio
import os
from aiogram import Bot

# FROM production.env
BOT_TOKEN = "8067557564:AAGpWa9lF3jdPS4umdi-peX2H3cOXfwUW4E"

async def main():
    bot = Bot(token=BOT_TOKEN)
    try:
        me = await bot.get_me()
        print(f"USERNAME:{me.username}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
