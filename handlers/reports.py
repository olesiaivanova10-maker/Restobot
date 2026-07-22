import os
import asyncio
import re
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.logger import logger
from core.config import AI_PROMPTS, STEPS_OPEN, STEPS_CLOSE, KISA_STEPS_CLOSE, LIST_MAPPING
from states.report import ReportSteps
from services.ai import encode_image_to_base64, get_parsed_report, optimize_image_for_ai
from services.google_sheets import update_google_sheet
from services.db import mark_shift_open, mark_shift_closed
from services.error_reporting import notify_admins_about_error, show_generic_report_error

reports_router = Router()

user_payload_storage = {}

def is_missing_report_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        status = str(value.get("status", "")).strip().lower()
        actual_value = value.get("value")
        if status == "пропущено":
            return True
        return is_missing_report_value(actual_value)

    text = str(value).strip()
    return text == "" or text.lower() == "пропущено"

def get_close_steps(est_key: str) -> list[str]:
    return KISA_STEPS_CLOSE if est_key == "kisa" else STEPS_CLOSE

def get_ai_prompt_key(report_type: str, est_key: str) -> str:
    if report_type == "Закрытие" and est_key == "kisa":
        return "Закрытие:kisa"
    return report_type

async def ask_missing_items(user_id: int, missing_queue: list[str], message: types.Message, state: FSMContext):
    items_text = "\n".join([f"— {item}" for item in missing_queue])
    text = (
        "🔎 <b>Некоторые обязательные пункты отчёта не найдены:</b>\n\n"
        f"{items_text}\n\n"
        "Пожалуйста, напишите недостающую информацию в <b>одном сообщении</b> (или прикрепите фото)."
    )
    await state.set_state(ReportSteps.waiting_for_missing_item)
    prompt_message = await message.reply(text, parse_mode="HTML")
    await state.update_data(service_message_ids=[prompt_message.message_id])


async def delete_service_messages(message: types.Message, state: FSMContext) -> None:
    user_data = await state.get_data()
    message_ids = user_data.get("service_message_ids", [])
    for message_id in message_ids:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=message_id)
        except Exception:
            pass
    if message_ids:
        await state.update_data(service_message_ids=[])

@reports_router.message(ReportSteps.waiting_for_combined_report, F.text | F.photo | F.document)
async def handle_initial_packet(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"==> RECEIVED PACKET from user {user_id}: type={message.content_type}, mg_id={message.media_group_id}")
    user_data = await state.get_data()
    menu_message_id = user_data.get("menu_message_id")
    
    if menu_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=menu_message_id)
            await state.update_data(menu_message_id=None)
        except Exception:
            pass

    if user_id not in user_payload_storage:
        user_payload_storage[user_id] = {"messages": [], "task": None}
        
    user_payload_storage[user_id]["messages"].append(message)
    
    if user_payload_storage[user_id]["task"]:
        user_payload_storage[user_id]["task"].cancel()
        
    user_payload_storage[user_id]["task"] = asyncio.create_task(
        wait_and_process_user_payload(user_id, state)
    )

async def wait_and_process_user_payload(user_id: int, state: FSMContext):
    try:
        await asyncio.sleep(4.0)
        data = user_payload_storage.pop(user_id, None)
        if not data:
            return
        
        messages_packet = data["messages"]
        await process_report_payload(messages_packet, state)
    except asyncio.CancelledError:
        pass

async def process_report_payload(messages_packet: list, state: FSMContext):
    message = messages_packet[0]
    user_id = message.from_user.id
    status_msg = await message.reply("⏳ Изучаю данные...")
    
    user_data = await state.get_data()
    accumulated_text = user_data.get("accumulated_text", "")
    stale_photo_ids = user_data.get("accumulated_photo_ids", [])
    current_photo_ids = []
    image_paths = []
    image_stats = []
    
    try:
        if stale_photo_ids:
            logger.warning(
                f"Clearing {len(stale_photo_ids)} stale photo(s) from state before AI request for user {user_id}"
            )
            await state.update_data(accumulated_photo_ids=[])

        for msg in messages_packet:
            if msg.text: accumulated_text += msg.text + "\n"
            if msg.caption: accumulated_text += msg.caption + "\n"
            if msg.photo:
                current_photo_ids.append(msg.photo[-1].file_id)

        # Текст можно хранить как историю, а фото держим только на один AI-запрос.
        await state.update_data(accumulated_text=accumulated_text, accumulated_photo_ids=[])
        
        for file_id in current_photo_ids:
            tmp_path = f"img_{file_id}.jpg"
            await msg.bot.download(file_id, destination=tmp_path)
            image_stats.append(optimize_image_for_ai(tmp_path))
            image_paths.append(tmp_path)

        report_type = user_data["chosen_type"]
        est_key = user_data.get("est_key")
        expected_steps = STEPS_OPEN if report_type == "Открытие" else get_close_steps(est_key)
        collected_data = user_data.get("collected_data", {})

        ai_text = f"История сообщений отчета:\n{accumulated_text.strip()}"

        ai_contents = [{"type": "text", "text": ai_text}]
        for path in image_paths:
            ai_contents.append({
                "type": "image_url", 
                "image_url": {"url": f"data:image/jpeg;base64,{encode_image_to_base64(path)}"}
            })

        if image_stats or stale_photo_ids:
            original_total = sum(item["original_size"] for item in image_stats)
            optimized_total = sum(item["optimized_size"] for item in image_stats)
            logger.info(
                "AI report request prepared: "
                f"user={user_id}, current_photos={len(current_photo_ids)}, "
                f"stale_photos_cleared={len(stale_photo_ids)}, "
                f"image_bytes={original_total}->{optimized_total}, "
                f"text_chars={len(ai_text)}"
            )

        prompt_key = get_ai_prompt_key(report_type, est_key)
        parsed_blocks = await get_parsed_report(report_type, AI_PROMPTS[prompt_key], ai_contents)

        for step in expected_steps:
            val = None
            for key, v in parsed_blocks.items():
                if step.lower() in key.lower() or key.lower() in step.lower():
                    val = v
                    break
            
            if not is_missing_report_value(val):
                collected_data[step] = val

        missing_queue = []
        for step in expected_steps:
            val = collected_data.get(step)
            if is_missing_report_value(val):
                missing_queue.append(step)

        if missing_queue:
            lower_text = accumulated_text.lower()
            keywords_map = {
                "Стоп лист": ["стоп лист", "stop list", "стоплист", "стоп листа"],
                "Наличные": ["наличные", "cash"],
                "Безнал": ["безнал", "безналичный"],
                "Депозиты": ["депозиты", "депозит"],
                "Общая выручка": ["выручка", "total revenue"],
                "Количество гостей": ["гости", "количество гостей"],
                "Опасные операции": ["опасные операции", "dangerous operations"],
                "Доклад об открытии смены": ["открытие смены", "отчет об открытии"],
                "Доклад об закрытии смены": ["закрытие смены", "отчет о закрытии"],
                "Блюда з": ["блюда", "dishes"],
                "Медуза": ["медуза"]
            }
            
            # Iterate over a copy to allow removal
            for missing in missing_queue[:]:
                kwlist = keywords_map.get(missing, [])
                matched = False
                for kw in kwlist:
                    if kw in lower_text:
                        # Negation detection
                        neg_patterns = [rf"нет\s*{kw}", rf"отсутствует\s*{kw}", r"отсутствует"]
                        if any(re.search(pat, lower_text) for pat in neg_patterns):
                            collected_data[missing] = "Нет"
                        else:
                            # Extract value after keyword
                            pattern = rf"{kw}\s*[:\-]?\s*([^\n\r]+)"
                            m = re.search(pattern, lower_text)
                            if m:
                                collected_data[missing] = m.group(1).strip()
                            else:
                                # Fallback: whole line containing keyword
                                line_match = re.search(rf".*{kw}.*", lower_text)
                                collected_data[missing] = line_match.group(0).strip() if line_match else "[Не указано]"
                        matched = True
                        break
                if matched:
                    missing_queue.remove(missing)

            if missing_queue:
                # После попытки заполнения, если всё ещё есть пропуски – оставляем их для обычного запроса
                await state.update_data(collected_data=collected_data, missing_queue=missing_queue)
                try:
                    await status_msg.delete()
                except Exception:
                    pass
                await ask_missing_items(user_id, missing_queue, message, state)
                return

        # Если все пункты заполнены – переходим к подтверждению отчёта
        await state.update_data(collected_data=collected_data, missing_queue=[])
        await state.set_state(ReportSteps.waiting_for_confirmation)
        summary = "\n".join([f"<b>{k}</b>: {v}" for k, v in collected_data.items()])
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить и отправить", callback_data="confirm_report")],
            [InlineKeyboardButton(text="✏️ Дополнить / Исправить", callback_data="edit_report")]
        ])
        await status_msg.edit_text(f"✅ <b>Все данные собраны. Итоговый отчет:</b>\n\n{summary}\n\nЗаписываем в таблицу?", parse_mode="HTML", reply_markup=kb)

    except Exception as e:
        logger.exception(f"Ошибка парсинга пакета: {e}")
        await state.update_data(accumulated_photo_ids=[])
        await notify_admins_about_error(
            message.bot,
            e,
            message,
            context="Обработка отчёта сотрудника",
        )
        await show_generic_report_error(status_msg)
    finally:
        for p in image_paths:
            if os.path.exists(p): os.remove(p)

@reports_router.message(ReportSteps.waiting_for_missing_item, F.text | F.photo | F.document)
async def handle_missing_item_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"==> RECEIVED MISSING ITEM from user {user_id}: type={message.content_type}, mg_id={message.media_group_id}")
    await delete_service_messages(message, state)
    
    if user_id not in user_payload_storage:
        user_payload_storage[user_id] = {"messages": [], "task": None}
        
    user_payload_storage[user_id]["messages"].append(message)
    
    if user_payload_storage[user_id]["task"]:
        user_payload_storage[user_id]["task"].cancel()
        
    user_payload_storage[user_id]["task"] = asyncio.create_task(
        wait_and_process_followup_payload(user_id, state)
    )

async def wait_and_process_followup_payload(user_id: int, state: FSMContext):
    try:
        await asyncio.sleep(4.0)
        data = user_payload_storage.pop(user_id, None)
        if not data:
            return
        
        messages_packet = data["messages"]
        await process_report_payload(messages_packet, state)
    except asyncio.CancelledError:
        pass


@reports_router.callback_query(ReportSteps.waiting_for_confirmation, F.data == "confirm_report")
async def handle_confirm_report(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.answer("Сохраняю отчет...")
    except Exception:
        pass

    try:
        user_data = await state.get_data()
        sheet_name = user_data["chosen_sheet"]
        is_test = user_data.get("is_test", False)
        # Get the est_key without the DEV prefix if it exists
        base_sheet_name = sheet_name.replace("DEV(", "").replace(")", "") if is_test else sheet_name
        est_key = user_data.get("est_key") or next((k for k, v in LIST_MAPPING.items() if v == base_sheet_name), base_sheet_name)
        report_type = user_data["chosen_type"]
        collected_data = user_data["collected_data"]
        target_date = user_data.get("target_date")

        if report_type == "Открытие":
            await mark_shift_open(est_key, collected_data, is_test=is_test, target_date=target_date)
        else:
            await mark_shift_closed(est_key, collected_data, is_test=is_test)

        await asyncio.to_thread(
            update_google_sheet,
            sheet_name,
            report_type,
            collected_data,
            target_date,
        )
        await callback.message.edit_text("✅ Отчёт успешно принят!", reply_markup=None)
        await state.clear()
    except Exception as e:
        logger.exception(f"Ошибка сохранения отчёта: {e}")
        await notify_admins_about_error(
            callback.bot,
            e,
            callback.message,
            context="Сохранение отчёта в БД или Google Sheets",
        )
        await show_generic_report_error(callback.message)

@reports_router.callback_query(ReportSteps.waiting_for_confirmation, F.data == "edit_report")
async def handle_edit_report(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:
        pass

    await callback.message.edit_text("✏️ Режим редактирования.\nНапишите текстом, что нужно исправить (или прикрепите новые фото).\nБот обновит отчет с учетом новых данных.")
    await state.set_state(ReportSteps.waiting_for_missing_item)
    await state.update_data(
        current_item="Правки отчета",
        service_message_ids=[callback.message.message_id],
    )
