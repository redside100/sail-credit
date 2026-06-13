from typing import Literal
import random


def get_log_source(game: str, log_type: Literal["DEBIT", "CREDIT"]):
    return game.replace(" ", "_").upper() + "_" + log_type


def get_crash_point():
    insta_crash_chance = 0.01
    if random.uniform(0, 1) < insta_crash_chance:
        return 1.01

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
