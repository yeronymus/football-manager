from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from app.db.models import Position

def get_position_keyboard() -> InlineKeyboardMarkup:
    # Deprecated, use get_primary_select_keyboard
    buttons = [
        [InlineKeyboardButton(text="🧤 Вратарь (GK)", callback_data=f"pos_{Position.GK.value}")],
        [InlineKeyboardButton(text="🛡 Защитник (DEF)", callback_data=f"pos_{Position.DEF.value}")],
        [InlineKeyboardButton(text="🏃 Полузащитник (MID)", callback_data=f"pos_{Position.MID.value}")],
        [InlineKeyboardButton(text="⚽ Нападающий (FWD)", callback_data=f"pos_{Position.FWD.value}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_multiselect_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for pos in Position:
        is_selected = pos.value in selected
        text = f"{'✅ ' if is_selected else ''}{pos.value}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"toggle_{pos.value}")])
    
    if selected:
        buttons.append([InlineKeyboardButton(text="Готово", callback_data="done_alt_pos")])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_primary_select_keyboard(available: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for pos_val in available:
        buttons.append([InlineKeyboardButton(text=pos_val, callback_data=f"primary_{pos_val}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_game_keyboard(game_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="➕ Я в деле", callback_data=f"join_{game_id}"),
            InlineKeyboardButton(text="➖ Сливаюсь", callback_data=f"leave_{game_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📜 Мои матчи"), KeyboardButton(text="👤 Мой профиль")]
        ],
        resize_keyboard=True
    )
