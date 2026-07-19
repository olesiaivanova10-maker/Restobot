from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from core.config import ALLOWED_USERS, ALLOWED_GROUPS, GROUP_REST_MAP
from core.logger import logger

class WhitelistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Если списки пустые, временно пускаем всех (защита от дурака)
        if not ALLOWED_USERS and not ALLOWED_GROUPS and not GROUP_REST_MAP:
            return await handler(event, data)
            
        user = getattr(event, "from_user", None)
        
        chat = getattr(event, "chat", None)
        if not chat and hasattr(event, "message") and event.message:
            chat = getattr(event.message, "chat", None)
            
        if user:
            is_allowed = False
            
            # Проверяем персональный доступ
            if ALLOWED_USERS and user.id in ALLOWED_USERS:
                is_allowed = True
                
            # Проверяем доступ через разрешённую группу
            if chat and ALLOWED_GROUPS and chat.id in ALLOWED_GROUPS:
                is_allowed = True

            # Проверяем доступ через ресторанную группу (Киса, Асьенда, Синичка, Буфет)
            if chat and GROUP_REST_MAP and chat.id in GROUP_REST_MAP:
                is_allowed = True
                
            if not is_allowed:
                logger.warning(f"⚠️ Отбита атака чужака! ID: {user.id} (@{user.username}) пытается использовать бота в чате {chat.id if chat else 'Unknown'}.")
                return 
                
        # Если проверка пройдена — пропускаем запрос дальше
        return await handler(event, data)

