import asyncio
import os
import sys

# Добавляем путь, чтобы импорты работали
sys.path.append("/app")

from core.database import AsyncSessionLocal
from models.shift import Shift
from sqlalchemy import select
from services.google_sheets import update_google_sheet, get_sheets_client, get_block_info, col_to_letter, clean_text_value, get_block_info_from_rows
from core.config import LIST_MAPPING, STEPS_OPEN, GOOGLE_SHEET_ID
from services.google_sheets import _cached_sheets_client

data_asienda = {
    "Стоп лист": "Нет",
    "Приход продуктов": "Начос 1.500 гр",
    "Приход хозов": "Нет",
    "Доклад об открытии смены": "Все в порядке"
}
open_time = "18:02"

async def update_db_and_sheets():
    async with AsyncSessionLocal() as session:
        est_key = "asienda"
        data = data_asienda
        print(f"Обрабатываем {est_key} за 12.07...")
        stmt = select(Shift).where(Shift.date_str == "12.07", Shift.establishment == est_key)
        result = await session.execute(stmt)
        shift = result.scalar_one_or_none()
        
        if not shift:
            print(f"Смена для {est_key} на 12.07 не найдена, создаем новую.")
            shift = Shift(date_str="12.07", establishment=est_key, is_opened=True, is_closed=False)
            session.add(shift)
        
        shift.is_opened = True
        shift.open_time = open_time
        shift.open_stop_list = data["Стоп лист"]
        shift.open_products = data["Приход продуктов"]
        shift.open_household = data["Приход хозов"]
        shift.open_report = data["Доклад об открытии смены"]
        
        await session.commit()
        print(f"✅ База данных обновлена для {est_key} 12.07")
        
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
            
        info = get_block_info_from_rows(row1, row6, "12.07", "Открытие")
        start_col = info["start_col"]
        
        col_b_let = col_to_letter(start_col + 1)
        col_c_let = col_to_letter(start_col + 2)
        
        # 1. Update Date and Time
        worksheet.update(values=[[open_time, "12.07"]], range_name=f"{col_b_let}1:{col_c_let}1")
        
        # 2. Update Details
        values = []
        for idx, h in enumerate(STEPS_OPEN):
            r = idx + 2
            val = data.get(h, "Нет")
            final_val = clean_text_value(val, r)
            values.append([final_val])
            
        range_str = f"{col_b_let}2:{col_b_let}{len(STEPS_OPEN) + 1}"
        worksheet.update(values=values, range_name=range_str)
        print(f"✅ Google Таблица обновлена для {sheet_name} 12.07")

if __name__ == "__main__":
    asyncio.run(update_db_and_sheets())
