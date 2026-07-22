from aiogram import Router, Bot
from aiogram.types import ErrorEvent
from aiogram.exceptions import TelegramBadRequest

from core.logger import logger
from services.error_reporting import notify_admins_about_error, show_generic_report_error

errors_router = Router()

@errors_router.errors()
async def global_error_handler(event: ErrorEvent, bot: Bot):
    """Глобальный ловец ошибок. Отправляет traceback админу."""
    
    # --- ИГНОРИРУЕМ ОШИБКУ ДВОЙНОГО КЛИКА ---
    if isinstance(event.exception, TelegramBadRequest) and "message is not modified" in str(event.exception):
        return
    # ----------------------------------------

    logger.exception(f"Произошла ошибка: {event.exception}")

    update = event.update
    source_message = getattr(update, "message", None)
    if not source_message:
        callback_query = getattr(update, "callback_query", None)
        source_message = getattr(callback_query, "message", None) if callback_query else None

    await notify_admins_about_error(
        bot,
        event.exception,
        source_message,
        context="Необработанная ошибка Telegram-события",
    )
    if source_message:
        await show_generic_report_error(source_message)
