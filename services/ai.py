import json
import base64
from typing import Dict, Tuple
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import PROXYAPI_KEY, AI_BASE_URL, AI_MODEL

ai_client = AsyncOpenAI(api_key=PROXYAPI_KEY, base_url=AI_BASE_URL)

def clean_json_markdown(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def get_parsed_report(report_type: str, system_prompt: str, user_contents: list) -> Dict[str, dict]:
    # JSON is enforced in the prompt from config.py
    
    response = await ai_client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_contents}
        ],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    
    content = response.choices[0].message.content
    content = clean_json_markdown(content)
    try:
        data = json.loads(content)
        return data
    except json.JSONDecodeError:
        # Fallback to old parsing if it somehow fails JSON
        from core.logger import logger
        logger.error("AI returned invalid JSON. Trying old parser.")
        return parse_ai_blocks_fallback(content)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def get_parsed_followup(system_prompt: str, user_contents: list) -> Tuple[str, str]:
    json_prompt = system_prompt + "\n\nОТВЕТЬ СТРОГО В ФОРМАТЕ JSON: {\"status\": \"...\", \"value\": \"...\"}. Не пиши ничего кроме JSON."
    response = await ai_client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": json_prompt},
            {"role": "user", "content": user_contents}
        ],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    content = response.choices[0].message.content
    content = clean_json_markdown(content)
    try:
        data = json.loads(content)
        return data.get("status", "Данные"), data.get("value", "")
    except json.JSONDecodeError:
        from core.logger import logger
        logger.error("AI returned invalid JSON in followup.")
        return "Данные", content.strip()

def parse_ai_blocks_fallback(text: str) -> dict:
    result = {}
    blocks = text.split("---")
    for block in blocks:
        if not block.strip(): continue
        lines = block.strip().split("\n")
        metric, status, val_lines = None, None, []
        for line in lines:
            if line.startswith("METRIC:"): metric = line.replace("METRIC:", "").strip()
            elif line.startswith("STATUS:"): status = line.replace("STATUS:", "").strip()
            elif line.startswith("VALUE:"): val_lines.append(line.replace("VALUE:", "").strip())
            elif metric and status: val_lines.append(line)
        if metric:
            result[metric] = {"status": status if status else "Пропущено", "value": "\n".join(val_lines).strip()}
    return result

def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


