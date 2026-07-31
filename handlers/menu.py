import asyncio
import os
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.filters.callback_data import CallbackData

from core.logger import logger
from core.config import LIST_MAPPING, GOOGLE_SHEET_ID, GROUP_REST_MAP, DEV_GROUP_ID, GLAVADMIN_ID
from services.db import check_shift_open, check_shift_closed, check_all_shifts_status, clear_all_shifts
from services.google_sheets import get_sheets_client, col_to_letter
from states.report import ReportSteps
from handlers.edit import EditMenuCallback
from datetime import datetime, timedelta, timezone

def is_morning_window() -> bool:
    # Отключено по просьбе пользователя, чтобы Открытие всегда писалось за текущий день
    return False

APP_VERSION = "Неизвестно"
if os.path.exists("version.txt"):
    try:
        with open("version.txt", "r", encoding="utf-8") as f:
            APP_VERSION = f.read().strip()
    except Exception:
        pass

menu_router = Router()

class MenuCallback(CallbackData, prefix="menu"):
    action: str
    user_id: int
    est_key: str = ""
    is_test: int = 0
    prompt_only: int = 0

@menu_router.message(Command("menu"))
async def show_main_menu(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if chat_id in GROUP_REST_MAP:
        await state.update_data(command_message_id=message.message_id)
        est_key = GROUP_REST_MAP[chat_id]
        sheet_name = LIST_MAPPING[est_key]
        
        statuses = await check_all_shifts_status([est_key])
        is_opened_today = statuses.get(est_key, {}).get("is_opened_today", False)
        is_opened_yesterday = statuses.get(est_key, {}).get("is_opened_yesterday", False)
        is_closed_yesterday = statuses.get(est_key, {}).get("is_closed_yesterday", False)
        
        builder = InlineKeyboardBuilder()
        
        is_morning = is_morning_window()
        
        if is_opened_yesterday and not is_closed_yesterday:
            builder.add(types.InlineKeyboardButton(text="🌌 Закрыть смену", callback_data=MenuCallback(action="est_close", user_id=user_id, est_key=est_key, is_test=0).pack()))
        elif is_morning and not is_opened_yesterday:
            builder.add(types.InlineKeyboardButton(text="🌅 Открыть вчерашнюю смену", callback_data=MenuCallback(action="est_open_yesterday", user_id=user_id, est_key=est_key, is_test=0).pack()))
        elif not is_morning and not is_opened_today:
            builder.add(types.InlineKeyboardButton(text="🌅 Открыть смену", callback_data=MenuCallback(action="est_open", user_id=user_id, est_key=est_key, is_test=0).pack()))
        else:
            msg = "🙌 За вчера смена уже открыта, а для сегодня еще рано!" if is_morning else "🙌 Смена для этого заведения на сегодня уже открыта, а вчерашняя закрыта!"
            await message.answer(msg)
            
        builder.add(types.InlineKeyboardButton(text="✏️ Редактировать отчет", callback_data=EditMenuCallback(a="start", u=user_id, e=est_key).pack()))
        builder.add(types.InlineKeyboardButton(text="❌ Закрыть", callback_data=MenuCallback(action="close_menu", user_id=user_id).pack()))
        builder.adjust(1)
        return await message.answer(f"Управление сменой: {sheet_name}", reply_markup=builder.as_markup())

    builder = InlineKeyboardBuilder()
    if not is_morning_window():
        builder.add(types.InlineKeyboardButton(text="🌅 Открыть смену", callback_data=MenuCallback(action="open", user_id=user_id).pack()))
    else:
        builder.add(types.InlineKeyboardButton(text="🌅 Открыть вчерашнюю смену", callback_data=MenuCallback(action="open", user_id=user_id).pack()))
    builder.add(types.InlineKeyboardButton(text="🌌 Закрыть смену", callback_data=MenuCallback(action="close", user_id=user_id).pack()))
    
    if chat_id == DEV_GROUP_ID:
        builder.add(types.InlineKeyboardButton(
            text="🧪 Тест промпта открытия",
            callback_data=MenuCallback(action="prompt_open", user_id=user_id).pack()
        ))
        builder.add(types.InlineKeyboardButton(
            text="🧪 Тест промпта закрытия",
            callback_data=MenuCallback(action="prompt_close", user_id=user_id).pack()
        ))
        builder.add(types.InlineKeyboardButton(text="✏️ Редактировать отчет", callback_data=EditMenuCallback(a="selest", u=user_id, e="").pack()))
        builder.add(types.InlineKeyboardButton(text="🔗 Полезные ссылки", callback_data=MenuCallback(action="links", user_id=user_id).pack()))
        builder.add(types.InlineKeyboardButton(text="🛠️ [DEV] Сбросить тест-данные", callback_data=MenuCallback(action="dev_clear", user_id=user_id).pack()))
        builder.add(types.InlineKeyboardButton(text="❌ Закрыть", callback_data=MenuCallback(action="close_menu", user_id=user_id).pack()))
        builder.adjust(2, 1, 1, 1, 1, 1)
    else:
        if user_id in GLAVADMIN_ID and message.chat.type == "private":
            builder.add(types.InlineKeyboardButton(text="📦 Скачать Excel Бэкап", callback_data=MenuCallback(action="get_backup", user_id=user_id).pack()))
            builder.add(types.InlineKeyboardButton(text="❌ Закрыть", callback_data=MenuCallback(action="close_menu", user_id=user_id).pack()))
            builder.adjust(2, 1, 1)
        else:
            builder.add(types.InlineKeyboardButton(text="❌ Закрыть", callback_data=MenuCallback(action="close_menu", user_id=user_id).pack()))
            builder.adjust(2, 1)
        
    text = "Выбери действие для управления сменой:"
    if chat_id == DEV_GROUP_ID:
        text += f"\n\n🤖 Текущая сборка: {APP_VERSION}"
    await message.answer(text, reply_markup=builder.as_markup())

@menu_router.callback_query(MenuCallback.filter(F.action == "close_menu"))
async def handle_close_menu(callback: types.CallbackQuery, callback_data: MenuCallback, state: FSMContext):
    if callback.from_user.id != callback_data.user_id:
        return await callback.answer("Не тыкай!", show_alert=True)
    try:
        await callback.answer()
    except Exception:
        pass
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass

@menu_router.callback_query(MenuCallback.filter(F.action == "links"))
async def handle_links(callback: types.CallbackQuery, callback_data: MenuCallback):
    if callback.from_user.id != callback_data.user_id:
        return await callback.answer("Не тыкай!", show_alert=True)
    try:
        await callback.answer()
    except Exception:
        pass
        
    links_text = (
        "🔗 <b>Полезные ссылки:</b>\n\n"
        "🗄 <b>БД основная:</b> http://2.27.43.134:8080 (пароль: restoadmin)\n"
        "🧪 <b>БД DEV:</b> http://2.27.43.134:8081 (пароль: restoadmin)\n"
        f"📊 <b>Google Таблица:</b> https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit\n"
        "🧠 <b>Провайдер ИИ:</b> https://aitunnel.ru/\n"
        "☁️ <b>Хостинг/ВМ:</b> https://play2go.cloud/"
    )
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="main", user_id=callback_data.user_id).pack()))
    
    await callback.message.edit_text(links_text, parse_mode="HTML", reply_markup=builder.as_markup(), disable_web_page_preview=True)

@menu_router.callback_query(MenuCallback.filter(F.action == "main"))
async def handle_back_to_main(callback: types.CallbackQuery, callback_data: MenuCallback, state: FSMContext):
    if callback.from_user.id != callback_data.user_id:
        return await callback.answer("Не тыкай!", show_alert=True)
    try:
        await callback.answer()
    except Exception:
        pass
    await state.clear()
    user_id = callback_data.user_id
    chat_id = callback.message.chat.id
    
    if chat_id in GROUP_REST_MAP:
        est_key = GROUP_REST_MAP[chat_id]
        sheet_name = LIST_MAPPING[est_key]
        
        statuses = await check_all_shifts_status([est_key])
        is_opened_today = statuses.get(est_key, {}).get("is_opened_today", False)
        is_opened_yesterday = statuses.get(est_key, {}).get("is_opened_yesterday", False)
        is_closed_yesterday = statuses.get(est_key, {}).get("is_closed_yesterday", False)
        
        builder = InlineKeyboardBuilder()
        is_morning = is_morning_window()
        
        if is_opened_yesterday and not is_closed_yesterday:
            builder.add(types.InlineKeyboardButton(text="🌌 Закрыть смену", callback_data=MenuCallback(action="est_close", user_id=user_id, est_key=est_key, is_test=0).pack()))
        elif is_morning and not is_opened_yesterday:
            builder.add(types.InlineKeyboardButton(text="🌅 Открыть вчерашнюю смену", callback_data=MenuCallback(action="est_open_yesterday", user_id=user_id, est_key=est_key, is_test=0).pack()))
        elif not is_morning and not is_opened_today:
            builder.add(types.InlineKeyboardButton(text="🌅 Открыть смену", callback_data=MenuCallback(action="est_open", user_id=user_id, est_key=est_key, is_test=0).pack()))
        else:
            msg = "🙌 За вчера смена уже открыта, а для сегодня еще рано!" if is_morning else "🙌 Смена для этого заведения на сегодня уже открыта, а вчерашняя закрыта!"
            return await callback.message.edit_text(msg)
            
        builder.add(types.InlineKeyboardButton(text="❌ Закрыть", callback_data=MenuCallback(action="close_menu", user_id=user_id).pack()))
        builder.adjust(1)
        return await callback.message.edit_text(f"Управление сменой: {sheet_name}", reply_markup=builder.as_markup())

    builder = InlineKeyboardBuilder()
    if not is_morning_window():
        builder.add(types.InlineKeyboardButton(text="🌅 Открыть смену", callback_data=MenuCallback(action="open", user_id=user_id).pack()))
    else:
        builder.add(types.InlineKeyboardButton(text="🌅 Открыть вчерашнюю смену", callback_data=MenuCallback(action="open", user_id=user_id).pack()))
    builder.add(types.InlineKeyboardButton(text="🌌 Закрыть смену", callback_data=MenuCallback(action="close", user_id=user_id).pack()))
    
    if chat_id == DEV_GROUP_ID:
        builder.add(types.InlineKeyboardButton(
            text="🧪 Тест промпта открытия",
            callback_data=MenuCallback(action="prompt_open", user_id=user_id).pack()
        ))
        builder.add(types.InlineKeyboardButton(
            text="🧪 Тест промпта закрытия",
            callback_data=MenuCallback(action="prompt_close", user_id=user_id).pack()
        ))
        builder.add(types.InlineKeyboardButton(text="🔗 Полезные ссылки", callback_data=MenuCallback(action="links", user_id=user_id).pack()))
        builder.add(types.InlineKeyboardButton(text="🛠️ [DEV] Сбросить тест-данные", callback_data=MenuCallback(action="dev_clear", user_id=user_id).pack()))
        builder.add(types.InlineKeyboardButton(text="❌ Закрыть", callback_data=MenuCallback(action="close_menu", user_id=user_id).pack()))
        builder.adjust(2, 1, 1, 1, 1, 1)
    else:
        builder.add(types.InlineKeyboardButton(text="❌ Закрыть", callback_data=MenuCallback(action="close_menu", user_id=user_id).pack()))
        builder.adjust(2, 1)
    text = "Выбери действие для управления сменой:"
    if chat_id == DEV_GROUP_ID:
        text += f"\n\n🤖 Текущая сборка: {APP_VERSION}"
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@menu_router.callback_query(MenuCallback.filter(F.action.in_(["back_open", "back_close"])))
async def handle_back_to_action(callback: types.CallbackQuery, callback_data: MenuCallback, state: FSMContext):
    if callback.from_user.id != callback_data.user_id:
        return await callback.answer("Не тыкай!", show_alert=True)
    try:
        await callback.answer()
    except Exception:
        pass
    action = "open" if callback_data.action == "back_open" else "close"
    await state.clear()
    
    if callback.message.chat.id == DEV_GROUP_ID:
        await handle_action_choice(callback, callback_data) # Redirect to DB selection
    else:
        await process_action_choice(callback, action, callback_data.user_id, is_test=0)

@menu_router.callback_query(MenuCallback.filter(F.action == "dev_clear"))
async def handle_dev_clear(callback: types.CallbackQuery, callback_data: MenuCallback):
    if callback.from_user.id != callback_data.user_id:
        return await callback.answer("Не тыкай!", show_alert=True)
    try:
        await callback.answer()
    except Exception:
        pass
    await callback.message.edit_text("⏳ Определяю последнюю дату и выжигаю данные...")
    try:
        def clear_sheets():
            sheets_client = get_sheets_client()
            if not sheets_client: return
            spr = sheets_client.open_by_key(GOOGLE_SHEET_ID)
            
            for _, name in LIST_MAPPING.items():
                try:
                    ws = spr.worksheet(f"DEV({name})")
                    row1 = ws.row_values(1)
                    row1_fixed = [""] + row1 
                    
                    c = 1
                    last_valid_col = 1
                    while c + 2 < len(row1_fixed):
                        date_val = str(row1_fixed[c + 2]).strip()
                        if not date_val:
                            break
                        last_valid_col = c
                        c += 5
                    
                    col_2 = col_to_letter(last_valid_col + 1)
                    col_5 = col_to_letter(last_valid_col + 4)
                    
                    ranges = [
                        f"{col_2}1", 
                        f"{col_2}6", 
                        f"{col_2}2:{col_5}5", 
                        f"{col_2}7:{col_5}15"
                    ]
                    ws.batch_clear(ranges)
                except Exception as e:
                    logger.warning(f"Failed to clear DEV sheet {name}: {e}")
        
        await asyncio.to_thread(clear_sheets)
        await clear_all_shifts(is_test=True)
        await callback.message.edit_text("✅ <b>[DEV] Контент последней даты бескомпромиссно уничтожен на DEV листах и в тестовой БД!</b>", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка очистки: {e}")
        await callback.message.edit_text(f"❌ Ошибка очистки: {e}")

@menu_router.callback_query(MenuCallback.filter(F.action.in_(["open", "close"])))
async def handle_action_choice(callback: types.CallbackQuery, callback_data: MenuCallback):
    if callback.from_user.id != callback_data.user_id:
        return await callback.answer("Не тыкай!", show_alert=True)
        
    action = callback_data.action
    try:
        await callback.answer()
    except Exception:
        pass
        
    if callback.message.chat.id == DEV_GROUP_ID:
        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(text="🛠 Рабочая база", callback_data=MenuCallback(action=f"prod_{action}", user_id=callback_data.user_id).pack()))
        builder.add(types.InlineKeyboardButton(text="🧪 Тестовая база", callback_data=MenuCallback(action=f"test_{action}", user_id=callback_data.user_id).pack()))
        builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data=MenuCallback(action="main", user_id=callback_data.user_id).pack()))
        builder.adjust(1)
        await callback.message.edit_text("Выберите базу данных:", reply_markup=builder.as_markup())
    else:
        await process_action_choice(callback, action, callback_data.user_id, is_test=0)

@menu_router.callback_query(MenuCallback.filter(F.action.in_(["prod_open", "test_open", "prod_close", "test_close"])))
async def handle_db_choice(callback: types.CallbackQuery, callback_data: MenuCallback):
    if callback.from_user.id != callback_data.user_id:
        return await callback.answer("Не тыкай!", show_alert=True)
    try:
        await callback.answer()
    except Exception:
        pass
        
    action_parts = callback_data.action.split("_")
    is_test = 1 if action_parts[0] == "test" else 0
    actual_action = action_parts[1]
    
    await process_action_choice(callback, actual_action, callback_data.user_id, is_test=is_test)


@menu_router.callback_query(MenuCallback.filter(F.action.in_(["prompt_open", "prompt_close"])))
async def handle_prompt_test(callback: types.CallbackQuery, callback_data: MenuCallback, state: FSMContext):
    if callback.from_user.id != callback_data.user_id:
        return await callback.answer("Не тыкай!", show_alert=True)
    if callback.message.chat.id != DEV_GROUP_ID:
        return await callback.answer("Тест промпта доступен только в DEV-группе.", show_alert=True)

    action = "est_open" if callback_data.action == "prompt_open" else "est_close"
    prompt_callback_data = MenuCallback(
        action=action,
        user_id=callback_data.user_id,
        est_key="kisa",
        prompt_only=1,
    )
    await handle_establishment_choice(callback, prompt_callback_data, state)


async def process_action_choice(callback: types.CallbackQuery, action: str, user_id: int, is_test: int):
    report_type_display = "открытия" if action == "open" else "закрытия"
    await callback.message.edit_text(f"⏳ Проверяю доступные заведения для {report_type_display}...")
    
    est_keys = ["kisa"] if is_test else list(LIST_MAPPING.keys())
    statuses = await check_all_shifts_status(est_keys, is_test=bool(is_test))
    
    is_morning = is_morning_window()
    results = []
    
    for est_key in est_keys:
        is_opened_today = statuses.get(est_key, {}).get("is_opened_today", False)
        is_opened_yesterday = statuses.get(est_key, {}).get("is_opened_yesterday", False)
        is_closed_yesterday = statuses.get(est_key, {}).get("is_closed_yesterday", False)
        if action == "open":
            if is_morning:
                results.append(not is_opened_yesterday)
            else:
                results.append(not is_opened_today)
        else:
            results.append(is_opened_yesterday and not is_closed_yesterday)
            
    builder = InlineKeyboardBuilder()
    visible_buttons = 0
    
    for est_key, should_show in zip(est_keys, results):
        if should_show:
            if action == "open":
                if is_morning:
                    cb_action = "est_open_yesterday"
                else:
                    cb_action = "est_open"
            else:
                cb_action = "est_close"
                
            btn_text = f"DEV({LIST_MAPPING[est_key]})" if is_test else LIST_MAPPING[est_key]
            builder.add(types.InlineKeyboardButton(
                text=btn_text, 
                callback_data=MenuCallback(action=cb_action, user_id=user_id, est_key=est_key, is_test=is_test).pack()
            ))
            visible_buttons += 1
            
    if callback.message.chat.id == DEV_GROUP_ID:
        builder.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action=action, user_id=user_id).pack()))
    else:
        builder.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCallback(action="main", user_id=user_id).pack()))
        
    builder.adjust(1)
    
    if visible_buttons == 0:
        if action == "open":
            await callback.message.edit_text("🙌 Все заведения уже открыли смену на сегодня!", reply_markup=builder.as_markup())
        else:
            await callback.message.edit_text("🙌 Нет заведений, готовых к закрытию!", reply_markup=builder.as_markup())
    else:
        await callback.message.edit_text(f"Выбери заведение для {report_type_display}:", reply_markup=builder.as_markup())

@menu_router.callback_query(MenuCallback.filter(F.action.in_(["est_open", "est_open_yesterday", "est_close"])))
async def handle_establishment_choice(callback: types.CallbackQuery, callback_data: MenuCallback, state: FSMContext):
    if callback.from_user.id != callback_data.user_id:
        return await callback.answer("Не тыкай!", show_alert=True)
        
    action = "open" if "open" in callback_data.action else "close"
    try:
        await callback.answer()
    except Exception:
        pass
    
    est_key = callback_data.est_key
    is_test = callback_data.is_test
    prompt_only = bool(callback_data.prompt_only)
    report_type = "Открытие" if action == "open" else "Закрытие"
    if prompt_only:
        sheet_name = f"ТЕСТ ПРОМПТА ({LIST_MAPPING[est_key]})"
    else:
        sheet_name = f"DEV({LIST_MAPPING[est_key]})" if is_test else LIST_MAPPING[est_key]
    
    builder = InlineKeyboardBuilder()
    chat_id = callback.message.chat.id
    if chat_id in GROUP_REST_MAP:
        builder.add(types.InlineKeyboardButton(
            text="⬅️ Назад", 
            callback_data=MenuCallback(action="main", user_id=callback_data.user_id).pack()
        ))
    else:
        if chat_id == DEV_GROUP_ID:
            back_action = "main" if prompt_only else f"test_{action}" if is_test else f"prod_{action}"
            builder.add(types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=MenuCallback(action=back_action, user_id=callback_data.user_id).pack()
            ))
        else:
            builder.add(types.InlineKeyboardButton(
                text="⬅️ Назад", 
                callback_data=MenuCallback(action=f"back_{action}", user_id=callback_data.user_id).pack()
            ))
    
    if report_type == "Открытие":
        msg = (
            f"📍 {sheet_name} | 🌅 ОТКРЫТИЕ\n\n"
            f"💬 Пришлите отчет.\n"
            f"Шаблон:\n"
            f"```\n"
            f"Стоп лист - \n"
            f"Приход продуктов - \n"
            f"Приход хозов - \n"
            f"Доклад об открытии смены - \n"
            f"```"
        )
    else:
        msg = (
            f"📍 {sheet_name} | 🌌 ЗАКРЫТИЕ\n\n"
            f"📎 Сфотографируйте 037 и 048 *одной фотографией*\n"
            f"📎 Сфотографируйте отчет на А4 *второй фотографией*\n\n"
            f"Если есть поломки или пункты, о которых стоит знать при открытии - напишите в отчете по смене"
        )
        
    menu_msg = await callback.message.edit_text(msg, parse_mode="Markdown", reply_markup=builder.as_markup())
    
    from datetime import datetime, timedelta, timezone
    vvo_tz = timezone(timedelta(hours=10))
    now = datetime.now(vvo_tz)
    
    if callback_data.action == "est_open_yesterday":
        target_date = (now - timedelta(days=1)).strftime("%d.%m")
    elif callback_data.action == "est_close":
        target_date = (now - timedelta(days=1)).strftime("%d.%m")
    else:
        target_date = now.strftime("%d.%m")
    
    await state.update_data(
        chosen_sheet=sheet_name, 
        est_key=est_key,
        is_test=bool(is_test),
        prompt_only=prompt_only,
        chosen_type=report_type, 
        target_date=target_date,
        collected_data={}, 
        missing_queue=[],
        accumulated_text="",
        accumulated_photo_ids=[],
        menu_message_id=menu_msg.message_id,
        service_message_ids=[],
        command_message_id=(await state.get_data()).get("command_message_id")
    )
    await state.set_state(ReportSteps.waiting_for_combined_report)

@menu_router.callback_query(MenuCallback.filter(F.action == "get_backup"))
async def handle_get_backup(callback: types.CallbackQuery, callback_data: MenuCallback):
    if callback.from_user.id != callback_data.user_id:
        return await callback.answer("Не тыкай!", show_alert=True)
        
    await callback.answer("Генерирую бэкап, пожалуйста подождите...")
    
    import pandas as pd
    import os
    from aiogram.types import FSInputFile
    from services.db import get_all_shifts
    from core.database import DATA_DIR
    
    try:
        shifts = await get_all_shifts()
        if not shifts:
            return await callback.message.answer("База данных пока пуста.")
            
        data = []
        for s in shifts:
            row = {
                "Дата": s.date_str,
                "Заведение": s.establishment,
                "Открыто": s.is_opened,
                "Время открытия": s.open_time or "",
                "Стоп лист": s.open_stop_list or "",
                "Приход продуктов": s.open_products or "",
                "Приход хозов": s.open_household or "",
                "Доклад об открытии": s.open_report or "",
                "Закрыто": s.is_closed,
                "Время закрытия": s.close_time or "",
                "Наличные": s.close_cash or "",
                "Безнал": s.close_card or "",
                "Депозиты": getattr(s, "close_deposits", "") or "",
                "Общая выручка": s.close_revenue or "",
                "Количество гостей": s.close_guests or "",
                "Опасные операции": s.close_dangerous or "",
                "Блюда за счет заведения": s.close_comps or "",
                "Расходы на маркетинг": s.close_marketing or "",
                "Расходы на смену": s.close_expenses or "",
                "Медуза": getattr(s, "close_meduza", "") or "",
                "Доклад о закрытии": s.close_report or "",
            }
            data.append(row)
            
        df = pd.DataFrame(data)
        backup_path = os.path.join(DATA_DIR, "infinite_backup.xlsx")
        df.to_excel(backup_path, index=False)
        
        file = FSInputFile(backup_path)
        await callback.message.answer_document(
            document=file,
            caption="📦 Ваш бесконечный Excel бэкап со всеми данными."
        )
        os.remove(backup_path)
    except Exception as e:
        logger.error(f"Ошибка при генерации Excel: {e}")
        await callback.message.answer(f"❌ Ошибка при генерации бэкапа: {e}")
