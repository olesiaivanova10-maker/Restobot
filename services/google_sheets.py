import time
from datetime import datetime
import gspread
from tenacity import retry, stop_after_attempt, wait_exponential

from core.logger import logger
from core.config import (
    GOOGLE_SHEET_ID,
    KISA_STEPS_CLOSE,
    LIST_MAPPING,
    STEPS_CLOSE,
    STEPS_OPEN,
    now_vlad,
)

# --- Кэш для клиента Google Sheets ---
_cached_sheets_client = None
_sheets_client_auth_time = 0

def get_sheets_client():
    """Безопасное получение клиента Google Sheets с кэшированием на 45 минут"""
    global _cached_sheets_client, _sheets_client_auth_time
    
    current_time = time.time()
    
    # Если клиент уже создан и с момента авторизации прошло меньше 45 минут (2700 секунд)
    if _cached_sheets_client and (current_time - _sheets_client_auth_time < 2700):
        return _cached_sheets_client
        
    # Если клиента нет или токен протух — читаем файл и авторизуемся заново
    try:
        _cached_sheets_client = gspread.service_account(filename="credentials.json")
        _sheets_client_auth_time = current_time
        logger.info("🔄 Google Sheets клиент успешно авторизован и сохранен в кэш.")
        return _cached_sheets_client
    except Exception as e:
        logger.error(f"❌ Ошибка авторизации Google Sheets: {e}")
        return None

def col_to_letter(col_idx: int) -> str:
    letter = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        letter = chr(65 + remainder) + letter
    return letter

def clean_text_value(val: str, row: int) -> str:
    val = str(val).strip()
    if not val:
        return val
        
    # Жесткая проверка на любые формы "нет"
    val_lower = val.lower().replace('.', '').replace(',', '').strip()
    negative_phrases = ["нет", "нету", "отсутствует", "не было", "небыло", "ничего", "-", "пусто"]
    if val_lower in negative_phrases or val_lower.startswith("нет "):
        return "Нет"
    
    try:
        float(val.replace(',', '.'))
        return val
    except ValueError:
        pass

    if row in [2, 3, 4, 5, 11, 13, 14]:
        while val.endswith('.'):
            val = val[:-1].strip()
        if val:
            val = val[0].upper() + val[1:]
            
    return val

def get_block_info_from_rows(row1: list, row6: list, target_date: str, report_type: str) -> dict:
    row1 = list(row1)
    row6 = list(row6)
    
    max_len = max(len(row1), len(row6))
    
    # Добиваем длину массива, чтобы она была кратна 3 (ширине нового блока)
    pad_len = (3 - (max_len % 3)) % 3
    max_len += pad_len
    
    row1.extend([""] * (max_len - len(row1)))
    row6.extend([""] * (max_len - len(row6)))

    last_block_start_idx = -1

    # Идем по таблице шагами по 3 (по блокам)
    for i in range(0, max_len, 3):
        c_idx = i + 2 # Индекс колонки C (3-я в блоке)
        
        val_c1 = str(row1[c_idx] if c_idx < len(row1) else "").strip()
        val_c6 = str(row6[c_idx] if c_idx < len(row6) else "").strip()
        
        if val_c1 or val_c6:
            last_block_start_idx = i

        # Поиск по C1 (для Открытия)
        if report_type == "Открытие" and val_c1 == target_date:
            start_col = i + 1
            open_time = str(row1[i + 1] if i + 1 < len(row1) else "").strip()
            return {"found": True, "start_col": start_col, "open_time": open_time, "close_time": ""}
        
        # Поиск по C6 (для Закрытия)
        elif report_type == "Закрытие" and val_c6 == target_date:
            start_col = i + 1
            close_time = str(row6[i + 1] if i + 1 < len(row6) else "").strip()
            return {"found": True, "start_col": start_col, "open_time": "", "close_time": close_time}

    # Если не нашли — выдаем стартовую колонку для следующего пустого блока
    fallback_col = (last_block_start_idx + 3 + 1) if last_block_start_idx != -1 else 1
    return {"found": False, "start_col": fallback_col, "open_time": "", "close_time": ""}

def get_block_info(worksheet, target_date: str, report_type: str) -> dict:
    try:
        row1 = worksheet.row_values(1)
    except Exception:
        row1 = []
    try:
        row6 = worksheet.row_values(6)
    except Exception:
        row6 = []
    return get_block_info_from_rows(row1, row6, target_date, report_type)

def get_batch_shift_status(sheet_names: list[str], target_date_open: str, target_date_close: str) -> dict:
    client = get_sheets_client()
    if not client:
        return {name: {"is_opened": False, "is_closed": False} for name in sheet_names}
        
    try:
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
        ranges = []
        for name in sheet_names:
            ranges.append(f"'{name}'!1:1")
            ranges.append(f"'{name}'!6:6")
            
        res = spreadsheet.values_batch_get(ranges)
        value_ranges = res.get('valueRanges', [])
        
        results = {}
        for i, name in enumerate(sheet_names):
            try:
                row1_data = value_ranges[i*2].get('values', [])
                row1 = row1_data[0] if row1_data else []
            except IndexError:
                row1 = []
                
            try:
                row6_data = value_ranges[i*2 + 1].get('values', [])
                row6 = row6_data[0] if row6_data else []
            except IndexError:
                row6 = []
                
            open_info = get_block_info_from_rows(row1, row6, target_date_open, "Открытие")
            close_info = get_block_info_from_rows(row1, row6, target_date_close, "Закрытие")
            
            is_opened = open_info["found"] and open_info["open_time"] != ""
            is_closed = close_info["found"] and close_info["close_time"] != ""
            
            results[name] = {
                "is_opened": is_opened,
                "is_closed": is_closed
            }
        return results
    except Exception as e:
        logger.error(f"Error in get_batch_shift_status: {e}")
        return {name: {"is_opened": False, "is_closed": False} for name in sheet_names}

from datetime import timedelta

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def update_google_sheet(sheet_name: str, report_type: str, collected_data: dict, target_date: str = None):
    sheets_client = get_sheets_client()
    if not sheets_client:
        logger.error("Google Sheets client не инициализирован")
        raise Exception("Google Sheets client init failed")
        
    spreadsheet = sheets_client.open_by_key(GOOGLE_SHEET_ID)
    worksheet = spreadsheet.worksheet(sheet_name)
    
    # Используем переданную дату, или вычисляем как раньше
    if not target_date:
        if report_type == "Открытие":
            target_date = now_vlad().strftime("%d.%m")
        else:
            target_date = (now_vlad() - timedelta(days=1)).strftime("%d.%m")
        
    current_time = now_vlad().strftime("%H:%M")
    
    info = get_block_info(worksheet, target_date, report_type)
    start_col = info["start_col"]

    col_b_let = col_to_letter(start_col + 1)

    if report_type == "Открытие":
        values = [[current_time]]
        for idx, h in enumerate(STEPS_OPEN):
            r = idx + 2
            final_val = clean_text_value(collected_data.get(h, "Нет"), r)
            values.append([final_val])
            
        range_str = f"{col_b_let}1:{col_b_let}{len(STEPS_OPEN) + 1}"
        worksheet.update(values=values, range_name=range_str)
            
    elif report_type == "Закрытие":
        close_steps = KISA_STEPS_CLOSE if sheet_name == LIST_MAPPING["kisa"] else STEPS_CLOSE
        values = [[current_time]]
        for idx, h in enumerate(close_steps):
            r = idx + 7
            default_fallback = "Информация отсутствует" if h == "Количество гостей" else "Нет"
            final_val = clean_text_value(collected_data.get(h, default_fallback), r)
            values.append([final_val])
            
        range_str = f"{col_b_let}6:{col_b_let}{len(close_steps) + 6}"
        worksheet.update(values=values, range_name=range_str)

    # После записи в лист ресторана — синхронизируем в Доклад
    sync_to_doklad(spreadsheet, sheet_name, report_type, target_date)


def sync_to_doklad(spreadsheet, sheet_name: str, report_type: str, target_date: str = None):
    """Синхронизирует данные из листа ресторана в лист Доклад."""
    from core.config import DOKLAD_SHEET_NAME, DOKLAD_EST_ORDER, DOKLAD_ROW_MAP, DOKLAD_ROW_LABELS

    try:
        doklad_ws = spreadsheet.worksheet(DOKLAD_SHEET_NAME)
        rest_ws = spreadsheet.worksheet(sheet_name)
    except Exception as e:
        logger.error(f"Не удалось открыть листы для синхронизации Доклада: {e}")
        return

    # Определяем колонку ресторана в Докладе (B=2, C=3, D=4, E=5)
    if sheet_name not in DOKLAD_EST_ORDER:
        logger.warning(f"Ресторан '{sheet_name}' не найден в DOKLAD_EST_ORDER")
        return
    est_col_idx = DOKLAD_EST_ORDER.index(sheet_name) + 2  # B=2, C=3, D=4, E=5

    # Используем переданную дату, или вычисляем как раньше
    if not target_date:
        if report_type == "Открытие":
            target_date = now_vlad().strftime("%d.%m")
        else:
            target_date = (now_vlad() - timedelta(days=1)).strftime("%d.%m")

    # Находим блок даты в листе ресторана
    rest_info = get_block_info(rest_ws, target_date, report_type)
    if not rest_info["found"]:
        logger.warning(f"Блок даты {target_date} не найден в листе {sheet_name}")
        return
    rest_data_col = rest_info["start_col"] + 1  # колонка с данными

    # У Кисы две дополнительные строки закрытия, остальные листы остаются 15-строчными.
    block_height = 17 if sheet_name == LIST_MAPPING["kisa"] else 15
    rest_col_letter = col_to_letter(rest_data_col)
    try:
        rest_values = rest_ws.get(f"{rest_col_letter}1:{rest_col_letter}{block_height}")
    except Exception:
        rest_values = []
    # Преобразуем в плоский список и дополняем пустыми значениями до высоты блока.
    rest_flat = []
    for row in rest_values:
        rest_flat.append(row[0] if row else "")
    while len(rest_flat) < block_height:
        rest_flat.append("")

    # Находим или создаём блок даты в Докладе
    # Блок Доклада: 5 колонок (дата+метки, 4 ресторана)
    try:
        doklad_row1 = doklad_ws.row_values(1)
    except Exception:
        doklad_row1 = []

    doklad_block_start = -1
    last_block_end = 0
    for i in range(0, len(doklad_row1), 5):
        val = str(doklad_row1[i]).strip() if i < len(doklad_row1) else ""
        if val:
            last_block_end = i + 5
        if val == target_date:
            doklad_block_start = i
            break

    if doklad_block_start == -1:
        # Создаём новый блок
        doklad_block_start = last_block_end
        date_col_letter = col_to_letter(doklad_block_start + 1)
        # Записываем дату в строку 1
        doklad_ws.update(values=[[target_date]], range_name=f"{date_col_letter}1")
        # Записываем метки A2:A11 (только для первого блока, колонка A)
        if doklad_block_start == 0:
            label_values = [[label] for label in DOKLAD_ROW_LABELS]
            doklad_ws.update(values=label_values, range_name=f"{date_col_letter}2:{date_col_letter}11")

    # Вычисляем колонку ресторана в этом блоке Доклада
    # est_col_idx: 2=B(Kisa), 3=C(Asienda), 4=D(Sinichka), 5=E(Bufet)
    # В блоке: offset 1=Kisa, 2=Asienda, 3=Sinichka, 4=Bufet
    doklad_col = doklad_block_start + (est_col_idx - 1)  # 0-indexed
    doklad_col_letter = col_to_letter(doklad_col + 1)  # 1-indexed for col_to_letter

    # Копируем данные по маппингу
    updates = []
    for rest_row, doklad_row in DOKLAD_ROW_MAP:
        if sheet_name == LIST_MAPPING["kisa"] and rest_row == 14:
            rest_row = 16
        value = rest_flat[rest_row - 1] if rest_row - 1 < len(rest_flat) else ""
        updates.append({
            "range": f"{doklad_col_letter}{doklad_row}",
            "values": [[value]]
        })

    if updates:
        doklad_ws.batch_update(updates)
        logger.info(f"Доклад синхронизирован: {sheet_name} ({report_type}) → блок {target_date}")
