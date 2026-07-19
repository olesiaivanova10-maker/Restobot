from aiogram.fsm.state import StatesGroup, State

class ReportSteps(StatesGroup):
    waiting_for_combined_report = State()
    waiting_for_missing_item = State()
    waiting_for_confirmation = State()
    waiting_for_edit_value = State()
