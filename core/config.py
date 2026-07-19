import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Часовой пояс Владивостока (GMT+10)
VLZ_TZ = ZoneInfo("Asia/Vladivostok")

def now_vlad() -> datetime:
    """Текущее время по Владивостоку."""
    return datetime.now(VLZ_TZ)

class Settings(BaseSettings):
    TELEGRAM_TOKEN: str
    GOOGLE_SHEET_ID: str
    
    ADMIN_ID: str
    ALLOWED_USERS: str = ""
    ALLOWED_GROUPS: str = ""
    
    DEV_GROUP_ID: Optional[str] = None
    GROUP_KISA: Optional[str] = None
    GROUP_ASIENDA: Optional[str] = None
    GROUP_SINICHKA: Optional[str] = None
    GROUP_BUFET: Optional[str] = None
    GLAVADMIN_ID: Optional[str] = None
    
    AI_API_KEY: str
    AI_BASE_URL: str = "https://api.proxyapi.ru/openai/v1"
    AI_MODEL: str = "gpt-4o-mini"
    
    REDIS_URL: str = "redis://redis:6379/0"
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'),
        env_file_encoding='utf-8', 
        extra='ignore'
    )

    @property
    def allowed_users_list(self) -> List[int]:
        if not self.ALLOWED_USERS:
            return []
        return [int(x.strip()) for x in self.ALLOWED_USERS.split(",") if x.strip().isdigit()]

    @property
    def allowed_groups_list(self) -> List[int]:
        if not self.ALLOWED_GROUPS:
            return []
        return [int(x.strip()) for x in self.ALLOWED_GROUPS.split(",") if x.strip().lstrip('-').isdigit()]

    @property
    def admin_ids_list(self) -> List[int]:
        if not self.ADMIN_ID:
            return []
        return [int(x.strip()) for x in str(self.ADMIN_ID).split(",") if x.strip().isdigit()]

    @property
    def glavadmin_ids_list(self) -> List[int]:
        if not self.GLAVADMIN_ID:
            return []
        return [int(x.strip()) for x in str(self.GLAVADMIN_ID).split(",") if x.strip().isdigit()]

settings = Settings()

# =====================================================================
# КОНФИГУРАЦИЯ
# =====================================================================
TELEGRAM_TOKEN = settings.TELEGRAM_TOKEN
GOOGLE_SHEET_ID = settings.GOOGLE_SHEET_ID

ADMIN_ID = settings.admin_ids_list
ALLOWED_USERS = settings.allowed_users_list
ALLOWED_GROUPS = settings.allowed_groups_list

DEV_GROUP_ID = int(settings.DEV_GROUP_ID) if settings.DEV_GROUP_ID else None
GROUP_KISA = int(settings.GROUP_KISA) if settings.GROUP_KISA else None
GROUP_ASIENDA = int(settings.GROUP_ASIENDA) if settings.GROUP_ASIENDA else None
GROUP_SINICHKA = int(settings.GROUP_SINICHKA) if settings.GROUP_SINICHKA else None
GROUP_BUFET = int(settings.GROUP_BUFET) if getattr(settings, "GROUP_BUFET", None) else None

GLAVADMIN_ID = settings.glavadmin_ids_list


GROUP_REST_MAP = {}
if GROUP_KISA:
    GROUP_REST_MAP[GROUP_KISA] = "kisa"
if GROUP_ASIENDA:
    GROUP_REST_MAP[GROUP_ASIENDA] = "asienda"
if GROUP_SINICHKA:
    GROUP_REST_MAP[GROUP_SINICHKA] = "sinichka"
if GROUP_BUFET:
    GROUP_REST_MAP[GROUP_BUFET] = "bufet"

PROXYAPI_KEY = settings.AI_API_KEY
AI_BASE_URL = settings.AI_BASE_URL
AI_MODEL = settings.AI_MODEL

REDIS_URL = settings.REDIS_URL

LIST_MAPPING = {
    "kisa": "Киса бар",
    "asienda": "Асьенда",
    "sinichka": "Синичка",
    "bufet": "Буфет",
}

DOKLAD_SHEET_NAME = "Доклад"

# Метки строк A2:A11 в листе Доклад
DOKLAD_ROW_LABELS = [
    "Открытие", "Стоп лист", "Закрытие", "Выручка",
    "Наличные", "Безнал", "Гостей", "Расходы на смену",
    "За счет заведения", "Опасные"
]

# Порядок ресторанов в колонках Доклада: B, C, D, E
DOKLAD_EST_ORDER = ["Киса бар", "Асьенда", "Синичка", "Буфет"]

# Маппинг: строка листа ресторана → строка листа Доклад
# (restaurant_row, doklad_row) — 1-indexed
DOKLAD_ROW_MAP = [
    (1, 2),    # open_time → Открытие
    (2, 3),    # Стоп лист → Стоп лист
    (6, 4),    # close_time → Закрытие
    (9, 5),    # Общая выручка → Выручка
    (5, 6),    # → Наличные
    (8, 7),    # Безнал → Безнал
    (10, 8),   # Кол-во гостей → Гостей
    (14, 9),   # Расходы на смену → Расходы на смену
    (12, 10),  # Блюда за счёт → За счет заведения
    (11, 11),  # Опасные → Опасные
]

STEPS_OPEN = ["Стоп лист", "Приход продуктов", "Приход хозов", "Доклад об открытии смены"]
STEPS_CLOSE = [
    "Наличные", 
    "Безнал", 
    "Общая выручка", 
    "Количество гостей", 
    "Опасные операции", 
    "Блюда за счет заведения", 
    "Расходы на маркетинг", 
    "Расходы на смену", 
    "Доклад о закрытии смены"
]
# Маппинг: название метрики из AI → имя колонки в БД
OPEN_FIELD_MAP = {
    "Стоп лист": "open_stop_list",
    "Приход продуктов": "open_products",
    "Приход хозов": "open_household",
    "Доклад об открытии смены": "open_report",
}

CLOSE_FIELD_MAP = {
    "Наличные": "close_cash",
    "Безнал": "close_card",
    "Общая выручка": "close_revenue",
    "Количество гостей": "close_guests",
    "Опасные операции": "close_dangerous",
    "Блюда за счет заведения": "close_comps",
    "Расходы на маркетинг": "close_marketing",
    "Расходы на смену": "close_expenses",
    "Доклад о закрытии смены": "close_report",
}

AI_PROMPTS = {
    "Открытие": (
        "Ты — внутренний анализатор ресторанной сети. Твоя задача — разобрать отчет об открытии смены "
        "и категоризировать информацию по обязательным метрикам: Стоп лист, Приход продуктов, Приход хозов, Доклад об открытии смены.\n\n"
        "Информация может поступать в виде текста или фотографий (бланков/чеков). Пользователь может перечислить данные списком или прислать фото. Твоя задача — найти упоминания каждой метрики.\n\n"
        "ПРАВИЛА ИЗВЛЕЧЕНИЯ (СТРОГО СОБЛЮДАТЬ):\n"
        "1. Формат ответа — СТРОГИЙ JSON. Ты должен вернуть ТОЛЬКО JSON-объект по следующему шаблону:\n"
        "{\n"
        "  \"Стоп лист\": \"...\",\n"
        "  \"Приход продуктов\": \"...\",\n"
        "  \"Приход хозов\": \"...\",\n"
        "  \"Доклад об открытии смены\": \"...\"\n"
        "}\n"
        "2. Если какой-то метрики (пункта) вообще нет в отчете и о ней ничего не сказано, значение должно быть строго строкой \"Пропущено\".\n"
        "3. Если пункт упомянут, и сказано, что его нет (например, 'стопов нет', 'хозов нет', 'пусто'), значение должно быть строго строкой \"Нет\".\n"
        "4. Значения должны быть сырыми данными из отчета без математических вычислений с твоей стороны.\n"
        "5. Инциденты: Любые поломки или жалобы в докладе выделяй эмодзи 🚨. Если все хорошо, пиши 'Все в порядке'.\n"
        "6. Строгая категоризация: Игнорируй, куда сотрудник вписал товар. Если он вписал 'салфетки' в продукты — перенеси в 'Приход хозов'.\n\n"
    ),
    "Закрытие": (
        "Ты — внутренний финансовый анализатор ресторанной сети. Твоя задача — детально разобрать отчет о закрытии смены по метрикам: "
        "Наличные, Безнал, Общая выручка, Количество гостей, Опасные операции, Блюда за счет заведения, Расходы на маркетинг, Расходы на смену, Доклад о закрытии смены.\n\n"
        "ИНСТРУКЦИЯ ПО РАСПОЗНАВАНИЮ ФОТО (ЧЕКИ И БЛАНК А4):\n"
        "КРИТИЧЕСКИ ВАЖНО: 8 главных метрик находятся на прикрепленных фотографиях (Z-отчеты, чеки, рукописный бланк А4).\n"
        "1. Приоритет данных: ДАННЫЕ С ФОТОГРАФИЙ ВСЕГДА ВАЖНЕЕ ТЕКСТА. Если пользователь написал одно, а на чеке другое — верь чеку.\n"
        "2. Карта поиска по чеку:\n"
        "   - Опасные операции: ищи строго по ключу '037 Опасные операции'.\n"
        "   - Блюда за счет заведения: ищи по ключу '048 Итого по смене' -> строка 'ИТОГО <Комплименты>'.\n"
        "   - Расходы на маркетинг: ищи по ключу '048 Итого по смене' -> строка 'ИТОГО <Маркетинг>'.\n"
        "3. Рукописный текст: Количество гостей и 'Расходы на смену' ищи на рукописном бланке А4. Если почерк неразборчив или цифра смазана, выводи: '[ЧИСЛО] (Требует проверки почерка)'.\n\n"
        "ПРАВИЛА ИЗВЛЕЧЕНИЯ И АУДИТА (СТРОГО СОБЛЮДАТЬ):\n"
        "1. Формат ответа — СТРОГИЙ JSON. Ты должен вернуть ТОЛЬКО JSON-объект по следующему шаблону:\n"
        "{\n"
        "  \"Наличные\": \"...\",\n"
        "  \"Безнал\": \"...\",\n"
        "  \"Общая выручка\": \"...\",\n"
        "  \"Количество гостей\": \"...\",\n"
        "  \"Опасные операции\": \"...\",\n"
        "  \"Блюда за счет заведения\": \"...\",\n"
        "  \"Расходы на маркетинг\": \"...\",\n"
        "  \"Расходы на смену\": \"...\",\n"
        "  \"Доклад о закрытии смены\": \"...\"\n"
        "}\n"
        "2. Если про метрику ничего не сказано и её нет на чеке, пиши строку \"Пропущено\".\n"
        "3. Если написано/указано, что метрики нет (например, 'опасных операций нет', или '0' гостей), пиши строку \"Нет\" (или 0 для гостей/выручки).\n"
        "4. Финансовый аудит ОТКЛЮЧЕН: не проверяй формулу выручки, просто извлекай сырые цифры как они есть, без математики.\n"
        "5. Стандартизация: Приводи сленг и названия к номенклатурному виду.\n"
        "6. Инциденты: Поломки в докладе выделяй 🚨. Если проблем нет — 'Все в порядке'.\n\n"
    )
}

FOLLOWUP_PROMPT = (
    "Ты — анализатор ресторанной отчетности. Пользователь досылает информацию для конкретного пункта: '{metric_name}'.\n"
    "Определи статус ответа:\n"
    "1. Данные — если предоставлена конкретная информация по пункту. ПОМНИ: пользователь может отправить просто одно число (например, '1', '1488', '5000'), название продукта (например, 'молоко', 'салфетки') или короткую фразу. Любые числа или короткие конкретные ответы считаются предоставленными данными.\n"
    "2. Явно отсутствует — если пользователь написал четкий отказ (например, 'нет', 'нету', 'не было', 'отсутствует', 'ноль', '0').\n\n"
    "Выдай ответ СТРОГО В ФОРМАТЕ JSON по шаблону:\n"
    "{\n"
    "  \"status\": \"Данные или Явно отсутствует\",\n"
    "  \"value\": \"Текст значения без звездочек и скобок. Если статус 'Явно отсутствует' — напиши СТРОГО слово: Нет. Если метрика 'Количество гостей' и данных нет — напиши: Информация отсутствует\"\n"
    "}\n"
)
