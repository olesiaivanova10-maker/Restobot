import traceback
import html
from aiogram import Router, Bot
from aiogram.types import ErrorEvent
from aiogram.exceptions import TelegramBadRequest

from core.logger import logger
from core.config import ADMIN_ID

errors_router = Router()

@errors_router.errors()
async def global_error_handler(event: ErrorEvent, bot: Bot):
    """Глобальный ловец ошибок. Отправляет traceback админу."""
    
    # --- ИГНОРИРУЕМ ОШИБКУ ДВОЙНОГО КЛИКА ---
    if isinstance(event.exception, TelegramBadRequest) and "message is not modified" in str(event.exception):
        return
    # ----------------------------------------

    logger.error(f"Произошла ошибка: {event.exception}\n{traceback.format_exc()}")
    
    if not ADMIN_ID:
        return
        
    # Достаем стек вызовов, чтобы понять, на какой строке упал код
    tb_list = traceback.format_exception(type(event.exception), event.exception, event.exception.__traceback__)
    tb_string = "".join(tb_list)
    
    # Telegram разрешает до 4096 символов, поэтому берем только конец ошибки, если она огромная
    tb_string = tb_string[-3500:]
    
    error_msg = (
        f"🚨 <b>КРИТИЧЕСКАЯ ОШИБКА В БОТЕ</b>\n\n"
        f"<b>Тип:</b> <code>{html.escape(str(type(event.exception).__name__))}</code>\n"
        f"<b>Сообщение:</b> {html.escape(str(event.exception))}\n\n"
        f"<b>Traceback:</b>\n<pre language='python'>{html.escape(tb_string)}</pre>"
    )
    
    try:
        for admin in ADMIN_ID:
            try:
                await bot.send_message(chat_id=admin, text=error_msg, parse_mode="HTML")
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Не удалось отправить алерт админу: {e}")
