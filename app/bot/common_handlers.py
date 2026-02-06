from aiogram import Router, F, types
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user_service import UserService
from app.bot.fsm import Registration
from app.bot.keyboards import get_cancel_keyboard
from app.config import settings

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject, state: FSMContext, session: AsyncSession):
    # Only private chats
    if message.chat.type != "private":
        return

    # DEEP LINK HANDLING
    args = command.args
    if args:
        # Handle "finish_{game_id}"
        if args.startswith("finish_") or args.startswith("edit_"):
            try:
                game_id = args.split("_")[1]
                # Construct WebApp URL
                # Ensure webapp_url has no trailing slash if we add one, or handle cleaner
                base = settings.webapp_url.rstrip("/")
                # Determined correct path from keyboards.py usage (requires /web prefix)
                # Adjusted parameter 'game_id' -> 'id' to match finish.html expectation
                web_url = f"{base}/web/finish.html?id={game_id}&mode=edit"
                
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(
                        text="🏁 Заполнить результаты",
                        web_app=types.WebAppInfo(url=web_url)
                    )]
                ])
                
                await message.answer(
                    f"Нажмите кнопку ниже, чтобы управлять результатами игры #{game_id}:",
                    reply_markup=kb
                )
                return # Stop here, don't show welcome message
            except IndexError:
                pass
        
        # Handle "game_{game_id}" (Drafts)
        if args.startswith("game_"):
            try:
                game_id = args.split("_")[1]
                
                # Check if admin (Draft is admin only tool usually, matches handlers/common.py logic)
                is_admin = message.from_user.id in settings.admin_ids or message.from_user.id == settings.system_owner_id
                
                if is_admin:
                    # Construct WebApp URL
                    base = settings.webapp_url.rstrip("/")
                    web_url = f"{base}/web/draft.html?game_id={game_id}&v=1.8"
                    
                    kb = types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(
                            text="🛠 Составы (Draft) [WebApp]",
                            web_app=types.WebAppInfo(url=web_url)
                        )]
                    ])
                    
                    await message.answer(
                        f"🛠 <b>Управление составами игры #{game_id}</b>",
                        reply_markup=kb
                    )
                    return
                else:
                    await message.answer("⛔ Только для админов.")
                    return

            except IndexError:
                pass

    # Check if user exists
    user_service = UserService(session)
    user = await user_service.get_user(message.from_user.id)
    
    if user:
        await message.answer(f"С возвращением, {user.full_name}! ⚽\nИспользуйте меню для управления.", reply_markup=types.ReplyKeyboardRemove())
    else:
        await message.answer("Добро пожаловать в Football Manager! ⚽\nДавайте создадим ваш профиль.\n\nКак вас зовут (Имя Фамилия)?", reply_markup=get_cancel_keyboard())
        await state.set_state(Registration.waiting_for_name)

@router.callback_query(F.data == "delete_msg")
async def cb_delete_msg(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        await callback.answer("Не удалось скрыть")
