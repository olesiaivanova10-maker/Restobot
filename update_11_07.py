import asyncio
import os
import sys
# Добавляем путь, чтобы импорты работали
sys.path.append("/app")
from core.database import AsyncSessionLocal
from models.shift import Shift
from sqlalchemy import select
from services.google_sheets import update_google_sheet, get_sheets_client, get_block_info, col_to_letter, clean_text_value, get_block_info_from_rows
from core.config import LIST_MAPPING, STEPS_CLOSE, GOOGLE_SHEET_ID
from services.google_sheets import _cached_sheets_client

data_kisa = {
    "Наличные": "49 120",
    "Безнал": "157 180",
    "Общая выручка": "210 300",
    "Количество гостей": "91",
    "Опасные операции": "-",
    "Блюда за счет заведения": "-",
    "Расходы на маркетинг": "-",
    "Доклад о закрытии смены": "все хорошо",
    "Расходы на смену": "11 000"
}

data_bufet = {
    "Наличные": "53 410",
    "Безнал": "145 260",
    "Общая выручка": "198 670",
    "Количество гостей": "1",
    "Опасные операции": "-",
    "Блюда за счет заведения": "-",
    "Расходы на маркетинг": "-",
    "Доклад о закрытии смены": "все хорошо",
    "Расходы на смену": "19 618"
}

async def update_db_and_sheets():
    async with AsyncSessionLocal() as session:
        for est_key, data in [("kisa", data_kisa), ("bufet", data_bufet)]:
            print(f"Обрабатываем {est_key} за 11.07...")
            stmt = select(Shift).where(Shift.date_str == "11.07", Shift.establishment == est_key)
            result = await session.execute(stmt)
            shift = result.scalar_one_or_none()
            
            if not shift:
                print(f"Смена для {est_key} на 11.07 не найдена, создаем новую.")
                shift = Shift(date_str="11.07", establishment=est_key, is_opened=True, is_closed=False)
                session.add(shift)
            
            shift.is_closed = True
            shift.close_cash = data["Наличные"]
            shift.close_card = data["Безнал"]
            shift.close_revenue = data["Общая выручка"]
            shift.close_guests = data["Количество гостей"]
            shift.close_dangerous = data["Опасные операции"]
            shift.close_comps = data["Блюда за счет заведения"]
            shift.close_marketing = data["Расходы на маркетинг"]
            shift.close_report = data["Доклад о закрытии смены"]
            shift.close_expenses = data["Расходы на смену"]
            
            await session.commit()
            print(f"✅ База данных обновлена для {est_key} 11.07")
            
            # Now update Google Sheets
            sheet_name = LIST_MAPPING[est_key]
            sheets_client = get_sheets_client()
            spreadsheet = sheets_client.open_by_key(GOOGLE_SHEET_ID)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            try:
                row1 = worksheet.row_values(1)
            except Exception:
                row1 = []
            try:
                row6 = worksheet.row_values(6)
            except Exception:
                row6 = []
                
            info = get_block_info_from_rows(row1, row6, "11.07", "Закрытие")
            start_col = info["start_col"]
            
            # Check if this date already exists in Открытие (C1 == 11.07)
            open_info = get_block_info_from_rows(row1, row6, "11.07", "Открытие")
            if open_info["found"]:
                start_col = open_info["start_col"]
            
            col_b_let = col_to_letter(start_col + 1)
            col_c_let = col_to_letter(start_col + 2)
            
            # 1. Update Date and Time
            worksheet.update(values=[["02:00", "11.07"]], range_name=f"{col_b_let}6:{col_c_let}6")
            
            # 2. Update Details
            values = []
            for idx, h in enumerate(STEPS_CLOSE):
                r = idx + 7
                val = data.get(h, "Нет")
                final_val = clean_text_value(val, r)
                values.append([final_val])
                
            range_str = f"{col_b_let}7:{col_b_let}{len(STEPS_CLOSE) + 6}"
            worksheet.update(values=values, range_name=range_str)
            print(f"✅ Google Таблица обновлена для {sheet_name} 11.07")

if __name__ == "__main__":
    asyncio.run(update_db_and_sheets())
