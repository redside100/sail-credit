from datetime import timedelta
import math
import time
from typing import List
from uuid import UUID
import discord

import db
from party import Party, PartyMember, PartyMemberStatus, PartyService, PartyStatus
from sail_bank import SailBank
from util import create_embed, disable_buttons_and_stop_view

bank = SailBank()
"""
View Workflow for Parties

    1. PartyView (ASSEMBLING)
    2. PostPartyView (SUCCESS)

    (if somebody flaked, and no party isn't currently VOTING)
    3. ReportSelectView (VOTING)
    4. ReportView (VOTING)
    5. Timeout (FAILED)
"""


class PartyView(discord.ui.View):
    """
    This view is responsible for removing the party on timeout, or start.
    """

    def __init__(self, party: Party, party_service: PartyService, scheduled=True):
        self.party: Party = party
        self.party_service = party_service
        super().__init__(timeout=3600 * 12)  # 12 hr

        # Start, join, leave, cancel buttons
        start_button = discord.ui.Button(label="Start", style=discord.ButtonStyle.green)
        join_button = discord.ui.Button(label="Join", style=discord.ButtonStyle.blurple)
        leave_button = discord.ui.Button(label="Leave", style=discord.ButtonStyle.red)
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)

        start_button.callback = self.start
        join_button.callback = self.join
        leave_button.callback = self.leave
        cancel_button.callback = self.cancel

        self.add_item(start_button)

        # Not scheduled if the job already ran and did not autostart.
        # Leave out join/leave buttons
        if scheduled:
            self.add_item(join_button)
            self.add_item(leave_button)

        self.add_item(cancel_button)

        # Leave out time adjustment buttons if not scheduled.
        if scheduled:

            def callback_constructor(minutes: int):
                async def button_callback(interaction: discord.Interaction):
                    if interaction.user.id != self.party.owner_id:
                        await interaction.response.send_message(
                            "Only the party leader can use this button!", ephemeral=True
                        )
                        return

                    self.party_service.update_party_start_time(self.party.uuid, minutes)
                    await interaction.response.defer()
                    await interaction.edit_original_response(
                        embed=create_embed(self.party.generate_embed())
                    )

                return button_callback

            # Add time adjustment buttons
            for val in [
                ("-15m", -15),
                ("+5m", 5),
                ("+15m", 15),
                ("+1h", 60),
            ]:
                button = discord.ui.Button(
                    label=val[0], style=discord.ButtonStyle.gray, row=1
                )
                button.callback = callback_constructor(val[1])
                self.add_item(button)

    # When this view is inactive, remove the party.
    async def on_timeout(self):
        # TODO: Fix cancer. Pass in self-referential message, and then cancel.
        self.party_service.remove_party(self.party.uuid)

    async def start(self, interaction: discord.Interaction):

        if not interaction.user.id == self.party.owner_id:
            await interaction.response.send_message(
                "Only the party leader can use this button!", ephemeral=True
            )
            return

        await interaction.response.defer()

        # TODO: Uncomment.
        # if len(self.party.members) < 2:
        #     await interaction.edit_original_response(
        #         embed=create_embed(
        #             "This party was not started since there are not enough members."
        #         ),
        #         content=None,
        #     )
        #     self.party_service.remove_party(self.party.uuid)
        #     await disable_buttons_and_stop_view(self, interaction)
        #     return

        # Notify all party members.
        party_mentions = [f"<@{member.user_id}>" for member in self.party.members]

        report_msg = "For the next 5 minutes, any party member can click the **Report** button to report a flaker."

        next_view = PostPartyView(self.party, None)
        next_view.message = await interaction.followup.send(
            content="The party has started! Come join "
            + ", ".join(party_mentions)
            + ".",
            embed=create_embed(
                f"<@{self.party.owner_id}> started the party for <@&{self.party.role.id}>!\n\n{report_msg}"
            ),
            view=next_view,
        )

        self.party_service.remove_party(self.party.uuid)
        await disable_buttons_and_stop_view(self, interaction)

    async def join(self, interaction: discord.Interaction):

        # Check if the user is already in the party.
        party_member_ids = [member.user_id for member in self.party.members]
        if interaction.user.id in party_member_ids:
            await interaction.response.send_message(
                "You are already in the party.", ephemeral=True
            )
            return

        # Check if the party is full.
        # TODO: In the future, people can still join parties which are full but are
        # waitlisted.
        if len(self.party.members) >= self.party.size:
            await interaction.response.send_message(
                "The party is full.", ephemeral=True
            )
            return

        self.party.members.append(
            PartyMember(user_id=interaction.user.id, name=interaction.user.display_name)
        )

        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=create_embed(self.party.generate_embed())
        )

    async def leave(self, interaction: discord.Interaction):

        # Check if the user is in the party.
        party_member_ids = [member.user_id for member in self.party.members]
        if interaction.user.id not in party_member_ids:
            await interaction.response.send_message(
                "You are not in the party.", ephemeral=True
            )
            return

        old_owner = self.party.owner_id
        self.party.leave_party(interaction.user.id)

        await interaction.response.defer()

        # If the party has no members left, it's abandoned.
        if not self.party.members:
            await interaction.edit_original_response(
                embed=create_embed("This party was abandoned since everyone left."),
                content=None,
            )
            await disable_buttons_and_stop_view(self, interaction)
            return

        await interaction.edit_original_response(
            embed=create_embed(self.party.generate_embed()),
            # If the party has a new owner, announce it.
            content=(
                f"<@{self.party.owner_id}> is the new party leader."
                if self.party.owner_id != old_owner
                else None
            ),
        )

    async def cancel(self, interaction: discord.Interaction):

        # Check if the user is the leader.
        if interaction.user.id != self.party.owner_id:
            await interaction.response.send_message(
                "Only the party leader can use this button!", ephemeral=True
            )
            return

        self.party_service.remove_party(self.party.uuid)
        await interaction.response.defer()

        await interaction.edit_original_response(
            embed=create_embed(
                f"This party was cancelled by the party leader <@{interaction.user.id}>."
            ),
            content=None,
        )
        await disable_buttons_and_stop_view(self, interaction)


class PostPartyView(discord.ui.View):
    def __init__(self, party: Party, message: discord.Message):
        self.party = party
        self.message = message
        super().__init__(timeout=2)  # TESTING PURPOSES.
        # super().__init__(timeout=300)  # 5m  # TODO: Uncomment.

    async def on_timeout(self):
        """
        When the PostPartyView times out, and the party status is not VOTING or FAILED,
        that means no one reported a flaker. The party is a success.
        """
        if (
            self.party.status != PartyStatus.VOTING
            and self.party.status != PartyStatus.FAILED
        ):
            self.party.status = PartyStatus.SUCCESS
            self.party.finished_at = int(time.time())
            reward_data = await bank.process_party_reward(self.party)
            await disable_buttons_and_stop_view(self, self.message)
            await self.message.edit(
                embed=create_embed(self.generate_embed(reward_data)),
            )

    def generate_embed(self, reward_data: dict[str, int]) -> str:
        content = "The party was a success! 🎉\n\n"
        for user_id, reward in reward_data.items():
            content += f"- <@{user_id}> received {reward['new'] - reward['old']} SSC ({reward['old']} SSC -> {reward['new']} SSC).\n"
        return content

    async def interaction_check(self, interaction: discord.Interaction):
        # Only allow party members to interact with this view.
        if interaction.user.id not in [member.user_id for member in self.party.members]:
            return False
        return True

    @discord.ui.button(label="Report", style=discord.ButtonStyle.red)
    async def report(self, interaction: discord.Interaction, _):

        # Check party status
        if self.party.status == PartyStatus.VOTING:
            await interaction.response.send_message(
                "Voting has already started. Please wait for the current vote to end.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            content="Who do you want to report?",
            view=ReportSelectView(self.party, interaction.user.id),
            ephemeral=True,
        )


class ReportSelectView(discord.ui.View):
    def __init__(self, party: Party, reporter_id: int):
        self.party = party
        self.party.status = PartyStatus.VOTING
        self.reporter_id = reporter_id
        super().__init__(timeout=60)  # 1m

        self.select = discord.ui.Select(placeholder=f"Select a user...")
        self.select.callback = self.select_user
        self.select.options = [
            discord.SelectOption(label=member.name, value=member.user_id)
            for member in self.party.members
        ]

        self.add_item(self.select)

    async def select_user(self, interaction: discord.Interaction):
        selected_id = int(self.select.values[0])

        # Check if the party member has already been reported.
        selected_member = next(
            (member for member in self.party.members if member.user_id == selected_id),
            None,
        )
        if selected_member.status == PartyMemberStatus.FLAKED:
            await interaction.response.send_message(
                "This user has already been reported.", ephemeral=True
            )
            return

        view = ReportView(self.party, selected_id)
        await interaction.response.send_message(
            content=f" <@{selected_id}> has been reported by <@{self.reporter_id}>.",
            embed=create_embed(view.generate_embed()),
            view=view,
            ephemeral=False,
            allowed_mentions=discord.AllowedMentions(),
        )
        self.stop()


class ReportView(discord.ui.View):
    def __init__(self, party: Party, reported_id: int):
        self.party = party
        self.reported_id = reported_id
        self.convict_votes = []
        self.acquit_votes = []
        super().__init__(timeout=300)  # 5m

        # Convict Button
        self.convict_button = discord.ui.Button(
            label="Convict", style=discord.ButtonStyle.red
        )

        async def convict_callback(*args, **kwargs):
            await self.on_convict(*args, **kwargs)
            await self.tally_votes(*args, **kwargs)

        self.convict_button.callback = convict_callback
        self.add_item(self.convict_button)

        # Acquit Button
        self.acquit_button = discord.ui.Button(
            label="Acquit", style=discord.ButtonStyle.green
        )

        async def acquit_callback(*args, **kwargs):
            await self.on_acquit(*args, **kwargs)
            await self.tally_votes(*args, **kwargs)

        self.acquit_button.callback = acquit_callback
        self.add_item(self.acquit_button)

        # Declare the member as flaked.
        reported_member = next(
            (member for member in self.party.members if member.user_id == reported_id),
            None,
        )
        reported_member.status = PartyMemberStatus.FLAKED

    def generate_embed(self) -> str:
        self.votes_needed = math.ceil(self.party.size / 2)
        convict_ratio = f"`{len(self.convict_votes)}` / `{self.votes_needed}`"
        acquit_ratio = f"`{len(self.acquit_votes)}` / `{self.votes_needed}`"
        content = f"{convict_ratio} to convict.\n{acquit_ratio} to acquit."
        return content

    async def tally_votes(self, interaction: discord.Interaction):
        """
        Post-processing for votes. If the votes are enough to convict or acquit, end the
        vote.
        """
        # Check if the vote ends.
        if (
            len(self.acquit_votes) < self.votes_needed
            and len(self.convict_votes) < self.votes_needed
        ):
            return

        # Mark the time the party was finished.
        self.party.finished_at = int(time.time())

        # Otherwise calculate the results of the vote.
        if len(self.acquit_votes) >= self.votes_needed:
            content = f"<@{self.reported_id}> has been ACQUITTED! 🎉"
            await interaction.edit_original_response(content=content)
            # No gains to be had.

        if len(self.convict_votes) >= self.votes_needed:
            fine = await bank.process_flaked_user(self.party, self.reported_id)
            content = f"**CONVICTED.** 🔨\n\n"
            content += (
                f"<@{self.reported_id}> has been fined {fine['new'] - fine['old']} SSC "
            )
            content += f"({fine['old']} SSC -> {fine['new']} SSC) for flaking."
            content += f" Thank you for contributing to a better community."
            await interaction.edit_original_response(content=content)

        # The party is no longer voting.
        self.party.status = PartyStatus.FAILED
        await disable_buttons_and_stop_view(self, interaction)

    async def on_convict(self, interaction: discord.Interaction):
        # Check if the user is in the party.
        party_member_ids = [member.user_id for member in self.party.members]
        if interaction.user.id not in party_member_ids:
            await interaction.response.send_message(
                "You are not in the party.", ephemeral=True
            )
            return

        # Check if the user has already voted.
        if interaction.user.id in self.convict_votes:
            await interaction.response.send_message(
                "You have already voted to convict.", ephemeral=True
            )
            return

        # Check if the user has already voted to acquit, and remove if so.
        if interaction.user.id in self.acquit_votes:
            self.acquit_votes.remove(interaction.user.id)

        # Record the vote and re-generate the embed.
        self.convict_votes.append(interaction.user.id)
        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=create_embed(self.generate_embed())
        )

    async def on_acquit(self, interaction: discord.Interaction):
        # Check if the user is in the party.
        party_member_ids = [member.user_id for member in self.party.members]
        if interaction.user.id not in party_member_ids:
            await interaction.response.send_message(
                "You are not in the party.", ephemeral=True
            )
            return

        # Check if the user has already voted.
        if interaction.user.id in self.acquit_votes:
            await interaction.response.send_message(
                "You have already voted to acquit.", ephemeral=True
            )
            return

        # Check if the user has already voted to convict, and remove if so.
        if interaction.user.id in self.convict_votes:
            self.convict_votes.remove(interaction.user.id)

        # Record the vote and re-generate the embed.
        self.acquit_votes.append(interaction.user.id)
        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=create_embed(self.generate_embed())
        )


class MessageBook(discord.ui.View):
    """
    General use view for showing multi-page content.
    Accepts a list of embeds.
    """

    def __init__(
        self,
        user_id: int,
        pages: List[discord.Embed],
    ):
        super().__init__(timeout=120)
        self.page_count = len(pages)

        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i + 1} of {self.page_count}")

        self.pages = pages
        self.user_id = user_id
        self.current_page = 0

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return False
        return True

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.blurple)
    async def prev_button(self, interaction: discord.Interaction, _):
        if not interaction.user.id == self.user_id:
            return

        await self.prev_page(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, _):
        if not interaction.user.id == self.user_id:
            return

        await self.next_page(interaction)

    async def next_page(self, interaction: discord.Interaction):
        self.current_page += 1
        if self.current_page > len(self.pages) - 1:
            self.current_page = 0

        await self.update_page(interaction)

    async def prev_page(self, interaction: discord.Interaction):
        self.current_page -= 1
        if self.current_page < 0:
            self.current_page = len(self.pages) - 1

        await self.update_page(interaction)

    async def update_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.edit_original_response(embed=self.pages[self.current_page])
