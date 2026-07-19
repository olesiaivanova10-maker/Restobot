from sqlalchemy import Column, Integer, String, Boolean
from core.database import Base

class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True, index=True)
    date_str = Column(String, index=True)       # "29.06"
    establishment = Column(String, index=True)   # "Киса бар"

    # ── ОТКРЫТИЕ ──
    is_opened = Column(Boolean, default=False)
    open_time = Column(String, default="")        # "14:30"
    open_stop_list = Column(String, default="")    # Стоп лист
    open_products = Column(String, default="")     # Приход продуктов
    open_household = Column(String, default="")    # Приход хозов
    open_report = Column(String, default="")       # Доклад об открытии смены

    # ── ЗАКРЫТИЕ ──
    is_closed = Column(Boolean, default=False)
    close_time = Column(String, default="")        # "02:15"
    close_cash = Column(String, default="")        # Наличные
    close_card = Column(String, default="")        # Безнал
    close_revenue = Column(String, default="")     # Общая выручка
    close_guests = Column(String, default="")      # Количество гостей
    close_dangerous = Column(String, default="")   # Опасные операции
    close_comps = Column(String, default="")       # Блюда за счет заведения
    close_marketing = Column(String, default="")   # Расходы на маркетинг
    close_expenses = Column(String, default="")    # Расходы на смену
    close_report = Column(String, default="")      # Доклад о закрытии смены
