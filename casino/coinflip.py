import asyncio
from dataclasses import dataclass, field, asdict
import json
import random

import discord
from casino.casino import DegenerateGambler
from casino.models import BetConfig, CasinoGame
from typing import Any, Dict, List, Literal, Optional

from util import create_embed


@dataclass
class CoinFlipGameState:
    members: List[DegenerateGambler] = field(default_factory=list)
    outcome: Optional[Literal["heads", "tails"]] = None
    winner: Optional[DegenerateGambler] = None
    win_multiplier: float = 1.98

    def to_dict(self):
        return {
            "members": [member.user_id for member in self.members],
            "outcome": self.outcome,
            "winner": self.winner.user_id if self.winner else None,
            "win_multiplier": self.win_multiplier,
        }


class Coinflip(CasinoGame):
    def __init__(
        self,
        interaction: discord.Interaction,
        host_bet: int = 10,
        host_choice: Literal["heads", "tails"] = "heads",
    ):
        super().__init__(interaction)
        self.name = "🪙 Sail Coinflip"
        self.canonical_name = "COINFLIP"
        self.description = f"Join a 1v1 coinflip against <@{interaction.user.id}>! The winner will receive **1.98x** their bet."
        self.bet_config = BetConfig(bet_type="fixed", fixed_bet_amount=host_bet)
        self.lobby_time = 15
        self.embed_details = {
            "color": discord.Colour(0xFFD700),
            "image_url": "https://redside.tor1.cdn.digitaloceanspaces.com/public/assets/sailcoinflip.png",
        }
        self.game_state = CoinFlipGameState()
        self.game_state.members.append(
            DegenerateGambler(interaction.user.id, host_bet, {"choice": host_choice})
        )

    def render_player_data(self, game_data: Dict[str, Any]) -> Optional[str]:
        choice = game_data.get("choice")
        if choice:
            return f"**({choice})**"

    async def start(self, members: List[DegenerateGambler]) -> None:
        if len(members) < 2:
            await self.interaction.edit_original_response(
                embed=create_embed(
                    "No opponent found!",
                    color=discord.Colour.red(),
                ),
                view=None,
            )
            return

        random_outcome = random.choice(["heads", "tails"])
        self.game_state.outcome = random_outcome
        self.game_state.winner = random.choice(members)

        await self.interaction.edit_original_response(
            embed=self.generate_embed(), view=None
        )
        await self.finish()

    async def finish(self) -> None:
        if self.finish_callback:
            await self.finish_callback()

    def get_metadata(self) -> Dict:
        return self.game_state.to_dict()
