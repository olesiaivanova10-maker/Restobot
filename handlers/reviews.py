import sqlite3

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from core.config import LIST_MAPPING
from core.logger import logger
from services.reviews import save_review

REVIEW_LINKS = {
    "review_kisa": "kisa",
    "review_asienda": "asienda",
    "review_buffet": "bufet",
    "review_sinichka": "sinichka",
}

reviews_router = Router()
reviews_router.message.filter(F.chat.type == "private")


class ReviewSteps(StatesGroup):
    waiting_for_text = State()


@reviews_router.message(
    CommandStart(deep_link=True, magic=F.args.in_(REVIEW_LINKS)),
    flags={"public_review": True},
)
async def start_review(message: Message, state: FSMContext, command: CommandObject) -> None:
    venue = REVIEW_LINKS[command.args]
    prompt = await message.answer(
        f"Оставьте отзыв о заведении «{LIST_MAPPING[venue]}». "
        "Напишите его одним сообщением. Для отмены отправьте /cancel."
    )
    await state.set_data({"venue": venue, "prompt_id": prompt.message_id})
    await state.set_state(ReviewSteps.waiting_for_text)


@reviews_router.message(ReviewSteps.waiting_for_text, Command("cancel"), flags={"public_review": True})
async def cancel_review(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отзыв отменён. Чтобы начать заново, откройте ссылку с QR-кода.")


@reviews_router.message(
    ReviewSteps.waiting_for_text,
    (F.content_type != "text") | ~F.text.startswith("/"),
    flags={"public_review": True},
)
async def receive_review(message: Message, state: FSMContext) -> None:
    body = (message.text or "").strip()
    if not body:
        await message.answer("Пожалуйста, отправьте отзыв текстом.")
        return

    review = await state.get_data()
    try:
        await save_review(review["venue"], body, message.chat.id, review["prompt_id"])
    except sqlite3.Error:
        logger.exception("Не удалось сохранить отзыв")
        await message.answer("Не удалось сохранить отзыв. Пожалуйста, отправьте его ещё раз.")
        return

    await state.clear()
    await message.answer("Спасибо! Ваш отзыв сохранён.")
