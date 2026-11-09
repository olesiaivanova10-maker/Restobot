from datetime import timedelta
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from core.config import ADMIN_ID, GLAVADMIN_ID, LIST_MAPPING, now_vlad
from services.db import get_shift_by_date
from services.reviews import count_reviews_by_venue

dashboard_router = Router()


def format_metric(value: str | None) -> str:
    text = " ".join((value or "").split())
    return (text[:13] + "…" if len(text) > 14 else text) or "—"


@dashboard_router.message(Command("dashboard"), F.chat.type == "private")
async def show_dashboard(message: Message) -> None:
    if not message.from_user or message.from_user.id not in {*ADMIN_ID, *GLAVADMIN_ID}:
        await message.answer("Общий отчёт доступен администраторам.")
        return

    day = now_vlad().date() - timedelta(days=1)
    review_counts = await count_reviews_by_venue(day)
    rows = [("Заведение", "Смена", "Выручка", "Гости", "Отзывы")]
    for venue, name in LIST_MAPPING.items():
        shift = await get_shift_by_date(day.strftime("%d.%m"), venue)
        status, revenue, guests = "—", "—", "—"
        if shift and shift.is_closed:
            status = "Закрыта"
            revenue = format_metric(shift.close_revenue)
            guests = format_metric(shift.close_guests)
        elif shift and shift.is_opened:
            status = "Открыта"
        rows.append((name, status, revenue, guests, str(review_counts.get(venue, 0))))

    widths = [max(map(len, column)) for column in zip(*rows)]
    table = "\n".join(
        " ".join(value.ljust(width) if index < 2 else value.rjust(width)
                 for index, (value, width) in enumerate(zip(row, widths)))
        for row in rows
    )
    await message.answer(
        f"<b>Общий отчёт за {day:%d.%m}</b> · Владивосток\n"
        f"<pre>{escape(table)}</pre>\n"
        "— данные отсутствуют",
        parse_mode="HTML",
    )
