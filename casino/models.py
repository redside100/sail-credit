from pydantic import BaseModel

from abc import ABC, abstractmethod
from typing import Callable, Dict, Any, List, Literal, Optional

from models import SerializableMessage

CasinoGameAlias = Literal["crash", "coinflip", "jackpot"]


class DegenerateGambler(BaseModel):
    user_id: int
    bet_amount: int
    avatar_url: str

    def __hash__(self):
        return self.user_id


class BetConfig(BaseModel):
    bet_type: Literal["freeform", "fixed"]
    fixed_bet_amount: Optional[int] = None


class CasinoGame(ABC):
    name: str
    canonical_name: str
    description: str
    lobby_time: int
    embed_details: Dict[str, Any]
    message: Optional[SerializableMessage] = None
    finish_callback: Optional[Callable] = None
    bet_config: BetConfig
    max_size: Optional[int] = None

    def __init__(self, message: Optional[SerializableMessage] = None):
        self.message = message

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
