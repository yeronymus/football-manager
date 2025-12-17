from aiogram import Router, F, types
from aiogram.filters import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Game, Signup, User, SignupStatus, GameStatus, Team
from app.config import settings
from app.bot.balancer import balance_teams, Player
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard
import logging

router = Router()

router = Router()

async def run_draft_logic(game_id: int, session: AsyncSession, bot, target_chat_id: int):
    game = await session.get(Game, game_id)
    if not game:
        return

    # Fetch Active Signups
    result = await session.execute(
        select(User).join(Signup).where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
    )
    users = result.scalars().all()

    if len(users) < 1:
        await bot.send_message(target_chat_id, f"⚠️ **{game.location}**: Слишком мало игроков ({len(users)}).")
        return

    # Run Balancer
    players = [Player(u) for u in users]
    team_a, team_b = balance_teams(players)

    # Format Message
    # Format Message
    date_str = game.date_time.strftime('%d.%m %H:%M')
    text = f"⚽ <b>Драфт: {date_str}</b>\n"
    text += f"📍 {game.location}"

    web_app_url = f"{settings.WEBAPP_URL}/web/draft.html?game_id={game.id}"
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⚽ Драфт", web_app=types.WebAppInfo(url=web_app_url))]
    ])
    
    await bot.send_message(target_chat_id, text, reply_markup=kb, parse_mode="HTML")

@router.message(Command("draft"))
@router.message(F.text == "🔀 Шаффл")
async def cmd_draft(message: types.Message, session: AsyncSession):
    if message.text == "🔀 Шаффл":
        try:
            await message.delete()
        except:
            pass
    if message.from_user.id not in settings.ADMIN_IDS:
        return

    if message.chat.type in ["group", "supergroup"]:
        query = select(Game).where(Game.chat_id == message.chat.id, Game.status == GameStatus.OPEN)
    else:
        query = select(Game).where(Game.status == GameStatus.OPEN)

    result = await session.execute(query)
    games = result.scalars().all()

    if not games:
        await message.answer("Нет открытых игр.")
        return

    if len(games) == 1:
        await run_draft_logic(games[0].id, session, message.bot, message.from_user.id)
    else:
        buttons = []
        for g in games:
            btn_text = f"{g.location} ({g.date_time.strftime('%d.%m')})"
            buttons.append([types.InlineKeyboardButton(text=btn_text, callback_data=f"select_draft_{g.id}")])
        
        await message.answer("Выберите игру для драфта:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("select_draft_"))
async def process_draft_selection(callback: types.CallbackQuery, session: AsyncSession):
    game_id = int(callback.data.split("_")[2])
    await run_draft_logic(game_id, session, callback.bot, callback.from_user.id)
    await callback.message.delete()

@router.callback_query(F.data.startswith("publish_"))
async def process_publish(callback: types.CallbackQuery, session: AsyncSession):
    if callback.from_user.id not in settings.ADMIN_IDS:
        return

    game_id = int(callback.data.split("_")[1])
    game = await session.get(Game, game_id)
    
    if not game:
        await callback.answer("Игра не найдена")
        return

    # Update Game Status? Or just message?
    # Let's keep status OPEN until played? Or change to ACTIVE?
    # Plan says: Game status -> ACTIVE.
    game.status = GameStatus.ACTIVE
    await session.commit()

    # Update Public Message
    public_text = await format_game_message(game, session)
    try:
        if game.message_id:
            await callback.bot.edit_message_text(
                chat_id=game.chat_id,
                message_id=game.message_id,
                text=public_text,
                reply_markup=get_game_keyboard(game_id),
                parse_mode="HTML"
            )
            await callback.bot.send_message(game.chat_id, "📢 **Составы утверждены!** Чекайте закреп.")
    except Exception as e:
        logging.error(f"Publish error: {e}")

    await callback.message.edit_text("✅ **Опубликовано!**")

@router.message(Command("finish"))
async def cmd_finish(message: types.Message):
    if message.from_user.id not in settings.ADMIN_IDS:
        return

    web_app_url = f"{settings.WEBAPP_URL}/web/finish.html"
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🏁 Завершить матч", web_app=types.WebAppInfo(url=web_app_url))]
    ])
    
    await message.answer("Открыть панель завершения матча:", reply_markup=kb)
