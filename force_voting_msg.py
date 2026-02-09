import asyncio
import os
from app.db.database import async_session_maker
from app.db.models import Game, GameStatus
from sqlalchemy import select
from app.bot.main import bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from app.config import settings

async def force_vote():
    async with async_session_maker() as session:
        # Find Game 2
        result = await session.execute(select(Game).where(Game.id == 2))
        game = result.scalar_one_or_none()
        
        if not game:
            print("Game 2 not found")
            return

        print(f"Targeting Game {game.id}")
        
        # Set Finished
        game.status = GameStatus.FINISHED
        await session.commit()
        print("Set status to FINISHED")

        # Send Voting Message
        vote_url = f"{settings.webapp_url}/web/vote.html?game_id={game.id}"
        print(f"Vote URL: {vote_url}")
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🏆 Голосование (MVP)", web_app=WebAppInfo(url=vote_url))
        ]])
        
        try:
            await bot.send_message(
                chat_id=game.chat_id,
                text=f"Матч в <b>{game.location}</b> завершен.\n\n<b>Голосование за MVP открыто!</b>\nВыберите лучших игроков (по одному от команды) по кнопке ниже.\n<i>(Результаты через 5 часов)</i>",
                reply_markup=kb,
                parse_mode="HTML"
            )
            print("Voting message sent (WebApp).")
        except Exception as e:
            print(f"WebApp button failed: {e}")
            # Fallback
            deep_link = f"https://t.me/fm_metabot?start=game_{game.id}"
            kb_fallback = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🏆 Голосование (Ссылка)", url=deep_link)
            ]])
            await bot.send_message(
                chat_id=game.chat_id,
                text=f"Матч в <b>{game.location}</b> завершен.\n\n<b>Голосование за MVP открыто!</b>\n(WebApp кнопка недоступна, используйте ссылку)",
                reply_markup=kb_fallback,
                parse_mode="HTML"
            )
            print("Voting message sent (DeepLink Fallback).")

if __name__ == "__main__":
    asyncio.run(force_vote())
