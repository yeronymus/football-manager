from app.bot.i18n import t
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
    
    join_btn_text = t("btn_join_game", locale=lang)
    
    buttons = [
        [
            InlineKeyboardButton(text=join_btn_text, web_app=types.WebAppInfo(url=game_url))
        ]
    ]
    
    if is_admin:
        draft_url = f"{base_url.rstrip('/')}/web/draft.html?game_id={game_id}&v={timestamp}{lang_param}"
        draft_btn_text = t("btn_draft_teams", locale=lang)
        buttons.append([
            InlineKeyboardButton(text=draft_btn_text, web_app=types.WebAppInfo(url=draft_url))
        ])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_channel_game_keyboard(game_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    from app.config import settings
    bot_username = settings.bot_username
    deep_link = f"https://t.me/{bot_username}?start=game_{game_id}"
    
    btn_text = t("btn_channel_join", locale=lang)
    
    buttons = [
        [InlineKeyboardButton(text=btn_text, url=deep_link)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_main_menu_keyboard(is_admin: bool = False, lang: str = "en"):
    if not is_admin:
        return types.ReplyKeyboardRemove()

    from app.config import settings
    web_app_url = f"{settings.webapp_url.rstrip('/')}/web/index.html?v=7"
    
    create_text = t("btn_create_game", locale=lang)
    shuffle_text = t("btn_shuffle_teams", locale=lang)
    
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
    create_text = t("btn_create_game", locale=lang)
    shuffle_text = t("btn_shuffle_teams", locale=lang)
    
    buttons = [
        [InlineKeyboardButton(text=create_text, web_app=types.WebAppInfo(url=web_app_url))],
        [InlineKeyboardButton(text=shuffle_text, callback_data="shuffle_teams")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_profile_edit_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    btn_edit = t("btn_edit_profile", locale=lang)
    buttons = [
        [
            InlineKeyboardButton(text=btn_edit, callback_data="edit_profile"),
            InlineKeyboardButton(text="🌐 Language", callback_data="change_user_lang")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_edit_choice_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=t("btn_change_name", locale=lang), callback_data="edit_name")],
        [InlineKeyboardButton(text=t("btn_change_position", locale=lang), callback_data="edit_position")],
        [InlineKeyboardButton(text=t("btn_change_alt_positions", locale=lang), callback_data="edit_alt_positions")],
        [InlineKeyboardButton(text="🌐 Change Language / Сменить язык", callback_data="change_user_lang")],
        [InlineKeyboardButton(text=t("btn_cancel", locale=lang), callback_data="edit_cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_cancel", locale=lang), callback_data="edit_cancel")]
    ])

def get_channel_voting_keyboard(game_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    """Returns a channel-safe keyboard with deep-link URL button for voting."""
    from app.config import settings
    bot_username = settings.bot_username.lstrip("@")
    deep_link = f"https://t.me/{bot_username}?start=vote_{game_id}"
    btn_text = t("btn_vote_mvp", locale=lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_text, url=deep_link)]
    ])

def get_voting_keyboard(game_id: int, team_a: list, team_b: list, team_c: list = None, unassigned: list = None, lang: str = "en") -> InlineKeyboardMarkup:
    buttons = []
    
    
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
        title_a = t("team_a_header", locale=lang)
        _add_team_section(title_a, team_a)
    if team_b:
        title_b = t("team_b_header", locale=lang)
        _add_team_section(title_b, team_b)
    if team_c:
        title_c = t("team_c_header", locale=lang)
        _add_team_section(title_c, team_c)
    if not team_a and not team_b and not team_c and unassigned:
        title_p = t("players_voting_header", locale=lang)
        _add_team_section(title_p, unassigned)
        


    return InlineKeyboardMarkup(inline_keyboard=buttons)
