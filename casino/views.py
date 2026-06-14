from typing import TYPE_CHECKING, Callable

import discord
from casino.models import DegenerateGambler
from casino.util import get_log_source
import db
from util import user_interaction_callback, get_balance

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

            old_ssc = get_balance(interaction)
            if old_ssc < bet_amount:
                await interaction.response.send_message(
                    "You don't have enough SSC to bet!", ephemeral=True
                )
                return

            await self.bet_callback(interaction, bet_amount, old_ssc)
        except ValueError:
            await interaction.response.send_message(
                "The bet amount must be a whole number between 10 to 1000.",
                ephemeral=True,
            )


class CasinoLobbyView(discord.ui.View):
    def __init__(self, lobby: "CasinoLobby"):
        super().__init__(timeout=lobby.game.lobby_time)
        self.lobby = lobby

        if lobby.game.bet_config.bet_type == "freeform":
            bet_button = discord.ui.Button(
                label="Place bet", style=discord.ButtonStyle.blurple
            )
            bet_10_button = discord.ui.Button(
                label="10", style=discord.ButtonStyle.green
            )
            bet_100_button = discord.ui.Button(
                label="100", style=discord.ButtonStyle.green
            )
            bet_250_button = discord.ui.Button(
                label="250", style=discord.ButtonStyle.green
            )
            bet_button.callback = self.place_bet
            bet_10_button.callback = self.bet_10
            bet_100_button.callback = self.bet_100
            bet_250_button.callback = self.bet_250
            self.add_item(bet_button)
            self.add_item(bet_10_button)
            self.add_item(bet_100_button)
            self.add_item(bet_250_button)
        elif (
            lobby.game.bet_config.bet_type == "fixed"
            and lobby.game.bet_config.fixed_bet_amount
        ):
            fixed_bet_button = discord.ui.Button(
                label=f"Join ({lobby.game.bet_config.fixed_bet_amount} SSC)",
                style=discord.ButtonStyle.blurple,
            )
            fixed_bet_button.callback = self.fixed_bet
            self.add_item(fixed_bet_button)

    @user_interaction_callback()
    async def fixed_bet(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        for member in self.lobby.members:
            if member.user_id == user_id:
                await interaction.response.defer()
                return

        await self.bet(
            interaction,
            self.lobby.game.bet_config.fixed_bet_amount,
            get_balance(interaction),
        )

    async def bet(
        self, interaction: discord.Interaction, bet_amount: int, old_ssc: int
    ):
        user_id = interaction.user.id
        if self.lobby.started:
            return

        if self.lobby.max_size and len(self.lobby.members) >= self.lobby.max_size:
            await interaction.response.send_message(
                "This lobby is full!", ephemeral=True
            )
            return

        existing_bet = 0
        casino_member = None
        for member in self.lobby.members:
            if member.user_id == user_id:
                casino_member = member
                existing_bet = member.bet_amount
                break

        if existing_bet + bet_amount > 1000:
            allowed = 1000 - existing_bet
            if allowed <= 0:
                await interaction.response.send_message(
                    "You've already reached the maximum bet of 1000 SSC!",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                f"Bet exceeds the 1000 SSC cap. You can only bet {allowed} more SSC.",
                ephemeral=True,
            )
            return

        if old_ssc < bet_amount:
            await interaction.response.send_message(
                "You don't have enough SSC to bet!", ephemeral=True
            )
            return

        source = get_log_source(self.lobby.game.canonical_name, "DEBIT")
        await db.change_and_log_sail_credit(
            user_id, -1, -1, -1, old_ssc, old_ssc - bet_amount, source
        )

        if casino_member:
            casino_member.bet_amount += bet_amount
        else:
            self.lobby.members.append(
                DegenerateGambler(
                    user_id, bet_amount, interaction.user.display_avatar.url
                )
            )

        await interaction.response.edit_message(embed=self.lobby.generate_embed())

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
        await self.bet(interaction, 10, get_balance(interaction))

    @user_interaction_callback()
    async def bet_100(self, interaction: discord.Interaction):
        await self.bet(interaction, 100, get_balance(interaction))

    @user_interaction_callback()
    async def bet_250(self, interaction: discord.Interaction):
        await self.bet(interaction, 250, get_balance(interaction))
