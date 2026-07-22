import html
import traceback

from aiogram import Bot, types

from core.config import ADMIN_ID
from core.logger import logger


def describe_message_source(message: types.Message | None) -> str:
    if not message:
        return "Источник Telegram не определён"

    chat = message.chat
    user = message.from_user
    chat_title = getattr(chat, "title", None) or getattr(chat, "full_name", None) or "Без названия"
    user_label = "Неизвестный пользователь"
    if user:
        username = f"@{user.username}" if user.username else "без username"
        user_label = f"{user.full_name} ({username}, ID: {user.id})"

    return (
        f"Чат: {chat_title} (ID: {chat.id}, тип: {chat.type})\n"
        f"Пользователь: {user_label}\n"
        f"Сообщение: {message.message_id}"
    )


async def notify_admins_about_error(
    bot: Bot,
    exception: Exception,
    message: types.Message | None = None,
    context: str = "",
) -> None:
    if not ADMIN_ID:
        return

    tb_string = "".join(
        traceback.format_exception(type(exception), exception, exception.__traceback__)
    )[-2800:]
    source = describe_message_source(message)
    error_msg = (
        "🚨 <b>ОШИБКА В БОТЕ</b>\n\n"
        f"<b>Контекст:</b> {html.escape(context or 'Не указан')}\n"
        f"<b>Источник:</b>\n<pre>{html.escape(source)}</pre>\n"
        f"<b>Тип:</b> <code>{html.escape(type(exception).__name__)}</code>\n"
        f"<b>Сообщение:</b> {html.escape(str(exception))}\n\n"
        f"<b>Traceback:</b>\n<pre>{html.escape(tb_string)}</pre>"
    )

    for admin_id in ADMIN_ID:
        try:
            await bot.send_message(chat_id=admin_id, text=error_msg, parse_mode="HTML")
        except Exception as alert_error:
            logger.error(f"Не удалось отправить ошибку администратору {admin_id}: {alert_error}")


async def show_generic_report_error(message: types.Message) -> None:
    try:
        await message.edit_text("❌ Ошибка, отчет не принят.", reply_markup=None)
    except Exception:
        try:
            await message.answer("❌ Ошибка, отчет не принят.")
        except Exception as send_error:
            logger.error(f"Не удалось показать пользователю сообщение об ошибке: {send_error}")
