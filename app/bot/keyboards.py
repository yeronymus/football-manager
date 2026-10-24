from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


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
        buttons.append([InlineKeyboardButton(text="✅ Готово / Done", callback_data="done_alt_pos")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад / Back", callback_data="back_to_edit_menu")])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_primary_select_keyboard(available: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    use_layout = len(available) > 5
    
    if use_layout:
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
        row = []
        for pos in available:
            row.append(InlineKeyboardButton(text=pos, callback_data=f"primary_{pos}"))
            if len(row) >= 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
            
    buttons.append([InlineKeyboardButton(text="🔙 Назад / Back", callback_data="back_to_edit_menu")])
            
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_game_keyboard(game_id: int, is_admin: bool = False, webapp_url: str = "", lang: str = "en") -> InlineKeyboardMarkup:
    from app.config import settings
    import time
    
    timestamp = int(time.time())
    base_url = webapp_url if webapp_url else settings.webapp_url
    lang_param = f"&lang={lang}" if lang else ""
    game_url = f"{base_url.rstrip('/')}/web/game.html?game_id={game_id}&v={timestamp}{lang_param}"
    
    is_en = (lang or "en").lower() == "en"
    join_btn_text = "⚽ Sign Up for Game" if is_en else "⚽ Записаться на игру"
    
    buttons = [
        [
            InlineKeyboardButton(text=join_btn_text, web_app=types.WebAppInfo(url=game_url))
        ]
    ]
    
    if is_admin:
        draft_url = f"{base_url.rstrip('/')}/web/draft.html?game_id={game_id}&v={timestamp}{lang_param}"
        draft_btn_text = "🛠 Teams (Draft)" if is_en else "🛠 Составы (Draft)"
        buttons.append([
            InlineKeyboardButton(text=draft_btn_text, web_app=types.WebAppInfo(url=draft_url))
        ])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_channel_game_keyboard(game_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    from app.config import settings
    bot_username = settings.bot_username
    deep_link = f"https://t.me/{bot_username}?start=game_{game_id}"
    
    is_en = (lang or "en").lower() == "en"
    btn_text = "⚽ Join Game" if is_en else "⚽ Перейти к записи"
    
    buttons = [
        [InlineKeyboardButton(text=btn_text, url=deep_link)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_main_menu_keyboard(is_admin: bool = False, lang: str = "en"):
    if not is_admin:
        return types.ReplyKeyboardRemove()

    from app.config import settings
    web_app_url = f"{settings.webapp_url.rstrip('/')}/web/index.html?v=7"
    
    is_en = (lang or "en").lower() == "en"
    create_text = "➕ Create Game" if is_en else "➕ Создать игру"
    shuffle_text = "🔀 Shuffle" if is_en else "🔀 Шаффл"
    
    buttons = [
        [KeyboardButton(text=create_text, web_app=types.WebAppInfo(url=web_app_url))],
        [KeyboardButton(text=shuffle_text)]
    ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

def get_main_menu_inline_keyboard(is_admin: bool = False, lang: str = "en") -> InlineKeyboardMarkup:
    if not is_admin:
        return None

    from app.config import settings
    web_app_url = f"{settings.webapp_url.rstrip('/')}/web/index.html?v=7"
    is_en = (lang or "en").lower() == "en"
    create_text = "➕ Create Game" if is_en else "➕ Создать игру"
    shuffle_text = "🔀 Shuffle" if is_en else "🔀 Шаффл"
    
    buttons = [
        [InlineKeyboardButton(text=create_text, web_app=types.WebAppInfo(url=web_app_url))],
        [InlineKeyboardButton(text=shuffle_text, callback_data="shuffle_teams")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_profile_edit_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    is_en = (lang or "en").lower() == "en"
    btn_edit = "✏️ Edit Profile" if is_en else "✏️ Изменить профиль"
    buttons = [
        [
            InlineKeyboardButton(text=btn_edit, callback_data="edit_profile"),
            InlineKeyboardButton(text="🌐 Language", callback_data="change_user_lang")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_edit_choice_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    is_en = (lang or "en").lower() == "en"
    buttons = [
        [InlineKeyboardButton(text="📝 Change Name" if is_en else "📝 Изменить имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="🏃 Change Position" if is_en else "🏃 Изменить позицию", callback_data="edit_position")],
        [InlineKeyboardButton(text="🔄 Change Alt Positions" if is_en else "🔄 Изменить доп. позиции", callback_data="edit_alt_positions")],
        [InlineKeyboardButton(text="🌐 Change Language / Сменить язык", callback_data="change_user_lang")],
        [InlineKeyboardButton(text="🔙 Back" if is_en else "🔙 Отмена", callback_data="edit_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    is_en = (lang or "en").lower() == "en"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back" if is_en else "🔙 Отмена", callback_data="edit_cancel")]
    ])

def get_channel_voting_keyboard(game_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    """Returns a channel-safe keyboard with deep-link URL button for voting."""
    from app.config import settings
    bot_username = settings.bot_username.lstrip("@")
    deep_link = f"https://t.me/{bot_username}?start=vote_{game_id}"
    is_en = (lang or "en").lower() == "en"
    btn_text = "🏆 Vote for MVP" if is_en else "🏆 Проголосовать за MVP"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_text, url=deep_link)]
    ])

def get_voting_keyboard(game_id: int, team_a: list, team_b: list, team_c: list = None, unassigned: list = None, lang: str = "en") -> InlineKeyboardMarkup:
    buttons = []
    is_en = (lang or "en").lower() == "en"
    
    def _add_team_section(title: str, players: list):
        if not players:
            return
        buttons.append([InlineKeyboardButton(text=title, callback_data="noop")])
        row = []
        for user in players:
            name = getattr(user, 'full_name', str(user))
            uid = getattr(user, 'user_id', user)
            row.append(InlineKeyboardButton(text=name, callback_data=f"vote_{game_id}_{uid}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

    if team_a:
        title_a = "🟠 --- TEAM A --- 🟠" if is_en else "🟠 --- КОМАНДА А --- 🟠"
        _add_team_section(title_a, team_a)
    if team_b:
        title_b = "🟢 --- TEAM B --- 🟢" if is_en else "🟢 --- КОМАНДА Б --- 🟢"
        _add_team_section(title_b, team_b)
    if team_c:
        title_c = "🔵 --- TEAM C --- 🔵" if is_en else "🔵 --- КОМАНДА С --- 🔵"
        _add_team_section(title_c, team_c)
    if not team_a and not team_b and not team_c and unassigned:
        title_p = "⚽ --- PLAYERS --- ⚽" if is_en else "⚽ --- ИГРОКИ --- ⚽"
        _add_team_section(title_p, unassigned)
        


    return InlineKeyboardMarkup(inline_keyboard=buttons)
