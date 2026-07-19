import os
import shutil
from aiogram import Bot
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.logger import logger
from core.config import ADMIN_ID, now_vlad
from core.database import DATA_DIR

async def backup_database(bot: Bot):
    try:
        source_db = os.path.join(DATA_DIR, 'restobot.db')
        if not os.path.exists(source_db):
            logger.warning("Нет базы данных для бэкапа.")
            return

        backup_date = now_vlad().strftime("%Y_%m_%d")
        backup_filename = f"restobot_backup_{backup_date}.db"
        backup_path = os.path.join(DATA_DIR, backup_filename)
        
        # Создаем копию БД
        shutil.copy2(source_db, backup_path)
        
        # Отправляем файл админу
        backup_file = FSInputFile(backup_path)
        for admin in ADMIN_ID:
            try:
                await bot.send_document(
                    chat_id=admin,
                    document=backup_file,
                    caption=f"📦 Ежедневный бэкап базы данных ({backup_date})"
                )
            except Exception:
                pass
        
        # Удаляем старые бэкапы (старше 7 дней)
        current_time = now_vlad().timestamp()
        for f in os.listdir(DATA_DIR):
            if f.startswith("restobot_backup_") and f.endswith(".db"):
                f_path = os.path.join(DATA_DIR, f)
                if current_time - os.path.getctime(f_path) > 7 * 86400:
                    os.remove(f_path)
                    
        logger.info(f"Бэкап {backup_filename} успешно создан и отправлен.")
    except Exception as e:
        logger.error(f"Ошибка создания бэкапа: {e}")

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    # Запуск бэкапа каждый день в 04:00 по серверному времени
    scheduler.add_job(backup_database, 'cron', hour=4, minute=0, args=[bot])
    
    return scheduler
