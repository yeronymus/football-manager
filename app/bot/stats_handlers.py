
from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db.models import User, GameStats, PlayerProfile
from app.core.repositories.user_repository import UserRepository

router = Router()

@router.message(Command("top"))
async def cmd_top(message: types.Message):
    if message.chat.type != "private":
        try:
            await message.delete()
        except:
            pass
        return

    from app.config import settings
    base = settings.webapp_url.rstrip("/")
    web_app_url = f"{base}/web/leaderboard.html?v=7"
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="🏆 Открыть Лидерборд", 
            web_app=types.WebAppInfo(url=web_app_url)
        )]
    ])
    
    await message.answer(
        "Нажмите кнопку ниже, чтобы открыть Лидерборд:",
        reply_markup=kb
    )
