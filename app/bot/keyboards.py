from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from app.db.models import Position

def get_position_keyboard() -> InlineKeyboardMarkup:
    # Deprecated, use get_primary_select_keyboard
    buttons = [
        [InlineKeyboardButton(text="🧤 Вратарь (GK)", callback_data=f"pos_{Position.GK.value}")],
        [InlineKeyboardButton(text="🛡 Защитник (DEF)", callback_data=f"pos_{Position.DEF.value}")],
        [InlineKeyboardButton(text="🏃 Полузащитник (MID)", callback_data=f"pos_{Position.MID.value}")],
        [InlineKeyboardButton(text="⚽ Нападающий (FWD)", callback_data=f"pos_{Position.FWD.value}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="delete_msg")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_multiselect_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    
    # Helper to create row
    def create_btn(pos_val):
        is_selected = pos_val in selected
        text = f"{'✅ ' if is_selected else ''}{pos_val}"
        return InlineKeyboardButton(text=text, callback_data=f"toggle_{pos_val}")

    # GK
    buttons.append([create_btn("GK")])
    
    # DEF
    buttons.append([create_btn("LB"), create_btn("CB"), create_btn("RB")])
    
    # MID
    buttons.append([create_btn("LM"), create_btn("RM")])
    buttons.append([create_btn("CM")])
    
    # FWD
    buttons.append([create_btn("LW"), create_btn("FWD"), create_btn("RW")])
    
    if selected:
        buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data="done_alt_pos")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_edit_menu")])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_primary_select_keyboard(available: list[str]) -> InlineKeyboardMarkup:
    # We want to show available positions, but also keep them organized if possible.
    # If 'available' is large (e.g. all positions), we group them.
    # If small (just selected alts), we list them.
    
    buttons = []
    
    # Check if we should use full layout or simple list
    use_layout = len(available) > 5
    
    if use_layout:
        # Define layout Structure provided available matches
        layout = [
            ["GK"],
            ["LB", "CB", "RB"],
            ["LM", "RM"],
            ["CM"],
            ["LW", "FWD", "RW"]
        ]
        for row in layout:
            btn_row = []
            for pos in row:
                if pos in available:
                    btn_row.append(InlineKeyboardButton(text=pos, callback_data=f"primary_{pos}"))
            if btn_row:
                buttons.append(btn_row)
    else:
        # Simple list wrapping
        row = []
        for pos in available:
            row.append(InlineKeyboardButton(text=pos, callback_data=f"primary_{pos}"))
            if len(row) >= 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
            
    # Add Back Button
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_edit_menu")])
            
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_game_keyboard(game_id: int) -> InlineKeyboardMarkup:
    # Use Deep Link to bypass "WebApp in Channel" restriction
    # User clicks -> Private Chat -> /start game_id -> We show WebApp button there
    bot_username = "fm_metabot" 
    deep_link = f"https://t.me/{bot_username}?start=game_{game_id}"
    
    from app.config import settings
    vote_url = f"{settings.webapp_url}/web/vote.html?game_id={game_id}"

    buttons = [
        [
            InlineKeyboardButton(text="➕ Я в деле", callback_data=f"join_{game_id}"),
            InlineKeyboardButton(text="➖ Сливаюсь", callback_data=f"leave_{game_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_channel_game_keyboard(game_id: int) -> InlineKeyboardMarkup:
    from app.config import settings
    # Deep link to bot with start param
    bot_username = settings.bot_token.split(":")[0] # Hacky if username not in config, but we used hardcoded before.
    # Better use the string we had
    bot_username = "fm_metabot"
    deep_link = f"https://t.me/{bot_username}?start=game_{game_id}"
    
    buttons = [
        [InlineKeyboardButton(text="⚽ Перейти к записи", url=deep_link)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_main_menu_keyboard(is_admin: bool = False):
    if not is_admin:
        return types.ReplyKeyboardRemove()

    from app.config import settings
    web_app_url = f"{settings.webapp_url}/web/index.html?v=3"
    
    # Admin Panel Only
    buttons = [
        [KeyboardButton(text="➕ Создать игру", web_app=types.WebAppInfo(url=web_app_url))],
        [KeyboardButton(text="🔀 Шаффл")]
    ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

def get_main_menu_inline_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    if not is_admin:
        return None

    from app.config import settings
    # Ensure ?v=3 is present to break cache
    web_app_url = f"{settings.webapp_url}/web/index.html?v=3"
    
    buttons = [
        [InlineKeyboardButton(text="➕ Создать игру", web_app=types.WebAppInfo(url=web_app_url))],
        [InlineKeyboardButton(text="🔀 Шаффл", callback_data="shuffle_teams")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_profile_edit_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✏️ Изменить профиль", callback_data="edit_profile")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)



def get_edit_choice_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📝 Изменить имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="🏃 Изменить позицию", callback_data="edit_position")],
        [InlineKeyboardButton(text="🔄 Изменить доп. позиции", callback_data="edit_alt_positions")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="edit_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="edit_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_voting_keyboard(game_id: int, team_a: list, team_b: list) -> InlineKeyboardMarkup:
    buttons = []
    
    # Team A Header
    buttons.append([InlineKeyboardButton(text="🟠 --- КОМАНДА А --- 🟠", callback_data="noop")])
    
    # Team A Players (2 per row)
    row = []
    for user in team_a:
        # User object or Signup object with user relation
        name = user.full_name
        uid = user.user_id
        row.append(InlineKeyboardButton(text=name, callback_data=f"vote_{game_id}_{uid}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    # Team B Header
    buttons.append([InlineKeyboardButton(text="🟢 --- КОМАНДА Б --- 🟢", callback_data="noop")])
    
    # Team B Players (2 per row)
    row = []
    for user in team_b:
        name = user.full_name
        uid = user.user_id
        row.append(InlineKeyboardButton(text=name, callback_data=f"vote_{game_id}_{uid}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)
