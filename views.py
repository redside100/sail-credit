import time
from uuid import UUID
import discord

import db
from party import Party, PartyMember, PartyService
from util import create_embed


class PartyView(discord.ui.View):
    def __init__(self, party: Party):
        self.party: Party = party
        super().__init__(timeout=300)  # 5 minutes

    @discord.ui.button(label="Join", style=discord.ButtonStyle.blurple)
    async def join(self, interaction: discord.Interaction, _):

        # TODO: Check if the user is already in the party.
        self.party.members.append(PartyMember(user_id=interaction.user.id))

        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=create_embed(PartyService.generate_embed(self.party))
        )

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, _):

        # TODO allow users to leave the party.
        pass
