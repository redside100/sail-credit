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

    def __init__(
        self,
        name: str,
        bet_callback: Callable,
        original_interaction: discord.Interaction,
    ):
        super().__init__(title=name)
        self.bet_callback = bet_callback
        self.original_interaction = original_interaction

    @user_interaction_callback()
    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet_amount = int(self.bet_amount.value)
            if not 10 <= bet_amount <= 1000:
                raise ValueError("Bet amount must be within 10 to 1000.")

            old_ssc = interaction.data["user_data"]["sail_credit"]  # pyright: ignore
            if old_ssc < bet_amount:
                await interaction.response.send_message(
                    "You don't have enough SSC to bet!", ephemeral=True
                )
                return

            await self.bet_callback(
                interaction.user.id, bet_amount, old_ssc, self.original_interaction
            )
            await interaction.response.defer()
        except Exception:
            await interaction.response.send_message(
                "The bet amount must be a whole number between 10 to 1000.",
                ephemeral=True,
            )
            return


class CasinoLobbyView(discord.ui.View):

    def __init__(self, lobby: "CasinoLobby"):
        super().__init__(timeout=lobby.game.lobby_time)
        self.lobby = lobby
        bet_button = discord.ui.Button(
            label="Place bet", style=discord.ButtonStyle.blurple
        )
        bet_button.callback = self.place_bet
        self.add_item(bet_button)

    async def bet(
        self,
        user_id: int,
        bet_amount: int,
        old_ssc: int,
        interaction: discord.Interaction,
    ):
        if self.lobby.started:
            return

        source = get_log_source(self.lobby.game.canonical_name, "DEBIT")
        await db.change_and_log_sail_credit(
            user_id, -1, -1, -1, old_ssc, old_ssc - bet_amount, source
        )

        user_id = interaction.user.id
        casino_member = None
        for member in self.lobby.members:
            if member.user_id == user_id:
                casino_member = member

        if casino_member:
            casino_member.bet_amount += bet_amount
        else:
            self.lobby.members.append(DegenerateGambler(user_id, bet_amount))

        await interaction.edit_original_response(
            embed=self.lobby.generate_embed(),
        )

    @user_interaction_callback()
    async def place_bet(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            BetModal(
                name=self.lobby.game.name,
                bet_callback=self.bet,
                original_interaction=interaction,
            )
        )

    @user_interaction_callback()
    async def bet_10(self, interaction: discord.Interaction):
        await self.bet(
            interaction.user.id,
            10,
            interaction.data["user_data"]["sail_credit"],
            interaction,
        )

    @user_interaction_callback()
    async def bet_100(self, interaction: discord.Interaction):
        await self.bet(
            interaction.user.id,
            100,
            interaction.data["user_data"]["sail_credit"],
            interaction,
        )

    async def bet_500(self, interaction: discord.Interaction):
        await self.bet(
            interaction.user.id,
            500,
            interaction.data["user_data"]["sail_credit"],
            interaction,
        )
