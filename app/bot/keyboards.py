from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.db.models import Position

def get_position_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🧤 Вратарь (GK)", callback_data=f"pos_{Position.GK.value}")],
        [InlineKeyboardButton(text="🛡 Защитник (DEF)", callback_data=f"pos_{Position.DEF.value}")],
        [InlineKeyboardButton(text="🏃 Полузащитник (MID)", callback_data=f"pos_{Position.MID.value}")],
        [InlineKeyboardButton(text="⚽ Нападающий (FWD)", callback_data=f"pos_{Position.FWD.value}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_game_keyboard(game_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="➕ Я в деле", callback_data=f"join_{game_id}"),
            InlineKeyboardButton(text="➖ Сливаюсь", callback_data=f"leave_{game_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
