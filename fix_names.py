import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "restobot.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def fix_names():
    async with AsyncSessionLocal() as session:
        # Удаляем дубликаты, которые были созданы с русскими названиями
        # (поскольку sync_sheets_to_db уже залил корректные данные с ключами)
        await session.execute(text("DELETE FROM shifts WHERE establishment IN ('Киса бар', 'Асьенда', 'Синичка', 'Буфет')"))
        await session.commit()
        print("Очистка старых названий завершена.")

if __name__ == "__main__":
    asyncio.run(fix_names())
