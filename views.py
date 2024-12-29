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

        # Check if the user is already in the party.
        party_member_ids = [member.user_id for member in self.party.members]
        if interaction.user.id in party_member_ids:
            await interaction.response.send_message(
                "You are already in the party.", ephemeral=True
            )
            return

        self.party.members.append(PartyMember(user_id=interaction.user.id))

        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=create_embed(self.party.generate_embed())
        )

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, _):

        # Check if the user is in the party.
        party_member_ids = [member.user_id for member in self.party.members]
        if interaction.user.id not in party_member_ids:
            await interaction.response.send_message(
                "You are not in the party.", ephemeral=True
            )
            return

        self.party.leave_party(interaction.user.id)

        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=create_embed(self.party.generate_embed())
        )
