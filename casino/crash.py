import asyncio
from dataclasses import dataclass, field

import discord

from casino.casino import DegenerateGambler
from casino.models import CasinoGame
from typing import Dict, List, Callable, Tuple

from casino.util import get_log_source
import db
from util import create_embed, user_interaction_callback

@dataclass
class CrashGameState:
    members: List[DegenerateGambler] = field(default_factory=list)
    cash_outs: Dict[DegenerateGambler, float] = field(default_factory=dict)
    finished: bool = False
    current_multiplier: float = 1

class CrashView(discord.ui.View):
    def __init__(self, crash: 'Crash'):
        super().__init__(timeout=None)
        cash_out_button = discord.ui.Button(label="Cashout", style=discord.ButtonStyle.blurple)
        cash_out_button.callback = self.cash_out
        self.add_item(cash_out_button)
        self.crash = crash
    
    @user_interaction_callback()
    async def cash_out(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        crash_member = None
        for member in self.crash.game_state.members:
            if member.user_id == user_id:
                crash_member = member

        if not crash_member:
            await interaction.response.defer()
            return
        
        if user_id in {member.user_id for member in self.crash.game_state.cash_outs}:
            await interaction.response.defer()
            return
        
        if self.crash.game_state.finished:
            await interaction.response.defer()
            return
        

        self.crash.game_state.cash_outs[crash_member] = self.crash.game_state.current_multiplier
        cash_out_amount = int(crash_member.bet_amount * self.crash.game_state.current_multiplier)

        user = interaction.data["user_data"] # pyright: ignore
        source = source = get_log_source(self.crash.canonical_name, "DEBIT")
        await db.change_and_log_sail_credit(user_id, -1, -1, -1, user["sail_credit"], user["sail_credit"] + cash_out_amount, source)

        # Avoid sending messages to respect rate limits
        await interaction.response.defer()


class Crash(CasinoGame):


    def __init__(self, interaction: discord.Interaction):
        super().__init__(interaction)
        self.name = "🚀 Sail Crash"
        self.canonical_name = "CRASH"
        self.description = "Bet your SSC and cash out before the chart crashes!"
        self.lobby_time = 30
        self.embed_details = {
            "color": discord.Colour(0x59ff00),
            "image_url": "https://redside.tor1.cdn.digitaloceanspaces.com/public/assets/sailcrash.png"
        }
        self.game_state = CrashGameState()

    def generate_embed(self):
        content = "Current multiplier at " if not self.game_state.finished else "Crashed at "
        content += f"**{round(self.game_state.current_multiplier, 2)}x**\n\n"
        for member in sorted(self.game_state.members, key=lambda m: m.bet_amount, reverse=True):
            content += f"- <@{member.user_id}> **({member.bet_amount} SSC)**"
            cash_out_multi = self.game_state.cash_outs.get(member)
            if cash_out_multi is not None:
                amount = int(cash_out_multi * member.bet_amount)
                content += f" - Cash out at {round(cash_out_multi, 2)}x **({amount} SSC)**"
            elif self.game_state.finished:
                content += " - 🪦"
            content += "\n"

        embed_contents = {"message": content, "title": self.name, "color": self.embed_details["color"] if not self.game_state.finished else discord.Colour(0xf54242)}

        return create_embed(**embed_contents)

    async def start(self, members: List[DegenerateGambler]) -> None:
        self.game_state.members = members
        # No-op, just sleep 1s and refund bets
        await self.interaction.edit_original_response(embed=self.generate_embed(), view=CrashView(self), content="Placeholder chart content")
        for _ in range(10):
            self.game_state.current_multiplier += 0.1
            await asyncio.sleep(1.1)
            await self.interaction.edit_original_response(embed=self.generate_embed())

    
        self.game_state.finished = True
        await self.interaction.edit_original_response(embed=self.generate_embed(), content="Finished! Losers", view=None)
        await self.finish()
    
    async def finish(self) -> None:
        if self.finish_callback:
            await self.finish_callback()