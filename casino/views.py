from typing import TYPE_CHECKING, Callable

import discord
from casino.models import DegenerateGambler
from casino.util import get_log_source
import db
from util import user_interaction_callback

if TYPE_CHECKING:
    from casino.casino import CasinoLobby


class BetModal(discord.ui.Modal):
    bet_amount = discord.ui.TextInput(
        label="Bet amount",
        placeholder="Amount of SSC to bet (10 to 1000)",
        style=discord.TextStyle.short,
        required=True,
        max_length=12,
    )

    def __init__(self, name: str, bet_callback: Callable, original_interaction: discord.Interaction):
        super().__init__(title=name)
        self.bet_callback = bet_callback
        self.original_interaction = original_interaction

    @user_interaction_callback()
    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet_amount = int(self.bet_amount.value)
            if not 10 <= bet_amount <= 1000:
                raise ValueError("Bet amount must be within 10 to 1000.")
            
            old_ssc = interaction.data["user_data"]["sail_credit"] # pyright: ignore
            if old_ssc < bet_amount:
                await interaction.response.send_message(
                    "You don't have enough SSC to bet!", ephemeral=True
                )
                return
            
            await self.bet_callback(interaction.user.id, bet_amount, old_ssc, self.original_interaction)
            await interaction.response.defer()
        except Exception:
            await interaction.response.send_message(
                "The bet amount must be a whole number between 10 to 1000.", ephemeral=True
            )
            return

class CasinoLobbyView(discord.ui.View):

    def __init__(self, lobby: 'CasinoLobby'):
        super().__init__(timeout=lobby.game.lobby_time)
        self.lobby = lobby
        # Start, join, leave, cancel buttons
        play_button = discord.ui.Button(label="Play", style=discord.ButtonStyle.blurple)
        play_button.callback = self.play
        self.add_item(play_button)


    async def add_member(self, user_id: int, bet_amount: int, old_ssc: int, interaction: discord.Interaction):
        if self.lobby.started:
            return

        source = get_log_source(self.lobby.game.canonical_name, "DEBIT")
        await db.change_and_log_sail_credit(user_id, -1, -1, -1, old_ssc, old_ssc - bet_amount, source)
        self.lobby.members.append(DegenerateGambler(user_id, bet_amount))
        await interaction.edit_original_response(
            embed=self.lobby.generate_embed(),
        )


    @user_interaction_callback()
    async def play(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        for member in self.lobby.members:
            if member.user_id == user_id:
                await interaction.response.send_message(
                    "You already bet!", ephemeral=True
                )
                return
        
        await interaction.response.send_modal(
            BetModal(
                name=self.lobby.game.name,
                bet_callback=self.add_member,
                original_interaction=interaction
            )
        )