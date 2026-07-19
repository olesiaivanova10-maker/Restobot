from datetime import timedelta
from sqlalchemy import select, delete
import asyncio

from core.database import AsyncSessionLocal, AsyncSessionLocalTest
from models.shift import Shift
from core.logger import logger
from core.config import OPEN_FIELD_MAP, CLOSE_FIELD_MAP, now_vlad

def get_session(is_test: bool = False):
    return AsyncSessionLocalTest() if is_test else AsyncSessionLocal()

async def get_or_create_shift(date_str: str, establishment: str, is_test: bool = False) -> Shift:
    async with get_session(is_test) as session:
        result = await session.execute(
            select(Shift).where(Shift.date_str == date_str, Shift.establishment == establishment)
        )
        # Use first() instead of scalar_one_or_none() to prevent crashes on duplicates
        shifts = result.scalars().all()
        
        if len(shifts) > 1:
            # Cleanup duplicates if they somehow exist
            shift = shifts[0]
            for extra_shift in shifts[1:]:
                await session.delete(extra_shift)
            await session.commit()
        elif len(shifts) == 1:
            shift = shifts[0]
        else:
            shift = None

        if not shift:
            shift = Shift(date_str=date_str, establishment=establishment)
            session.add(shift)
            await session.commit()
            await session.refresh(shift)
        return shift


async def get_shift_by_date(date_str: str, establishment: str, is_test: bool = False) -> Shift:
    async with get_session(is_test) as session:
        res = await session.execute(
            select(Shift).where(Shift.date_str == date_str, Shift.establishment == establishment)
        )
        # Use first to avoid duplicate exceptions
        return res.scalars().first()

async def check_all_shifts_status(sheet_names: list[str], is_test: bool = False) -> dict:
    current_date = now_vlad().strftime("%d.%m")
    target_date_close = (now_vlad() - timedelta(days=1)).strftime("%d.%m")
    
    statuses = {}
    async with get_session(is_test) as session:
        for est in sheet_names:
            res_open = await session.execute(select(Shift).where(Shift.date_str == current_date, Shift.establishment == est))
            shift_open = res_open.scalars().first()
            is_opened_today = shift_open.is_opened if shift_open else False
            
            res_close = await session.execute(select(Shift).where(Shift.date_str == target_date_close, Shift.establishment == est))
            shift_close = res_close.scalars().first()
            is_opened_yesterday = shift_close.is_opened if shift_close else False
            is_closed_yesterday = shift_close.is_closed if shift_close else False
            
            statuses[est] = {
                "is_opened_today": is_opened_today,
                "is_opened_yesterday": is_opened_yesterday,
                "is_closed_yesterday": is_closed_yesterday
            }
    return statuses

async def check_shift_open(establishment: str, is_test: bool = False) -> bool:
    current_date = now_vlad().strftime("%d.%m")
    async with get_session(is_test) as session:
        res = await session.execute(select(Shift).where(Shift.date_str == current_date, Shift.establishment == establishment))
        shift = res.scalars().first()
        return shift.is_opened if shift else False

async def check_shift_closed(establishment: str, is_test: bool = False) -> bool:
    target_date_close = (now_vlad() - timedelta(days=1)).strftime("%d.%m")
    async with get_session(is_test) as session:
        res = await session.execute(select(Shift).where(Shift.date_str == target_date_close, Shift.establishment == establishment))
        shift = res.scalars().first()
        return shift.is_closed if shift else False

async def mark_shift_open(establishment: str, data: dict = None, is_test: bool = False, target_date: str = None):
    current_date = target_date if target_date else now_vlad().strftime("%d.%m")
    current_time = now_vlad().strftime("%H:%M")
    shift = await get_or_create_shift(current_date, establishment, is_test)
    async with get_session(is_test) as session:
        shift = await session.merge(shift)
        shift.is_opened = True
        shift.open_time = current_time
        
        if data:
            for metric_name, db_col in OPEN_FIELD_MAP.items():
                val = data.get(metric_name, "")
                setattr(shift, db_col, str(val) if val is not None else "")
        
        await session.commit()

async def mark_shift_closed(establishment: str, data: dict = None, is_test: bool = False):
    target_date_close = (now_vlad() - timedelta(days=1)).strftime("%d.%m")
    current_time = now_vlad().strftime("%H:%M")
    shift = await get_or_create_shift(target_date_close, establishment, is_test)
    async with get_session(is_test) as session:
        shift = await session.merge(shift)
        shift.is_closed = True
        shift.close_time = current_time
        
        if data:
            for metric_name, db_col in CLOSE_FIELD_MAP.items():
                val = data.get(metric_name, "")
                setattr(shift, db_col, str(val) if val is not None else "")
        
        await session.commit()

async def get_all_shifts(is_test: bool = False):
    async with get_session(is_test) as session:
        res = await session.execute(select(Shift))
        return res.scalars().all()

async def clear_all_shifts(is_test: bool = False):
    async with get_session(is_test) as session:
        await session.execute(delete(Shift))
        await session.commit()
