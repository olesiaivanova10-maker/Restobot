import asyncio
import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

# Загружаем окружение
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Настраиваем подключение к БД
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "restobot.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

from models.shift import Shift
from core.config import LIST_MAPPING

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

async def sync_sheets_to_db():
    print(f"Подключение к БД: {DB_PATH}")
    
    # Подключаемся к Google Sheets
    creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    
    SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
    spreadsheet = client.open_by_key(SHEET_ID)
    
    async with AsyncSessionLocal() as session:
        for sheet_key, sheet_name in LIST_MAPPING.items():
            print(f"Синхронизация листа: {sheet_name} ({sheet_key})")
            try:
                ws = spreadsheet.worksheet(sheet_name)
                # Получаем все данные листа
                all_values = ws.get_all_values()
                if not all_values or len(all_values) < 15:
                    continue
                
                max_cols = len(all_values[0])
                
                for c in range(0, max_cols, 3):
                    # Проверяем колонку C, F, I (индексы 2, 5, 8) на наличие даты открытия
                    if c + 2 >= len(all_values[0]):
                        continue
                    
                    date_open = all_values[0][c+2].strip() if len(all_values[0]) > c+2 else ""
                    if not date_open:
                        continue
                        
                    # Данные открытия
                    open_time = all_values[0][c+1].strip() if len(all_values[0]) > c+1 else ""
                    open_stop = all_values[1][c+1].strip() if len(all_values) > 1 and len(all_values[1]) > c+1 else ""
                    open_prod = all_values[2][c+1].strip() if len(all_values) > 2 and len(all_values[2]) > c+1 else ""
                    open_hoz = all_values[3][c+1].strip() if len(all_values) > 3 and len(all_values[3]) > c+1 else ""
                    open_rep = all_values[4][c+1].strip() if len(all_values) > 4 and len(all_values[4]) > c+1 else ""
                    
                    is_opened = bool(open_time)

                    # Данные закрытия (строка 6, индекс 5)
                    date_close = all_values[5][c+2].strip() if len(all_values) > 5 and len(all_values[5]) > c+2 else ""
                    close_time = all_values[5][c+1].strip() if len(all_values) > 5 and len(all_values[5]) > c+1 else ""
                    
                    close_cash = all_values[6][c+1].strip() if len(all_values) > 6 and len(all_values[6]) > c+1 else ""
                    close_card = all_values[7][c+1].strip() if len(all_values) > 7 and len(all_values[7]) > c+1 else ""
                    close_rev = all_values[8][c+1].strip() if len(all_values) > 8 and len(all_values[8]) > c+1 else ""
                    close_guests = all_values[9][c+1].strip() if len(all_values) > 9 and len(all_values[9]) > c+1 else ""
                    close_dang = all_values[10][c+1].strip() if len(all_values) > 10 and len(all_values[10]) > c+1 else ""
                    close_comps = all_values[11][c+1].strip() if len(all_values) > 11 and len(all_values[11]) > c+1 else ""
                    close_mark = all_values[12][c+1].strip() if len(all_values) > 12 and len(all_values[12]) > c+1 else ""
                    close_rep = all_values[13][c+1].strip() if len(all_values) > 13 and len(all_values[13]) > c+1 else ""
                    close_exp = all_values[14][c+1].strip() if len(all_values) > 14 and len(all_values[14]) > c+1 else ""
                    
                    is_closed = bool(close_time)

                    # --- Синхронизация Открытия ---
                    if date_open:
                        res = await session.execute(select(Shift).where(Shift.date_str == date_open, Shift.establishment == sheet_key))
                        shift = res.scalar_one_or_none()
                        if not shift:
                            shift = Shift(date_str=date_open, establishment=sheet_key)
                            session.add(shift)
                        
                        if is_opened:
                            shift.is_opened = True
                            shift.open_time = open_time
                            shift.open_stop_list = open_stop
                            shift.open_products = open_prod
                            shift.open_household = open_hoz
                            shift.open_report = open_rep
                            
                    # --- Синхронизация Закрытия ---
                    if date_close:
                        res2 = await session.execute(select(Shift).where(Shift.date_str == date_close, Shift.establishment == sheet_key))
                        shift2 = res2.scalar_one_or_none()
                        if not shift2:
                            shift2 = Shift(date_str=date_close, establishment=sheet_key)
                            session.add(shift2)
                            
                        if is_closed:
                            shift2.is_closed = True
                            shift2.close_time = close_time
                            shift2.close_cash = close_cash
                            shift2.close_card = close_card
                            shift2.close_revenue = close_rev
                            shift2.close_guests = close_guests
                            shift2.close_dangerous = close_dang
                            shift2.close_comps = close_comps
                            shift2.close_marketing = close_mark
                            shift2.close_expenses = close_exp
                            shift2.close_report = close_rep

                print(f"  Успешно обработан {sheet_name}")
            except Exception as e:
                print(f"  Ошибка при обработке {sheet_name}: {e}")
                
        await session.commit()
        print("Синхронизация завершена. БД обновлена.")

if __name__ == "__main__":
    asyncio.run(sync_sheets_to_db())
