from aiogram import Router, F, types
from app.config import settings
from app.core.uow import UnitOfWork
from app.core.services.roster import RosterService, PlayerJoinedEvent, PlayerLeftEvent
from app.core.events import EventBus
from app.db.models import Game
import logging

router = Router()

@router.callback_query(F.data.startswith("join_"))
async def process_join(callback: types.CallbackQuery):
    game_id = int(callback.data.split("_")[1])
    telegram_user_id = callback.from_user.id
    
    # Feature Flag для Strangler Fig Pattern
    use_new_logic = settings.use_new_roster_logic or (telegram_user_id in settings.debug_new_logic_user_ids)

    if not use_new_logic:
        await callback.answer("Легаси режим отключен. Используйте новую логику.", show_alert=True)
        return

    alert_msg = None
    event_payload = None

    try:
        # Вся работа с БД строго внутри контекста UoW
        async with UnitOfWork() as uow:
            # 1. Проверка регистрации (через репозиторий, а не SQL!)
            user = await uow.user_repo.get_by_id(telegram_user_id)
            
            if not user:
                me = await callback.bot.get_me()
                await callback.answer("Переходим к регистрации...", url=f"https://t.me/{me.username}?start=reg")
                return

            # 2. Работа сервиса
            service = RosterService(uow.game_repo)
            result = await service.join_player(game_id, user)
            
            if not result.success:
                await callback.answer(result.message, show_alert=True)
                # Нет commit(), транзакция откатится автоматически при выходе
                return

            # 3. Подготовка данных для события (до коммита)
            alert_msg = result.message
            if result.signup:
                event_payload = PlayerJoinedEvent(
                    game_id=game_id, 
                    user_id=telegram_user_id, 
                    signup=result.signup, 
                    is_reserve=result.is_reserve, 
                    message=alert_msg
                )

            # 4. Фиксация транзакции
            await uow.commit()

        # --- Side Effects (События отправляем ПОСЛЕ успешного коммита) ---
        if event_payload:
            await EventBus.publish(event_payload)

        # Обновление UI (убрана логика dashboard отсюда, она должна быть в listener)
        await callback.answer(alert_msg)

    except Exception as e:
        logging.error(f"New Roster Logic Failed: {e}", exc_info=True)
        await callback.answer("Произошла системная ошибка", show_alert=True)


@router.callback_query(F.data.startswith("leave_"))
async def process_leave(callback: types.CallbackQuery):
    game_id = int(callback.data.split("_")[1])
    telegram_user_id = callback.from_user.id
    is_admin = telegram_user_id in settings.admin_ids or telegram_user_id == settings.system_owner_id
    
    try:
        async with UnitOfWork() as uow:
            service = RosterService(uow.game_repo)
            
            success, msg, promoted_user = await service.leave_player(
                game_id, telegram_user_id, is_admin=is_admin
            )
            
            if not success:
                await callback.answer(msg, show_alert=True)
                return

            await uow.commit()
            
        # --- Side Effects ---
        if promoted_user:
            try:
                await callback.bot.send_message(
                    promoted_user.user_id,
                    "🎉 <b>Вас перевели в основной состав!</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        await EventBus.publish(PlayerLeftEvent(
            game_id=game_id, 
            user_id=telegram_user_id, 
            message=msg, 
            promoted_user=promoted_user
        ))

        await callback.answer(msg)

    except Exception as e:
        logging.error(f"Leave Error: {e}", exc_info=True)
        await callback.answer("Ошибка при выходе.", show_alert=True)
