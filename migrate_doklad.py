"""
Одноразовый скрипт:
1. Удалить строку 1 в листе "Доклад", записать метки A2:A11
2. Исправить даты в листах "Киса бар" и "Буфет" (сдвиг 09-11.07 на +1 день)
"""
import gspread
from google.oauth2.service_account import Credentials
import os

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Ищем credentials.json
creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
client = gspread.authorize(creds)

# ID таблицы из .env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

spreadsheet = client.open_by_key(SHEET_ID)

# ============ ЗАДАЧА 2-3: Лист "Доклад" ============
print("=== Задача 2-3: Реструктуризация листа 'Доклад' ===")
try:
    doklad_ws = spreadsheet.worksheet("Доклад")
    
    # Удаляем первую строку
    print("Удаляю строку 1...")
    doklad_ws.delete_rows(1)
    
    # Записываем метки в A2:A11
    labels = [
        ["Открытие"], ["Стоп лист"], ["Закрытие"], ["Выручка"],
        ["Наличные"], ["Безнал"], ["Гостей"], ["Расходы на смену"],
        ["За счет заведения"], ["Опасные"]
    ]
    print("Записываю метки A2:A11...")
    doklad_ws.update(values=labels, range_name="A2:A11")
    
    print("✅ Лист 'Доклад' реструктуризирован!")
except Exception as e:
    print(f"❌ Ошибка при работе с листом 'Доклад': {e}")

# ============ ЗАДАЧА 4: Фикс дат в Кисе и Буфете ============
print("\n=== Задача 4: Фикс дат в листах 'Киса бар' и 'Буфет' ===")

DATE_SHIFT = {
    "09.07": "10.07",
    "10.07": "11.07", 
    "11.07": "12.07",
}

for sheet_name in ["Киса бар", "Буфет"]:
    try:
        ws = spreadsheet.worksheet(sheet_name)
        row1 = ws.row_values(1)
        row6 = ws.row_values(6)
        
        updates = []
        
        # Проверяем строку 1 (даты открытия)
        for col_idx, val in enumerate(row1):
            val_stripped = str(val).strip()
            if val_stripped in DATE_SHIFT:
                col_letter = chr(ord('A') + col_idx) if col_idx < 26 else None
                if col_letter:
                    new_date = DATE_SHIFT[val_stripped]
                    updates.append({
                        "range": f"{col_letter}1",
                        "values": [[new_date]]
                    })
                    print(f"  {sheet_name}: {col_letter}1: {val_stripped} → {new_date}")
        
        # Проверяем строку 6 (даты закрытия)
        for col_idx, val in enumerate(row6):
            val_stripped = str(val).strip()
            if val_stripped in DATE_SHIFT:
                col_letter = chr(ord('A') + col_idx) if col_idx < 26 else None
                if col_letter:
                    new_date = DATE_SHIFT[val_stripped]
                    updates.append({
                        "range": f"{col_letter}6",
                        "values": [[new_date]]
                    })
                    print(f"  {sheet_name}: {col_letter}6: {val_stripped} → {new_date}")
        
        if updates:
            ws.batch_update(updates)
            print(f"✅ {sheet_name}: {len(updates)} дат исправлено")
        else:
            print(f"ℹ️  {sheet_name}: дат для исправления не найдено")
            
    except Exception as e:
        print(f"❌ Ошибка при работе с листом '{sheet_name}': {e}")

print("\n=== Готово! ===")
