import asyncio
from dataclasses import dataclass, field
import random

import discord
from casino.flip_generator import create_coinflip_gif
from casino.models import BetConfig, CasinoGame, DegenerateGambler
from typing import Dict, List, Literal, Optional

import db
from util import create_embed


@dataclass
class CoinFlipGambler(DegenerateGambler):
    choice: Literal["heads", "tails"]


@dataclass
class CoinFlipGameState:
    members: List[CoinFlipGambler] = field(default_factory=list)
    outcome: Optional[Literal["heads", "tails"]] = None
    win_multiplier: float = 1.98

    def to_dict(self):
        return {
            "members": [
                {
                    "id": member.user_id,
                    "choice": member.choice,
                    "bet_amount": member.bet_amount,
                }
                for member in self.members
            ],
            "outcome": self.outcome,
            "win_multiplier": self.win_multiplier,
        }


class Coinflip(CasinoGame):

    HEADS_URL = (
        "https://redside.tor1.cdn.digitaloceanspaces.com/public/assets/sailheads.png"
    )
    TAILS_URL = (
        "https://redside.tor1.cdn.digitaloceanspaces.com/public/assets/sailtails.png"
    )

    def __init__(
        self,
        interaction: discord.Interaction,
        host_bet: int = 10,
        host_choice: Literal["heads", "tails"] = "heads",
    ):
        super().__init__(interaction)
        self.name = "🪙 Sail Coinflip"
        self.canonical_name = "COINFLIP"

        self.game_state = CoinFlipGameState()
        self.description = f"Join a 1v1 coinflip against <@{interaction.user.id}>!\n\nThe winner receives **{int(host_bet * self.game_state.win_multiplier)} SSC**."
        self.bet_config = BetConfig(bet_type="fixed", fixed_bet_amount=host_bet)
        self.lobby_time = 15
        self.embed_details = {
            "color": discord.Colour(0xFFD700),
            "image_url": "https://redside.tor1.cdn.digitaloceanspaces.com/public/assets/sailcoinflip.png",
        }
        self.host_choice = host_choice
        self.max_size = 2

    async def flip(self):

        winner = random.choice(self.game_state.members)
        loser = [m for m in self.game_state.members if m.user_id != winner.user_id][0]
        self.game_state.outcome = winner.choice
        win_amount = int(winner.bet_amount * self.game_state.win_multiplier)

        wait_time_ms = 3000
        label_map = {"heads": "H", "tails": "T"}
        front_label = label_map[self.game_state.members[0].choice]
        back_label = label_map[self.game_state.members[1].choice]
        gif_bytes = await create_coinflip_gif(
            self.game_state.members[0].avatar_url,
            self.game_state.members[1].avatar_url,
            front_label=front_label,
            back_label=back_label,
            result="front" if label_map[winner.choice] == front_label else "back",
            total_ms=wait_time_ms,
            size=192,
        )

        description = ""
        for member in self.game_state.members:
            description += f"- <@{member.user_id}> **({member.bet_amount} SSC)** **({member.choice})**\n"

        await self.interaction.edit_original_response(
            attachments=[discord.File(gif_bytes, filename="coinflip.gif")],
            embed=create_embed(
                description,
                "Flipping...",
                image_url="attachment://coinflip.gif",
                color=self.embed_details["color"],
            ),
            view=None,
        )

        await asyncio.sleep(wait_time_ms / 1000)

        winner_data = await db.get_user(winner.user_id)
        ssc = winner_data["sail_credit"]
        await db.change_and_log_sail_credit(
            winner.user_id, -1, -1, -1, ssc, ssc + win_amount
        )

        await self.interaction.edit_original_response(
            embed=create_embed(
                f"<@{winner.user_id}> wins! **(+{win_amount} SSC)**\n\nBetter luck next time, <@{loser.user_id}>.",
                f"{winner.choice.capitalize()}!",
                image_url=winner.avatar_url,
                color=self.embed_details["color"],
            ),
            view=None,
            attachments=[],
        )

    async def start(self, members: List[DegenerateGambler]) -> None:
        if len(members) == 1:
            await self.interaction.edit_original_response(
                embed=create_embed(
                    f"<@{members[0].user_id}> No opponent found!",
                    image_url=self.embed_details["image_url"],
                    color=discord.Colour.red(),
                ),
                view=None,
            )
            user_data = await db.get_user(members[0].user_id)
            ssc = user_data["sail_credit"]
            await db.change_and_log_sail_credit(
                members[0].user_id, -1, -1, -1, ssc, ssc + members[0].bet_amount
            )
            return

        opponent_choice = "heads" if self.host_choice == "tails" else "tails"
        self.game_state.members = [
            CoinFlipGambler(
                user_id=members[0].user_id,
                bet_amount=members[0].bet_amount,
                choice=self.host_choice,
                avatar_url=members[0].avatar_url,
            ),
            CoinFlipGambler(
                user_id=members[1].user_id,
                bet_amount=members[1].bet_amount,
                choice=opponent_choice,
                avatar_url=members[1].avatar_url,
            ),
        ]

        await self.flip()
        await self.finish()

    async def finish(self) -> None:
        if self.finish_callback:
            await self.finish_callback()

    def get_metadata(self) -> Dict:
        return self.game_state.to_dict()
