import asyncio

import discord

from casino.casino import DegenerateGambler
from casino.models import CasinoGame
from typing import List, Callable

from casino.util import get_log_source
import db

class Crash(CasinoGame):


    def __init__(self, interaction: discord.Interaction):
        super().__init__(interaction)
        self.name = "🚀 Sail Crash"
        self.canonical_name = "CRASH"
        self.description = "Bet your SSC and cash out before the chart crashes!"
        self.lobby_time = 30
        self.embed_details = {
            "color": discord.Colour(0x59ff00),
            "image_url": ""
        }

    async def start(self, members: List[DegenerateGambler]) -> None:

        # No-op, just sleep 1s and refund bets
        await self.interaction.edit_original_response(embed=None, view=None, content="Test crash")
        await asyncio.sleep(1)
        for member in members:
            source = get_log_source(self.canonical_name, "DEBIT")
            user = await db.get_user(member.user_id)
            if not user:
                continue

            await db.change_and_log_sail_credit(member.user_id, -1, -1, -1, user["sail_credit"], user["sail_credit"] + member.bet_amount, source)

        await self.interaction.edit_original_response(content="Finished!")
        await self.finish()
    
    async def finish(self) -> None:
        if self.finish_callback:
            await self.finish_callback()