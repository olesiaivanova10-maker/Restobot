import asyncio
from datetime import datetime, timedelta, timezone
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from core.logger import logger
from core.config import (
    GROUP_REST_MAP, LIST_MAPPING, 
    OPEN_FIELD_MAP, CLOSE_FIELD_MAP, DEV_GROUP_ID
)
from models.shift import Shift
from services.db import get_shift_by_date, get_session
from services.google_sheets import update_google_sheet
from states.report import ReportSteps

edit_router = Router()

# Global lock for editing: { est_key: {"user_id": int, "timestamp": datetime} }
EDIT_LOCKS = {}
LOCK_TIMEOUT = timedelta(minutes=10)

# All column names that are safe to edit via this interface
ALLOWED_COLUMNS = set(OPEN_FIELD_MAP.values()) | set(CLOSE_FIELD_MAP.values())

# Short codes for callback_data to fit Telegram's 64-byte limit
# report_type: "o" = Открытие, "c" = Закрытие
TYPE_CODE = {"o": "Открытие", "c": "Закрытие"}
TYPE_CODE_REV = {v: k for k, v in TYPE_CODE.items()}

# field_key: numeric index -> field name
OPEN_FIELDS = list(OPEN_FIELD_MAP.keys())   # ["Стоп лист", "Приход продуктов", ...]
CLOSE_FIELDS = list(CLOSE_FIELD_MAP.keys()) # ["Наличные", "Безнал", ...]

def field_idx_to_name(type_code: str, idx: int) -> str:
    fields = OPEN_FIELDS if type_code == "o" else CLOSE_FIELDS
    return fields[idx] if 0 <= idx < len(fields) else None

def field_name_to_idx(type_code: str, name: str) -> int:
    fields = OPEN_FIELDS if type_code == "o" else CLOSE_FIELDS
    return fields.index(name) if name in fields else -1

def vvo_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=10)))

class EditMenuCallback(CallbackData, prefix="ed"):
    a: str          # action: start, sdate, stype, sfield, cancel, selest
    u: int          # user_id
    e: str          # est_key (short: kisa, asienda, etc.)
    d: str = ""     # date_str (DD.MM)
    t: str = ""     # type code: "o" or "c"
    f: int = -1     # field index

def acquire_lock(est_key: str, user_id: int) -> bool:
    now = vvo_now()
    if est_key in EDIT_LOCKS:
        lock = EDIT_LOCKS[est_key]
        if lock["user_id"] != user_id and now - lock["timestamp"] < LOCK_TIMEOUT:
            return False
    EDIT_LOCKS[est_key] = {"user_id": user_id, "timestamp": now}
    return True

def release_lock(est_key: str, user_id: int):
    if est_key in EDIT_LOCKS and EDIT_LOCKS[est_key]["user_id"] == user_id:
        del EDIT_LOCKS[est_key]

def validate_chat_est(chat_id: int, est_key: str) -> bool:
    """Validate that est_key belongs to this chat. DEV group can edit any."""
    if chat_id == DEV_GROUP_ID:
        return est_key in LIST_MAPPING
    expected = GROUP_REST_MAP.get(chat_id)
    return expected is not None and expected == est_key


# ── DEV: Select establishment ──
@edit_router.callback_query(EditMenuCallback.filter(F.a == "selest"))
async def select_est(callback: types.CallbackQuery, callback_data: EditMenuCallback):
    user_id = callback.from_user.id
    if user_id != callback_data.u:
        return await callback.answer("Не тыкай!", show_alert=True)
    
    builder = InlineKeyboardBuilder()
    for est_key, sheet_name in LIST_MAPPING.items():
        builder.add(types.InlineKeyboardButton(
            text=f"🏠 {sheet_name}",
            callback_data=EditMenuCallback(a="start", u=user_id, e=est_key).pack()
        ))
    builder.add(types.InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=EditMenuCallback(a="cancel", u=user_id, e="").pack()
    ))
    builder.adjust(1)
    await callback.message.edit_text("🏠 Выберите заведение для редактирования:", reply_markup=builder.as_markup())


# ── Start: Select date ──
@edit_router.callback_query(EditMenuCallback.filter(F.a == "start"))
async def start_edit(callback: types.CallbackQuery, callback_data: EditMenuCallback, state: FSMContext):
    user_id = callback.from_user.id
    if user_id != callback_data.u:
        return await callback.answer("Не тыкай!", show_alert=True)
    
    est_key = callback_data.e
    if not validate_chat_est(callback.message.chat.id, est_key):
        return await callback.answer("❌ Нельзя редактировать отчеты другого заведения.", show_alert=True)
    
    if not acquire_lock(est_key, user_id):
        lock_user = EDIT_LOCKS[est_key]["user_id"]
        return await callback.answer(f"❌ Отчет редактируется другим пользователем (ID: {lock_user}).", show_alert=True)
    
    await state.clear()
    
    now = vvo_now()
    dates = [
        ("Сегодня", now),
        ("Вчера", now - timedelta(days=1)),
        ("Позавчера", now - timedelta(days=2))
    ]
    
    builder = InlineKeyboardBuilder()
    for label, dt in dates:
        date_str = dt.strftime("%d.%m")
        builder.add(types.InlineKeyboardButton(
            text=f"{label} ({date_str})", 
            callback_data=EditMenuCallback(a="sdate", u=user_id, e=est_key, d=date_str).pack()
        ))
    builder.add(types.InlineKeyboardButton(
        text="❌ Отмена", 
        callback_data=EditMenuCallback(a="cancel", u=user_id, e=est_key).pack()
    ))
    builder.adjust(1)
    await callback.message.edit_text("📅 Выберите день для редактирования отчета:", reply_markup=builder.as_markup())


# ── Select report type (Открытие / Закрытие) ──
@edit_router.callback_query(EditMenuCallback.filter(F.a == "sdate"))
async def select_date(callback: types.CallbackQuery, callback_data: EditMenuCallback):
    user_id = callback.from_user.id
    if user_id != callback_data.u:
        return await callback.answer("Не тыкай!", show_alert=True)
    
    est_key = callback_data.e
    if not validate_chat_est(callback.message.chat.id, est_key):
        return await callback.answer("❌ Нельзя редактировать отчеты другого заведения.", show_alert=True)
    if not acquire_lock(est_key, user_id):
        return await callback.answer("❌ Время ожидания истекло или отчет занят.", show_alert=True)
    
    date_str = callback_data.d
    shift = await get_shift_by_date(date_str, est_key)
    
    builder = InlineKeyboardBuilder()
    has_reports = False
    
    if shift and shift.is_opened:
        builder.add(types.InlineKeyboardButton(
            text="🌅 Открытие", 
            callback_data=EditMenuCallback(a="stype", u=user_id, e=est_key, d=date_str, t="o").pack()
        ))
        has_reports = True
    if shift and shift.is_closed:
        builder.add(types.InlineKeyboardButton(
            text="🌌 Закрытие", 
            callback_data=EditMenuCallback(a="stype", u=user_id, e=est_key, d=date_str, t="c").pack()
        ))
        has_reports = True
    
    builder.add(types.InlineKeyboardButton(
        text="🔙 Назад", 
        callback_data=EditMenuCallback(a="start", u=user_id, e=est_key).pack()
    ))
    builder.adjust(1)
    
    text = f"📅 Дата: {date_str}\nВыберите тип отчета для редактирования:"
    if not has_reports:
        text = f"📅 Дата: {date_str}\n\n❌ Нет сохраненных отчетов за этот день."
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


# ── Select field ──
@edit_router.callback_query(EditMenuCallback.filter(F.a == "stype"))
async def select_type(callback: types.CallbackQuery, callback_data: EditMenuCallback):
    user_id = callback.from_user.id
    if user_id != callback_data.u:
        return await callback.answer("Не тыкай!", show_alert=True)
    
    est_key = callback_data.e
    if not validate_chat_est(callback.message.chat.id, est_key):
        return await callback.answer("❌ Нельзя редактировать отчеты другого заведения.", show_alert=True)
    if not acquire_lock(est_key, user_id):
        return await callback.answer("❌ Время ожидания истекло или отчет занят.", show_alert=True)
    
    date_str = callback_data.d
    type_code = callback_data.t
    report_type = TYPE_CODE.get(type_code, "Открытие")
    
    field_map = OPEN_FIELD_MAP if type_code == "o" else CLOSE_FIELD_MAP
    fields = OPEN_FIELDS if type_code == "o" else CLOSE_FIELDS
    
    shift = await get_shift_by_date(date_str, est_key)
    
    builder = InlineKeyboardBuilder()
    for idx, field_name in enumerate(fields):
        builder.add(types.InlineKeyboardButton(
            text=f"✏️ {field_name}", 
            callback_data=EditMenuCallback(a="sfield", u=user_id, e=est_key, d=date_str, t=type_code, f=idx).pack()
        ))
    builder.add(types.InlineKeyboardButton(
        text="🔙 Назад", 
        callback_data=EditMenuCallback(a="sdate", u=user_id, e=est_key, d=date_str).pack()
    ))
    builder.adjust(1)
    
    text = f"📝 <b>Отчет: {report_type} ({date_str})</b>\n\n"
    if shift:
        for field_name in fields:
            db_col = field_map.get(field_name)
            val = str(getattr(shift, db_col, ""))
            if not val.strip():
                val_str = " <i>(пусто)</i>"
            elif "\n" in val:
                formatted_val = val.replace("\n", "\n  ")
                val_str = f"\n  {formatted_val}"
            else:
                val_str = f" {val}"
            text += f"🔹 <b>{field_name}:</b>{val_str}\n"
            
    text += "\n<i>Выберите поле для изменения:</i>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())


# ── Show current value, ask for new ──
@edit_router.callback_query(EditMenuCallback.filter(F.a == "sfield"))
async def select_field(callback: types.CallbackQuery, callback_data: EditMenuCallback, state: FSMContext):
    user_id = callback.from_user.id
    if user_id != callback_data.u:
        return await callback.answer("Не тыкай!", show_alert=True)
    
    est_key = callback_data.e
    if not validate_chat_est(callback.message.chat.id, est_key):
        return await callback.answer("❌ Нельзя редактировать отчеты другого заведения.", show_alert=True)
    if not acquire_lock(est_key, user_id):
        return await callback.answer("❌ Время ожидания истекло или отчет занят.", show_alert=True)
    
    date_str = callback_data.d
    type_code = callback_data.t
    report_type = TYPE_CODE.get(type_code, "Открытие")
    field_name = field_idx_to_name(type_code, callback_data.f)
    
    if not field_name:
        return await callback.answer("❌ Недопустимое поле.", show_alert=True)
    
    field_map = OPEN_FIELD_MAP if type_code == "o" else CLOSE_FIELD_MAP
    db_col = field_map.get(field_name)
    
    if not db_col or db_col not in ALLOWED_COLUMNS:
        return await callback.answer("❌ Недопустимое поле.", show_alert=True)
    
    shift = await get_shift_by_date(date_str, est_key)
    current_val = getattr(shift, db_col, "") if shift else ""
    
    await state.update_data(
        edit_est_key=est_key,
        edit_date_str=date_str,
        edit_report_type=report_type,
        edit_field_name=field_name,
        edit_db_col=db_col,
        edit_msg_id=callback.message.message_id
    )
    await state.set_state(ReportSteps.waiting_for_edit_value)
    
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="🔙 Отмена", 
        callback_data=EditMenuCallback(a="stype", u=user_id, e=est_key, d=date_str, t=type_code).pack()
    ))
    
    text = (
        f"📝 <b>Редактирование:</b> {field_name}\n"
        f"📅 <b>Дата:</b> {date_str}\n\n"
        f"<b>Текущее значение:</b>\n{current_val}\n\n"
        f"<i>Отправьте новое значение следующим сообщением:</i>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())


# ── Process text input ──
@edit_router.message(ReportSteps.waiting_for_edit_value, F.text)
async def process_edit_value(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    
    est_key = data.get("edit_est_key")
    date_str = data.get("edit_date_str")
    report_type = data.get("edit_report_type")
    field_name = data.get("edit_field_name")
    db_col = data.get("edit_db_col")
    
    if not db_col or db_col not in ALLOWED_COLUMNS:
        await state.clear()
        return await message.answer("❌ Ошибка: недопустимое поле для редактирования.")
    
    if not acquire_lock(est_key, user_id):
        await state.clear()
        return await message.answer("❌ Время ожидания истекло или отчет занят другим пользователем.")
    
    new_value = message.text.strip()
    
    async with get_session() as session:
        result = await session.execute(
            select(Shift).where(Shift.date_str == date_str, Shift.establishment == est_key)
        )
        shift = result.scalar_one_or_none()
        
        if not shift:
            await state.clear()
            release_lock(est_key, user_id)
            return await message.answer("❌ Отчет не найден в базе данных. Возможно, он был удалён.")
        
        setattr(shift, db_col, new_value)
        await session.commit()
        
        field_map = OPEN_FIELD_MAP if report_type == "Открытие" else CLOSE_FIELD_MAP
        collected_data = {}
        for ai_key, col in field_map.items():
            collected_data[ai_key] = getattr(shift, col, "")
    
    sheet_name = LIST_MAPPING[est_key]
    asyncio.create_task(asyncio.to_thread(update_google_sheet, sheet_name, report_type, collected_data))
    
    await state.clear()
    release_lock(est_key, user_id)
    
    logger.info(f"[EDIT] User {user_id} updated {est_key}/{date_str}/{report_type}/{field_name} = '{new_value[:50]}'")
    await message.reply(f"✅ Успешно обновлено поле <b>{field_name}</b>!", parse_mode="HTML")
    
    try:
        edit_msg_id = data.get("edit_msg_id")
        if edit_msg_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=edit_msg_id)
    except Exception:
        pass


# ── Cancel ──
@edit_router.callback_query(EditMenuCallback.filter(F.a == "cancel"))
async def cancel_edit(callback: types.CallbackQuery, callback_data: EditMenuCallback, state: FSMContext):
    user_id = callback.from_user.id
    if user_id != callback_data.u:
        return await callback.answer("Не тыкай!", show_alert=True)
    
    est_key = callback_data.e
    if est_key:
        release_lock(est_key, user_id)
    await state.clear()
    
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Редактирование отменено.")
