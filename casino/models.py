from dataclasses import dataclass

import discord
from abc import ABC, abstractmethod
from typing import Callable, Dict, Any, List, Literal, Optional

CasinoGameAlias = Literal["crash"]


@dataclass
class DegenerateGambler:
    user_id: int
    bet_amount: int
    avatar_url: str

    def __hash__(self):
        return self.user_id


@dataclass
class BetConfig:
    bet_type: Literal["freeform", "fixed"]
    fixed_bet_amount: int = None


class CasinoGame(ABC):
    interaction: discord.Interaction
    name: str
    canonical_name: str
    description: str
    lobby_time: int
    embed_details: Dict[str, Any]
    finish_callback: Optional[Callable] = None
    bet_config: BetConfig
    max_size: Optional[int] = None

    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction

    @abstractmethod
    async def start(self, members: List[DegenerateGambler]):
        pass

    @abstractmethod
    async def finish(self):
        pass

    @abstractmethod
    def get_metadata(self) -> Dict:
        pass

    def player_descriptor(
        self, member: DegenerateGambler, members: List[DegenerateGambler]
    ) -> str:
        return f"<@{member.user_id}> **({member.bet_amount} SSC)**"
