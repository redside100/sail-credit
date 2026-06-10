from dataclasses import dataclass

import discord
from abc import ABC, abstractmethod
from typing import Callable, Dict, Any, List, Literal, Optional

CasinoGameAlias = Literal["crash"]

@dataclass
class DegenerateGambler:
    user_id: int
    bet_amount: int

class CasinoGame(ABC):
    interaction: discord.Interaction
    name: str
    canonical_name: str
    description: str
    lobby_time: int
    embed_details: Dict[str, Any]
    finish_callback: Optional[Callable] = None

    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction

    @abstractmethod
    async def start(self, members: List[DegenerateGambler]):
        pass

    @abstractmethod
    async def finish(self):
        pass