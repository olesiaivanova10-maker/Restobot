import asyncio
from services.db import check_all_shifts_status
from core.config import LIST_MAPPING

async def main():
    est_keys = list(LIST_MAPPING.keys())
    statuses = await check_all_shifts_status(est_keys)
    for k, v in statuses.items():
        print(f"{k}: {v}")

asyncio.run(main())
