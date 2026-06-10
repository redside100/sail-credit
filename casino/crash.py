import asyncio
from dataclasses import dataclass, field, asdict
import json

import discord
from casino.casino import DegenerateGambler
from casino.graph import render_graph
from casino.models import CasinoGame
from typing import Dict, List

from casino.util import get_crash_point, get_log_source
import db
from util import create_embed, user_interaction_callback
import time


@dataclass
class CrashGameState:
    members: List[DegenerateGambler] = field(default_factory=list)
    cash_outs: Dict[DegenerateGambler, float] = field(default_factory=dict)
    finished: bool = False
    current_multiplier: float = 1

    def to_dict(self):
        return {
            "members": [member.user_id for member in self.members],
            "cash_outs": {
                dg.user_id: {
                    "bet_amount": dg.bet_amount,
                    "multiplier": mul
                } for dg, mul in self.cash_outs.items()
            },
            "crash_multiplier": self.current_multiplier
        }


class CrashView(discord.ui.View):
    def __init__(self, crash: "Crash"):
        super().__init__(timeout=None)
        cash_out_button = discord.ui.Button(
            label="Cash out", style=discord.ButtonStyle.green
        )
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

        self.crash.game_state.cash_outs[crash_member] = (
            self.crash.game_state.current_multiplier
        )
        cash_out_amount = int(
            crash_member.bet_amount * self.crash.game_state.current_multiplier
        )

        user = interaction.data["user_data"]  # pyright: ignore
        source = source = get_log_source(self.crash.canonical_name, "DEBIT")
        await db.change_and_log_sail_credit(
            user_id,
            -1,
            -1,
            -1,
            user["sail_credit"],
            user["sail_credit"] + cash_out_amount,
            source,
        )

        # Avoid sending messages to respect rate limits
        await interaction.response.defer()


class Crash(CasinoGame):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(interaction)
        self.name = "🚀 Sail Crash"
        self.canonical_name = "CRASH"
        self.description = "Bet your SSC and cash out before the chart crashes!"
        self.lobby_time = 15
        self.embed_details = {
            "color": discord.Colour(0x59FF00),
            "image_url": "https://redside.tor1.cdn.digitaloceanspaces.com/public/assets/sailcrash.png",
        }
        self.game_state = CrashGameState()

    def generate_embed(self):
        content = (
            "Current multiplier at " if not self.game_state.finished else "Crashed at "
        )
        content += (
            f"**{format(round(self.game_state.current_multiplier, 3), '.2f')}x**\n\n"
        )
        for member in sorted(
            self.game_state.members, key=lambda m: m.bet_amount, reverse=True
        ):
            entry = f"- <@{member.user_id}> ({member.bet_amount} SSC)"
            cash_out_multi = self.game_state.cash_outs.get(member)
            if cash_out_multi is not None:
                amount = int(cash_out_multi * member.bet_amount)
                entry = f"- <@{member.user_id}> **(+{amount} SSC)** 🎉 Cashed out at **{format(round(cash_out_multi, 3), '.2f')}x**"
            elif self.game_state.finished:
                entry = f"- <@{member.user_id}> **(-{member.bet_amount} SSC)** 🪦"

            content += f"{entry}\n"

        embed_contents = {
            "message": content,
            "title": self.name,
            "color": self.embed_details["color"]
            if not self.game_state.finished
            else discord.Colour(0xF54242),
        }

        return create_embed(**embed_contents)

    async def simulate(self):

        crash_point = get_crash_point()
        ticks = 0
        ticks_per_second = 2
        tick_acceleration = 0.1  # 2 ticks for every cycle
        view_initialized = False
        
        past_crashes = await db.get_casino_lobby_logs(self.canonical_name, limit=10)
        past_crash_mults = []
        for log in past_crashes:
            metadata = log.get("metadata")
            if not metadata:
                continue
            crash_mult = json.loads(metadata.decode()).get("crash_multiplier")
            if not crash_mult:
                continue
            
            crash_string = '📈' if crash_mult >= 2 else '📉'
            crash_string += ' ' + format(round(crash_mult, 3), ".2f") + 'x'
            past_crash_mults.insert(0, crash_string)

        
        past_crash_line = "**Past crashes** " + ' | '.join(past_crash_mults)
        while True:
            ticks += int(ticks_per_second)
            self.game_state.current_multiplier = min(
                self.game_state.current_multiplier + ticks * 0.01, crash_point
            )

            if self.game_state.current_multiplier >= crash_point:
                self.game_state.finished = True
            graph = render_graph(self.game_state.current_multiplier, self.game_state.finished)

            content = f"# {self.name}\n{past_crash_line}\n```{graph}```"
            start_time = time.time()
            if not view_initialized:
                await self.interaction.edit_original_response(
                    embed=self.generate_embed(),
                    content=content,
                    view=CrashView(self),
                )
                view_initialized = True
            else:
                await self.interaction.edit_original_response(
                    embed=self.generate_embed(), content=content
                )

            if self.game_state.finished:
                break

            sleep_time = max(0, 1.2 - (time.time() - start_time))
            await asyncio.sleep(sleep_time)
            ticks_per_second += tick_acceleration

    async def start(self, members: List[DegenerateGambler]) -> None:
        self.game_state.members = members
        await self.simulate()
        await self.interaction.edit_original_response(
            embed=self.generate_embed(), view=None
        )
        await self.finish()

    async def finish(self) -> None:
        if self.finish_callback:
            await self.finish_callback()

    def get_metadata(self) -> Dict:
        return self.game_state.to_dict()
