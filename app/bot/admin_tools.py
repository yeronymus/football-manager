
from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Chat
from app.config import settings

router = Router()

@router.message(Command("get_id"))
async def cmd_get_id(message: types.Message):
    """
    Returns the current chat ID.
    Useful for admins to know the ID of the Admin Channel.
    """
    await message.answer(f"🆔 ID этого чата: <code>{message.chat.id}</code>")

@router.message(Command("link"))
async def cmd_link_chat(message: types.Message, command: CommandObject, session: AsyncSession):
    """
    Usage: /link <football_chat_id>
    Links the Football Chat (by ID) to the CURRENT Admin Chat.
    """
    # 1. Security Check: Are we in an Admin Chat?
    # Ideally, only admins can run this.
    # We can check if sender is in ADMIN_IDS
    if message.from_user.id not in settings.ADMIN_IDS:
        return

    football_chat_id_str = command.args
    if not football_chat_id_str:
        await message.answer("⚠️ Используйте: `/link <football_chat_id>`\nНапример: `/link -1001234567890`")
        return

    try:
        football_chat_id = int(football_chat_id_str)
    except ValueError:
        await message.answer("❌ Некорректный ID чата.")
        return

    # 2. Find the Football Chat
    # Note: We query by chat_id, which is BigInteger
    chat = await session.get(Chat, football_chat_id)
    
    if not chat:
        await message.answer(f"❌ Чат с ID <code>{football_chat_id}</code> не найден в базе.\nСначала выполните `/register_chat` в самом футбольном чате.")
        return

    # 3. Update Link
    current_admin_chat_id = message.chat.id
    chat.admin_chat_id = current_admin_chat_id
    await session.commit()

    await message.answer(
        f"✅ <b>Связь установлена!</b>\n\n"
        f"⚽ Футбольный чат: {chat.title}\n"
        f"📢 Админский чат: {message.chat.title} (ID: {current_admin_chat_id})\n\n"
        f"Теперь панель управления из {chat.title} будет приходить сюда."
    )

from aiogram import F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(Command("setup"))
async def cmd_setup_admin(message: types.Message, session: AsyncSession):
    """
    Interactive setup for Admin Chat.
    Lists all known chats and allows toggling their link to THIS chat.
    """
    # 1. Fetch available chats (exclude current)
    result = await session.execute(select(Chat).where(Chat.chat_id != message.chat.id))
    all_chats = result.scalars().all()
    
    if not all_chats:
         await message.answer("Бот не добавлен ни в одну группу.")
         return

    # 2. Filter: Show only chats where THIS user is an admin
    user_id = message.from_user.id
    admin_chats = []
    
    # Check current user global admin status (bypass)
    is_global_admin = user_id in settings.ADMIN_IDS
    
    msg_wait = await message.answer("🔍 Проверяю ваши права в группах...")
    
    from app.bot.main import bot
    
    for chat in all_chats:
        try:
            if is_global_admin:
                admin_chats.append(chat)
                continue
                
            member = await bot.get_chat_member(chat.chat_id, user_id)
            if member.status in ['administrator', 'creator']:
                admin_chats.append(chat)
        except Exception as e:
            # Bot might be kicked or logic fail
            continue
    
    await msg_wait.delete()

    if not admin_chats:
        await message.answer("⚠️ Вы не являетесь администратором ни в одной подключенной группе.")
        return

    text = f"⚙️ <b>Панель управления связями</b>\n\n" \
           f"Вы находитесь в <b>Админском чате</b> (ID: <code>{message.chat.id}</code>).\n" \
           f"Отметьте галочками ✅ те футбольные группы, которыми вы хотите управлять <b>ОТСЮДА</b>.\n\n" \
           f"<i>Когда в отмеченной группе создастся игра, отчет о ней (оплата, составы) придет прямо сюда.</i>"

    kb = build_setup_keyboard(admin_chats, message.chat.id)
    await message.answer(text, reply_markup=kb)

def build_setup_keyboard(chats, current_admin_id):
    buttons = []
    for chat in chats:
        is_linked = chat.admin_chat_id == current_admin_id
        status_icon = "✅" if is_linked else "⬜"
        # Truncate title
        title = chat.title[:20] + ".." if len(chat.title) > 20 else chat.title
        btn_text = f"{status_icon} {title}"
        cb_data = f"setup_toggle_{chat.chat_id}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=cb_data)])
    
    buttons.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="setup_refresh")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data.startswith("setup_toggle_"))
async def cb_setup_toggle(callback: types.CallbackQuery, session: AsyncSession):
    target_chat_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    # 1. Verify user has rights to this specific chat
    from app.bot.main import bot
    chat = await session.get(Chat, target_chat_id)
    if not chat:
        await callback.answer("Чат не найден", show_alert=True)
        return

    is_global = user_id in settings.ADMIN_IDS
    has_rights = is_global
    if not is_global:
        try:
            m = await bot.get_chat_member(target_chat_id, user_id)
            if m.status in ['administrator', 'creator']:
                has_rights = True
        except:
            pass
            
    if not has_rights:
        await callback.answer("У вас нет прав администратора в этой группе", show_alert=True)
        return

    current_admin_id = callback.message.chat.id
    
    # Toggle logic
    if chat.admin_chat_id == current_admin_id:
        chat.admin_chat_id = None # Unlink
        action = "Отвязано"
    else:
        chat.admin_chat_id = current_admin_id # Link
        action = "Привязано"
        
    await session.commit()
    
    # Refresh Keyboard (Filtered)
    # Re-use logic to fetch allowed chats
    # Ideally refactor to helper function `get_allowed_chats(session, user_id, current_chat_id)`
    # But for now, inline for speed.
    res_all = await session.execute(select(Chat).where(Chat.chat_id != current_admin_id))
    all_c = res_all.scalars().all()
    allowed = []
    for c in all_c:
        if is_global:
            allowed.append(c)
            continue
        try:
            mem = await bot.get_chat_member(c.chat_id, user_id)
            if mem.status in ['administrator', 'creator']:
                allowed.append(c)
        except: pass
    
    try:
        await callback.message.edit_reply_markup(reply_markup=build_setup_keyboard(allowed, current_admin_id))
    except:
        pass 
        
    await callback.answer(action)

@router.callback_query(F.data == "setup_refresh")
async def cb_setup_refresh(callback: types.CallbackQuery, session: AsyncSession):
    current_admin_id = callback.message.chat.id
    user_id = callback.from_user.id
    is_global = user_id in settings.ADMIN_IDS
    
    from app.bot.main import bot
    
    res_all = await session.execute(select(Chat).where(Chat.chat_id != current_admin_id))
    all_c = res_all.scalars().all()
    allowed = []
    
    for c in all_c:
        if is_global:
            allowed.append(c)
            continue
        try:
            mem = await bot.get_chat_member(c.chat_id, user_id)
            if mem.status in ['administrator', 'creator']:
                allowed.append(c)
        except: pass

    try:
        await callback.message.edit_reply_markup(reply_markup=build_setup_keyboard(allowed, current_admin_id))
    except:
        pass
    await callback.answer("Обновлено")
