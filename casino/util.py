from typing import Literal


def get_log_source(game: str, log_type: Literal["DEBIT", "CREDIT"]):
    return game.replace(" ", "_").upper() + "_" + log_type
