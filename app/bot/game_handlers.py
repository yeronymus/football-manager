from aiogram import Router, F, types
from app.config import settings
from app.core.uow import UnitOfWork
from app.core.services.roster import RosterService, PlayerJoinedEvent, PlayerLeftEvent
from app.core.events import event_bus
import logging

router = Router()

@router.callback_query(F.data.startswith("join_"))
async def process_join(callback: types.CallbackQuery):
    game_id = int(callback.data.split("_")[1])
    tg_id = callback.from_user.id
    
    # --- STRANGLER ROUTER ---
    # Legacy Games (ID <= 5) use the old logic
    if game_id <= settings.last_legacy_game_id:
        from app.bot.legacy_handlers import process_join as legacy_join
        await legacy_join(callback)
        return

    # --- NEW ARCHITECTURE ---
    alert_msg = None
    event_payload = None

    try:
        # ЗАПУСК ТРАНЗАКЦИИ
        async with UnitOfWork() as uow:
            # 1. Получаем пользователя (БЕЗ сырого SQL, через репозиторий)
            user = await uow.user_repo.get_by_id(tg_id)
            
            if not user:
                bot_user = await callback.bot.get_me()
                await callback.answer("Нужна регистрация!", url=f"https://t.me/{bot_user.username}?start=reg")
                return

            # 2. Вызываем сервис
            service = RosterService(uow)
            result = await service.join_player(game_id, user)
            
            if not result.success:
                await callback.answer(result.message, show_alert=True)
                return # Выход без commit (авто-rollback)

            # 3. Подготовка события (side-effect)
            alert_msg = result.message
            if result.signup:
                event_payload = PlayerJoinedEvent(
                    game_id=game_id,
                    user_id=tg_id,
                    signup=result.signup,
                    is_reserve=result.is_reserve,
                    message=alert_msg
                )

            # 4. ФИКСАЦИЯ ИЗМЕНЕНИЙ
            await uow.commit()

        # --- ЗА ПРЕДЕЛАМИ ТРАНЗАКЦИИ ---
        # Отправляем события только если commit прошел успешно
        if event_payload:
            await event_bus.publish(event_payload)

        await callback.answer(alert_msg)

    except Exception as e:
        logging.error(f"Critical Join Error: {e}", exc_info=True)
        await callback.answer("Ошибка системы. Мы уже чиним.", show_alert=True)

@router.callback_query(F.data.startswith("leave_"))
async def process_leave(callback: types.CallbackQuery):
    game_id = int(callback.data.split("_")[1])
    tg_id = callback.from_user.id
    is_admin = tg_id in settings.admin_ids or tg_id == settings.system_owner_id
    
    # --- STRANGLER ROUTER ---
    if game_id <= settings.last_legacy_game_id:
        from app.bot.legacy_handlers import process_leave as legacy_leave
        await legacy_leave(callback)
        return

    # --- NEW ARCHITECTURE ---
    try:
        async with UnitOfWork() as uow:
            service = RosterService(uow)
            success, msg, promoted = await service.leave_player(game_id, tg_id, is_admin)
            
            if not success:
                await callback.answer(msg, show_alert=True)
                return

            await uow.commit()
            
        # Side Effects
        if promoted:
            try:
                await callback.bot.send_message(promoted.user_id, "🚀 Вы переведены в основной состав!")
            except: pass

        await event_bus.publish(PlayerLeftEvent(game_id, tg_id, msg, promoted))
        await callback.answer(msg)

    except Exception as e:
        logging.error(f"Critical Leave Error: {e}", exc_info=True)
        await callback.answer("Ошибка выхода.", show_alert=True)
