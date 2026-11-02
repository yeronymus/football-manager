from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("top"))
async def cmd_top(message: types.Message, session: AsyncSession):
    if message.chat.type != "private":
        try:
            await message.delete()
        except:
            pass
        return

    from app.bot.utils import resolve_chat_language
    from app.bot.i18n import t
    user_lang = await resolve_chat_language(session, message.from_user.id)

    from app.config import settings
    base = settings.webapp_url.rstrip("/")
    web_app_url = f"{base}/web/leaderboard.html?v=7"
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text=t("btn_open_leaderboard", locale=user_lang), 
            web_app=types.WebAppInfo(url=web_app_url)
        )]
    ])
    
    await message.answer(
        t("open_leaderboard_prompt", locale=user_lang),
        reply_markup=kb
    )
