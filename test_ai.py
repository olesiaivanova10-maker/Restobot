import asyncio
from services.ai import get_parsed_report
from core.config import AI_PROMPTS
from core.logger import logger

async def test():
    try:
        # Just send a simple request
        await get_parsed_report("Открытие", AI_PROMPTS["Открытие"], [{"type": "text", "text": "Test"}])
        print("Success")
    except Exception as e:
        print(f"Failed: {type(e)} {e}")

asyncio.run(test())
