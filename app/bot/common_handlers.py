from aiogram import Router, F, types

router = Router()

@router.callback_query(F.data == "delete_msg")
async def cb_delete_msg(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        await callback.answer("Не удалось скрыть")
