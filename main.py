import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.session.aiohttp import AiohttpSession

from core.logger import logger
from core.config import TELEGRAM_TOKEN, REDIS_URL, DEV_GROUP_ID
from core.database import init_db
from middlewares.whitelist import WhitelistMiddleware
from handlers.menu import menu_router
from handlers.reports import reports_router
from handlers.errors import errors_router
from handlers.edit import edit_router
from services.scheduler import setup_scheduler

async def main():
    logger.info("--> Начался запуск функции main()...")
    await init_db()
    logger.info("--> База данных SQLite инициализирована.")
    
    # Initialize bot without proxy to avoid connection issues
    bot = Bot(token=TELEGRAM_TOKEN)
    
    # Инициализация и запуск планировщика
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("--> Планировщик задач (Cron) запущен.")

    # Setup Redis Storage
    storage = RedisStorage.from_url(REDIS_URL)
    dp = Dispatcher(storage=storage)
    
    # Register middlewares
    dp.message.middleware(WhitelistMiddleware())
    dp.callback_query.middleware(WhitelistMiddleware())
    
    # Register routers
    dp.include_router(menu_router)
    dp.include_router(reports_router)
    dp.include_router(edit_router)
    dp.include_router(errors_router)
    
    logger.info("--> Объект бота создан. Пробуем связаться с Telegram (delete_webhook)...")
    await bot.delete_webhook(drop_pending_updates=True)
    
    logger.info("Бот Restobot v2 запущен и готов к работе...")
    if DEV_GROUP_ID:
        try:
            import socket
            container_id = socket.gethostname()
            marker_path = "/app/data/.last_container_id"
            is_rebuild = True
            try:
                with open(marker_path, "r") as f:
                    if f.read().strip() == container_id:
                        is_rebuild = False
            except FileNotFoundError:
                pass
            with open(marker_path, "w") as f:
                f.write(container_id)
            
            if is_rebuild:
                text = "✅ Код серва обновлен и бот успешно запущен!"
            else:
                text = "🔄 Бот рестартнут (docker compose restart)"
            await bot.send_message(chat_id=int(DEV_GROUP_ID), text=text)
        except Exception as e:
            logger.error(f"Failed to send startup message: {e}")
            
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
