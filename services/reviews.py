from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import aiosqlite

from core.config import VLZ_TZ
from core.database import DATA_DIR

REVIEWS_DB = Path(DATA_DIR) / "reviews.db"


async def init_reviews_db() -> None:
    async with aiosqlite.connect(REVIEWS_DB) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                venue TEXT NOT NULL,
                body TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                prompt_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (chat_id, prompt_id)
            )
        """)
        await conn.commit()


async def save_review(venue: str, body: str, chat_id: int, prompt_id: int) -> None:
    async with aiosqlite.connect(REVIEWS_DB) as conn:
        await conn.execute(
            """
            INSERT INTO reviews (venue, body, chat_id, prompt_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (chat_id, prompt_id) DO NOTHING
            """,
            (venue, body, chat_id, prompt_id),
        )
        await conn.commit()


async def count_reviews_by_venue(day: date) -> dict[str, int]:
    start = datetime.combine(day, time.min, VLZ_TZ).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, VLZ_TZ).astimezone(timezone.utc)
    async with aiosqlite.connect(REVIEWS_DB) as conn:
        async with conn.execute(
            """
            SELECT venue, COUNT(*) FROM reviews
            WHERE created_at >= ? AND created_at < ?
            GROUP BY venue
            """,
            (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")),
        ) as cursor:
            return dict(await cursor.fetchall())
