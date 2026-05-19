from aiogram.fsm.state import State, StatesGroup

class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_alt_positions = State()
    waiting_for_position = State()

class EditingProfile(StatesGroup):
    waiting_for_choice = State()
    waiting_for_name = State()
    waiting_for_position = State()
    waiting_for_alt_positions = State()
class GuestAddition(StatesGroup):
    waiting_for_name = State()
    waiting_for_position = State()
