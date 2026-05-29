import pytest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from app.bot.handlers.setup_handlers import get_setup_keyboard
from app.bot.keyboards import get_game_keyboard, get_multiselect_keyboard

def test_get_setup_keyboard():
    kb = get_setup_keyboard()
    assert isinstance(kb, InlineKeyboardMarkup)
    
    # Check buttons
    buttons = kb.inline_keyboard
    assert len(buttons) == 3
    
    # Row 1: Languages
    assert buttons[0][0].text == "🇷🇺 RU"
    assert buttons[0][0].callback_data == "setlang_ru"
    assert buttons[0][1].text == "🇬🇧 EN"
    assert buttons[0][1].callback_data == "setlang_en"
    
    # Row 2: Payment
    assert buttons[1][0].text == "💳 Изменить реквизиты"
    assert buttons[1][0].callback_data == "setup_payment"
    
    # Row 3: Close
    assert buttons[2][0].text == "❌ Закрыть"
    assert buttons[2][0].callback_data == "setup_close"

def test_get_game_keyboard_regular():
    game_id = 123
    kb = get_game_keyboard(game_id, is_admin=False, webapp_url="https://test.com")
    assert isinstance(kb, InlineKeyboardMarkup)
    
    buttons = kb.inline_keyboard
    assert len(buttons) == 1
    assert buttons[0][0].text == "⚽ Записаться на игру"
    assert isinstance(buttons[0][0].web_app, WebAppInfo)
    assert "game_id=123" in buttons[0][0].web_app.url
    assert "https://test.com" in buttons[0][0].web_app.url

def test_get_game_keyboard_admin():
    game_id = 123
    kb = get_game_keyboard(game_id, is_admin=True, webapp_url="https://test.com")
    assert len(kb.inline_keyboard) == 2
    
    # Second button should be draft
    admin_btn = kb.inline_keyboard[1][0]
    assert admin_btn.text == "🛠 Составы (Draft)"
    assert "draft.html" in admin_btn.web_app.url
    assert "game_id=123" in admin_btn.web_app.url

def test_get_multiselect_keyboard_none_selected():
    kb = get_multiselect_keyboard([])
    # Expected rows: GK, DEF(3), MID(2), MID(1), FWD(3), Back = 6 rows
    assert len(kb.inline_keyboard) == 6
    
    # Verify no checkmarks
    for row in kb.inline_keyboard:
        for btn in row:
            if "🔙" not in btn.text:
                assert "✅" not in btn.text

def test_get_multiselect_keyboard_with_selections():
    kb = get_multiselect_keyboard(["GK", "CB", "FWD"])
    # 5 rows + "Done" button row + "Back" button row = 7 rows
    assert len(kb.inline_keyboard) == 7
    
    # Check if correct buttons have checkmarks
    assert "✅ GK" in kb.inline_keyboard[0][0].text
    assert "✅ CB" in kb.inline_keyboard[1][1].text
    assert "✅ FWD" in kb.inline_keyboard[4][1].text
    
    # Done button (appended before Back)
    assert kb.inline_keyboard[5][0].text == "✅ Готово"
    assert kb.inline_keyboard[5][0].callback_data == "done_alt_pos"
    
    # Back button
    assert kb.inline_keyboard[6][0].text == "🔙 Назад"
    assert kb.inline_keyboard[6][0].callback_data == "back_to_edit_menu"
