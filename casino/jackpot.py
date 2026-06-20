import asyncio
from dataclasses import dataclass, field
import random

import discord
from typing import Dict, List, Optional

from casino.models import BetConfig, CasinoGame, DegenerateGambler
from casino.spin_generator import Player, create_jackpot_gif
from casino.util import get_log_source
import db
from util import create_embed


@dataclass
class JackpotGameState:
    members: List[DegenerateGambler] = field(default_factory=list)
    winner: Optional[DegenerateGambler] = None
    total_multiplier: float = 0.98

    def to_dict(self):
        return {
            "members": [
                {
                    "id": member.user_id,
                    "bet_amount": member.bet_amount,
                }
                for member in self.members
            ],
            "winner": self.winner.user_id if self.winner else None,
            "total_multiplier": self.total_multiplier,
        }


class Jackpot(CasinoGame):
    def __init__(
        self,
        interaction: discord.Interaction,
    ):
        super().__init__(interaction)
        self.name = "🎰 Sail Jackpot"
        self.canonical_name = "JACKPOT"

        self.game_state = JackpotGameState()
        self.description = f"Join the pot and try your luck, winner takes all!\nThe more you bet, the better your odds."
        self.bet_config = BetConfig(bet_type="freeform")
        self.lobby_time = 30
        self.embed_details = {
            "color": discord.Colour(0x1DA1F2),
            "image_url": "https://redside.tor1.cdn.digitaloceanspaces.com/public/assets/sailjackpot.png",
        }

    async def roll(self):
        total_bet_amount = sum(member.bet_amount for member in self.game_state.members)
        if total_bet_amount == 0:
            # Is this even possible?
            return

        winner = random.choices(
            self.game_state.members,
            weights=[member.bet_amount for member in self.game_state.members],
        )[0]
        winning_amount = max(
            winner.bet_amount, int(total_bet_amount * self.game_state.total_multiplier)
        )
        winning_chance = format(winner.bet_amount / total_bet_amount * 100, ".2f")
        self.game_state.winner = winner

        wait_time_ms = 4500
        jackpot_players = [
            Player(url=member.avatar_url, weight=member.bet_amount / total_bet_amount)
            for member in self.game_state.members
        ]
        gif_bytes = await create_jackpot_gif(
            players=jackpot_players,
            winner_url=winner.avatar_url,
            avatar_size=192,
            tile_w=192,
            canvas_tiles=5,
            total_ms=wait_time_ms - 500,
        )

        description = ""
        for member in self.game_state.members:
            member_chance = format(member.bet_amount / total_bet_amount * 100, ".2f")
            description += f"- <@{member.user_id}> **({member.bet_amount} SSC)** **({member_chance}%)**\n"

        await self.interaction.edit_original_response(
            attachments=[discord.File(gif_bytes, filename="jackpot.gif")],
            embed=create_embed(
                description,
                "🎰 Rolling...",
                image_url="attachment://jackpot.gif",
                color=self.embed_details["color"],
            ),
            view=None,
        )

        await asyncio.sleep(wait_time_ms / 1000)

        winner_data = await db.get_user(winner.user_id)
        await db.change_and_log_sail_credit(
            winner.user_id,
            -1,
            -1,
            -1,
            winner_data["sail_credit"],
            winner_data["sail_credit"] + winning_amount,
            source=get_log_source(self.canonical_name, "CREDIT"),
        )

        end_description = ""
        for member in self.game_state.members:
            if member.user_id != winner.user_id:
                member_chance = format(
                    member.bet_amount / total_bet_amount * 100, ".2f"
                )
                end_description += f"- <@{member.user_id}> **(-{member.bet_amount} SSC)** **({member_chance}%)**\n"

        await self.interaction.edit_original_response(
            embed=create_embed(
                f"🏆 <@{winner.user_id}> won with a **{winning_chance}%** chance! **(+{winning_amount} SSC)**\n\n{end_description}",
                self.name,
                image_url=winner.avatar_url,
                color=self.embed_details["color"],
            ),
            view=None,
            attachments=[],
        )

    async def start(self, members: List[DegenerateGambler]) -> None:
        if len(members) < 2:
            if members:
                user_data = await db.get_user(members[0].user_id)
                ssc = user_data["sail_credit"]
                await db.change_and_log_sail_credit(
                    members[0].user_id,
                    -1,
                    -1,
                    -1,
                    ssc,
                    ssc + members[0].bet_amount,
                    source=get_log_source(self.canonical_name, "CREDIT"),
                )

            await self.interaction.edit_original_response(
                embed=create_embed(
                    f"Not enough players! All bets were refunded.",
                    image_url=self.embed_details["image_url"],
                    color=discord.Colour.red(),
                ),
                view=None,
            )
            await self.finish()
            return

        self.game_state.members = members

        await self.roll()
        await self.finish()

    def player_descriptor(
        self, member: DegenerateGambler, members: List[DegenerateGambler]
    ) -> str:
        total_bet_amount = sum(m.bet_amount for m in members)
        member_chance = (
            format(member.bet_amount / total_bet_amount * 100, ".2f")
            if total_bet_amount > 0
            else "0.00"
        )
        return (
            f"<@{member.user_id}> **({member.bet_amount} SSC)** **({member_chance}%)**"
        )

    async def finish(self) -> None:
        if self.finish_callback:
            await self.finish_callback()

    def get_metadata(self) -> Dict:
        return self.game_state.to_dict()
