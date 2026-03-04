from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload
from app.db.models import Chat, Game, GameStatus
from app.config import settings

router = Router()

# Helper for Link Keyboard
def build_setup_keyboard(chats, current_admin_id):
    buttons = []
    for chat in chats:
        is_linked = chat.admin_chat_id == current_admin_id
        status_icon = "✅" if is_linked else "⬜"
        title = chat.title[:20] + ".." if len(chat.title) > 20 else chat.title
        buttons.append([types.InlineKeyboardButton(text=f"{status_icon} {title}", callback_data=f"setup_toggle_{chat.chat_id}")])
    buttons.append([types.InlineKeyboardButton(text="🔄 Обновить", callback_data="setup_refresh")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("get_id"))
async def cmd_get_id(message: types.Message, session: AsyncSession):
    # Ensure chat exists in DB
    chat = await session.get(Chat, message.chat.id)
    if not chat:
        chat = Chat(chat_id=message.chat.id, title=message.chat.title or "Unknown")
        session.add(chat)
        await session.commit()
    await message.answer(f"🆔 ID этого чата: <code>{message.chat.id}</code>\nЧат зарегистрирован.")

@router.message(Command("debug_game"))
async def cmd_debug_game(message: types.Message, command: CommandObject, session: AsyncSession):
    if message.from_user.id not in settings.admin_ids: return
    try:
        game_id = int(command.args)
    except:
        await message.answer("Usage: /debug_game <game_id>")
        return
    game = await session.get(Game, game_id)
    if not game:
        await message.answer("Game not found.")
        return
    chat = await session.get(Chat, game.chat_id)
    txt = f"🐞 **Debug Game #{game_id}**\nChat ID: `{game.chat_id}`\nTitle: {chat.title if chat else '?'}\nAdmin Msg: `{game.admin_message_id}`"
    await message.answer(txt, parse_mode="Markdown")

@router.message(Command("fix_game"))
async def cmd_fix_game(message: types.Message, command: CommandObject, session: AsyncSession):
    if message.from_user.id not in settings.admin_ids: return
    try:
        game_id = int(command.args)
        game = await session.get(Game, game_id)
        if not game: return
        chat = await session.get(Chat, game.chat_id)
        if chat:
            chat.admin_chat_id = message.chat.id
            game.admin_message_id = None
            await session.commit()
            from app.bot.admin_dashboard import update_dashboard_message
            await update_dashboard_message(message.bot, game_id, session, target_chat_id=message.chat.id)
            await message.answer("Fixed.")
    except Exception as e:
        await message.answer(f"Error: {e}")

# God Mode Logic
@router.message(Command("setup"))
async def cmd_setup_admin(message: types.Message):
    if message.from_user.id not in settings.admin_ids and message.from_user.id != settings.system_owner_id:
        return
    user = message.from_user
    text = f"🕹 <b>God Mode</b>\n👤 {user.full_name}"
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔗 Связи Чатов", callback_data="god_menu_links")],
        [types.InlineKeyboardButton(text="📂 Список Игр / Удаление", callback_data="god_menu_games")],
        [types.InlineKeyboardButton(text="❎ Закрыть", callback_data="god_close")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "god_close")
async def cb_god_close(callback: types.CallbackQuery):
    await callback.message.delete()

@router.callback_query(F.data.startswith("god_menu_"))
async def cb_god_menu(callback: types.CallbackQuery, session: AsyncSession):
    section = callback.data.split("_")[2]
    
    if section == "main":
        user = callback.from_user
        uid = user.id
        text = f"🕹 <b>God Mode</b>\n👤 Админ: <a href='tg://user?id={uid}'>{user.full_name}</a>\n"
        if callback.message.chat.type != "private":
             text += f"📍 Чат: {callback.message.chat.title} (<code>{callback.message.chat.id}</code>)\n"
        text += "\nВыберите действие:"
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔗 Связи Чатов (Links)", callback_data="god_menu_links")],
            [types.InlineKeyboardButton(text="📂 Список Игр / Удаление", callback_data="god_menu_games")],
            [types.InlineKeyboardButton(text="❎ Закрыть", callback_data="god_close")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        return

    if section == "links":
        result = await session.execute(select(Chat).where(Chat.chat_id != callback.message.chat.id))
        all_chats = result.scalars().all()
        kb = build_setup_keyboard(all_chats, callback.message.chat.id)
        kb.inline_keyboard.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="god_menu_main")])
        await callback.message.edit_text("🔗 <b>Управление Связями</b>\nОтметьте, какие чаты привязать к этому админ-чату:", reply_markup=kb, parse_mode="HTML")
        return

    if section == "games":
        current_time = func.now()
        result = await session.execute(
            select(Game).where(Game.status.in_([GameStatus.OPEN, GameStatus.ACTIVE]))
            .order_by(Game.date_time.desc())
        )
        games = result.scalars().all()
        
        if not games:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Назад", callback_data="god_menu_main")]])
            await callback.message.edit_text("📂 Нет активных игр.", reply_markup=kb)
            return

        buttons = []
        for g in games:
            status_emoji = "🟢" if g.status == GameStatus.OPEN else "⚽"
            d_str = g.date_time.strftime("%d.%m")
            txt = f"{status_emoji} {g.location} ({d_str})"
            buttons.append([types.InlineKeyboardButton(text=txt, callback_data=f"god_game_{g.id}")])
            
        buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="god_menu_main")])
        kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text("📂 <b>Активные игры:</b>", reply_markup=kb, parse_mode="HTML")
        return

@router.callback_query(F.data.startswith("god_game_"))
async def cb_god_game_detail(callback: types.CallbackQuery, session: AsyncSession):
    game_id = int(callback.data.split("_")[2])
    result = await session.execute(select(Game).where(Game.id == game_id).options(selectinload(Game.signups)))
    game = result.scalar_one_or_none()
    
    if not game:
        await callback.answer("Игра не найдена")
        return 
        
    text = f"⚽ <b>Игра #{game.id}</b>\n📍 {game.location}\n📅 {game.date_time}\n📊 Статус: {game.status}\n👥 Игроков: {len(game.signups)}"
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📢 Запостить в канал", callback_data=f"god_publish_chan_{game.id}")],
        [types.InlineKeyboardButton(text="🧨 Режим Удаления", callback_data=f"god_del_wait_{game.id}")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="god_menu_games")]
    ])
    try: await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except: pass # Ignore if same message

@router.callback_query(F.data.startswith("god_del_wait_"))
async def cb_god_delete_confirm(callback: types.CallbackQuery):
    game_id = int(callback.data.split("_")[3])
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🧨 УДАЛИТЬ НАВСЕГДА", callback_data=f"god_del_commit_{game_id}")],
        [types.InlineKeyboardButton(text="❌ ОТМЕНА", callback_data=f"god_game_{game_id}")]
    ])
    await callback.message.edit_text(f"⚠️ <b>ВЫ УВЕРЕНЫ?</b>\nЭто удалит игру #{game_id} и все записи.\nНЕОБРАТИМО.", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("god_del_commit_"))
async def cb_god_delete_commit(callback: types.CallbackQuery, session: AsyncSession):
    await callback.answer("⏳ Удаление...", show_alert=False)
    game_id = int(callback.data.split("_")[3])
    try:
        game = await session.get(Game, game_id)
        if not game:
             await callback.message.edit_text("❌ Игра не найдена.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 К списку", callback_data="god_menu_games")]]))
             return

        from sqlalchemy import delete
        from app.db.models import Signup, Vote, RatingHistory, GameStats
        
        await session.execute(delete(Signup).where(Signup.game_id == game_id))
        await session.execute(delete(Vote).where(Vote.game_id == game_id))
        await session.execute(delete(RatingHistory).where(RatingHistory.game_id == game_id))
        await session.execute(delete(GameStats).where(GameStats.game_id == game_id))
        
        if game.chat_id and game.message_id:
            try:
                await callback.bot.edit_message_text(chat_id=game.chat_id, message_id=game.message_id, text=f"❌ <b>Игра в {game.location} отменена администратором.</b>", parse_mode="HTML")
            except: pass
        
        await session.delete(game)
        await session.commit()
        
        # Reset ID sequence if last game deleted or to fill gaps (PostgreSQL)
        try:
            await session.execute(text("SELECT setval('games_id_seq', (SELECT COALESCE(MAX(id), 0) FROM games) + 1, false);"))
            await session.commit()
        except Exception as seq_err:
            logging.warning(f"Failed to reset sequence: {seq_err}")

        await callback.message.edit_text("✅ <b>Успешно удалено.</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 К списку", callback_data="god_menu_games")]]), parse_mode="HTML")
            
    except Exception as e:
        await session.rollback()
        await callback.message.edit_text(f"❌ Ошибка: {e}")

@router.callback_query(F.data.startswith("setup_toggle_"))
async def cb_setup_toggle(callback: types.CallbackQuery, session: AsyncSession):
    target_chat_id = int(callback.data.split("_")[2])
    chat = await session.get(Chat, target_chat_id)
    if not chat: return
    current_admin_id = callback.message.chat.id
    if chat.admin_chat_id == current_admin_id:
        chat.admin_chat_id = None
        action = "Отвязано"
    else:
        chat.admin_chat_id = current_admin_id
        action = "Привязано"
    await session.commit()
    result = await session.execute(select(Chat).where(Chat.chat_id != current_admin_id))
    all_chats = result.scalars().all()
    kb = build_setup_keyboard(all_chats, current_admin_id)
    kb.inline_keyboard.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="god_menu_main")])
    try: await callback.message.edit_reply_markup(reply_markup=kb)
    except: pass
    await callback.answer(action)

@router.callback_query(F.data == "setup_refresh")
async def cb_setup_refresh(callback: types.CallbackQuery, session: AsyncSession):
    current_admin_id = callback.message.chat.id
    result = await session.execute(select(Chat).where(Chat.chat_id != current_admin_id))
    all_chats = result.scalars().all()
    kb = build_setup_keyboard(all_chats, current_admin_id)
    kb.inline_keyboard.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="god_menu_main")])
    try: await callback.message.edit_reply_markup(reply_markup=kb)
    except: pass
    await callback.answer("Обновлено")

@router.callback_query(F.data.startswith("god_publish_chan_"))
async def cb_god_publish_chan(callback: types.CallbackQuery, session: AsyncSession):
    game_id = int(callback.data.split("_")[3])
    game = await session.get(Game, game_id)
    if not game:
        await callback.answer("Игра не найдена", show_alert=True)
        return
        
    if not game.channel_id:
        # Pопытаемся найти привязанный канал через Chat
        chat = await session.get(Chat, game.chat_id)
        if chat and chat.channel_id:
            game.channel_id = chat.channel_id
        else:
            await callback.answer("У этой игры или чата не настроен channel_id. Чтобы публиковать, нужно привязать канал.", show_alert=True)
            return

    from app.bot.utils import format_game_message
    from app.bot.keyboards import get_game_keyboard

    try:
        text = await format_game_message(game, session, is_short=False)
        msg = await callback.bot.send_message(
            chat_id=game.channel_id,
            text=text,
            reply_markup=get_game_keyboard(game.id),
            parse_mode="HTML"
        )
        game.channel_message_id = msg.message_id
        await session.commit()
        await callback.answer("✅ Анонс успешно отправлен в канал!")
    except Exception as e:
         import logging
         logging.error(f"Failed to publish to channel: {e}")
         await callback.answer(f"❌ Ошибка отправки: {e}", show_alert=True)
