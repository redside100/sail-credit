import asyncio
import io
from typing import Literal
import random

from PIL.Image import Image
import aiohttp


def get_log_source(game: str, log_type: Literal["DEBIT", "CREDIT"]):
    return game.replace(" ", "_").upper() + "_" + log_type


def get_crash_point():
    insta_crash_chance = 0.02
    if random.uniform(0, 1) < insta_crash_chance:
        return 1.00

    r = max(random.uniform(0, 1), 0.001)
    clamped = min(max(1 / r, 1.001), 9999)
    return clamped


def mult_to_emoji(mult: float):
    if mult >= 1000:
        return "👑"
    elif mult >= 100:
        return "💎"
    elif mult >= 10:
        return "🔥"
    elif mult >= 2:
        return "📈"
    elif mult >= 1.01:
        return "📉"
    else:
        return "🪦"


async def fetch_image(
    session: aiohttp.ClientSession, url: str, max_retries: int = 3
) -> Image.Image:
    for attempt in range(max_retries + 1):
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                content = await response.read()
            return Image.open(io.BytesIO(content)).convert("RGBA")
        except (aiohttp.ClientResponseError, aiohttp.ServerTimeoutError) as e:
            if attempt == max_retries:
                raise
            wait = 0.2 * (2**attempt)
            await asyncio.sleep(wait)
