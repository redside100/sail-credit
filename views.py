import time
import discord

import db


class PartyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)  # 5 minutes

    # async def interaction_check(self, interaction: discord.Interaction):
    #     if interaction.user.id != self.id_b:
    #         return False
    #     return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, _):

        print("TEST")
        # if self.id_a in self.battle_cache:
        #     del self.battle_cache[self.id_a]

        # if self.id_b in self.battle_cache:
        #     del self.battle_cache[self.id_b]

        # if (self.id_a, self.id_b) in self.battle_cancel_cache:
        #     del self.battle_cancel_cache[(self.id_a, self.id_b)]

        # await interaction.response.send_message(
        #     f"<@{self.id_a}> <@{self.id_b}>",
        #     embed=create_embed("Leetcode battle cancelled!"),
        # )

        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, _):

        print("YEET")
        # if (self.id_a, self.id_b) in self.battle_cancel_cache:
        #     del self.battle_cancel_cache[(self.id_a, self.id_b)]

        # await interaction.response.send_message(
        #     embed=create_embed(
        #         f"<@{self.id_b}> declined the cancel request.",
        #     )
        # )

        self.stop()
