from collections import deque
from dataclasses import dataclass, field
import time
from typing import Dict, Optional
from enum import Enum
from uuid import UUID, uuid4
from discord import User, Member
import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta, timezone

from util import create_embed, disable_buttons_and_stop_view

STARTING_SSC = 1000


class PartyStatus(Enum):
    ASSEMBLING = "ASSEMBLING"  # Finding members for the party.
    SUCCESS = "SUCCESS"  # Success! The party hasn't reported anyone flaking.
    VOTING = "VOTING"  # Somebody stands trials for flaking.
    FAILED = "FAILED"  # The party did not go through.


class PartyMemberStatus(Enum):
    NEUTRAL = "NEUTRAL"
    SHOWED_UP = "SHOWED_UP"
    FLAKED = "FLAKED"


@dataclass
class PartyMember:
    user_id: int
    name: str
    cached_ssc: int
    status: PartyMemberStatus = PartyMemberStatus.NEUTRAL


@dataclass
class Party:
    uuid: UUID
    role: discord.Role
    name: str
    owner_id: Optional[int]
    created_at: int
    role_image_url: Optional[int] = None
    finished_at: Optional[int] = None
    start_time: Optional[int] = None
    interaction: Optional[discord.Interaction] = None
    jump_url: Optional[str] = None
    max_size: int = 5
    status: PartyStatus = PartyStatus.ASSEMBLING
    description: str = ""
    members: list[PartyMember] = field(default_factory=lambda: [])
    waitlist: deque[PartyMember] = field(default_factory=lambda: deque())

    @property
    def size(self) -> int:
        return len(self.members)

    def generate_embed(self) -> str:
        start_string = f"\n\nStarts: <t:{self.start_time}:R>" if self.start_time else ""
        waitlist_mentions = [f"<@{m.user_id}>" for m in self.waitlist]
        waitlist_string = f"Waitlist: {" ".join(waitlist_mentions)}"
        remaining_spots = self.max_size - len(self.members)
        content = (
            f"**{self.name}**\n\n`{remaining_spots}` spot{'s' if remaining_spots != 1 else ''} left.{start_string}\n\n"
            + f"Current Party:\n"
        )
        for member in self.members:
            content += f"- {'👑 ' if member.user_id == self.owner_id else ''}<@{member.user_id}>"
            if member.cached_ssc < 900:
                content += f' [(!)]({self.jump_url} "Warning: Party member has low SSC ({member.cached_ssc}).")'
            content += "\n"

        if self.waitlist:
            content += f"\n{waitlist_string}\n"

        embed_contents = {"message": content, "color": self.role.color}

        if self.role_image_url:
            embed_contents["image_url"] = self.role_image_url

        return embed_contents

    """
    Adds a party member.
    Automatically adds the member to the waitlist if the party is full.
    Returns true if waitlisted, false if not.
    """

    def add_member(self, user_id: int, user_name: str, user_ssc: int) -> bool:
        party_member = PartyMember(user_id=user_id, name=user_name, cached_ssc=user_ssc)

        # There is space, add to member list.
        if len(self.members) < self.max_size:
            self.members.append(party_member)
            return False

        # No space, add to waitlist.
        self.waitlist.append(party_member)
        return True

    """
    Removes a party member.
    Automatically adds the next waiting user as a member.
    Returns the member that was auto added from waitlist, if any.
    """

    def remove_member(self, user_id: int) -> Optional[PartyMember]:

        # User is in the waitlist. Remove them from the waitlist.
        waitlist_ids = [member.user_id for member in self.waitlist]
        if user_id in waitlist_ids:
            self.waitlist = [
                member for member in self.waitlist if member.user_id != user_id
            ]
            return None

        # User is a member. Remove them from the member list.
        self.members = [member for member in self.members if member.user_id != user_id]

        new_member = None
        # If there is a waitlist, de-queue the first one and add them to the party.
        if self.waitlist:
            new_member = self.waitlist.popleft()
            self.members.append(new_member)

        # If the user that left was the owner, assign a new owner if possible.
        if user_id == self.owner_id:
            self.owner_id = self.members[0].user_id if self.members else None

        return new_member


class PartyService:
    def __init__(self):
        self.parties: Dict[UUID, Party] = {}
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.scheduler.start()

    def create_party(
        self,
        user: User | Member,
        user_ssc: int,
        start_time: Optional[datetime],
        **kwargs,
    ) -> Party:
        # We don't want to pass None values to the Party constructor, preserving
        # the default values of the dataclass.
        party_kwargs = {
            kwarg: kwargs[kwarg] for kwarg in kwargs if kwargs[kwarg] is not None
        }

        # Pre-processing.
        if party_kwargs.get("name") is None:
            role = party_kwargs["role"]
            party_kwargs["name"] = f"{user.display_name}'s <@&{role.id}> Party"

        party_uuid = uuid4()

        # Add start job to scheduler with default 5 mins
        run_date = datetime.now(tz=timezone.utc) + timedelta(minutes=5)

        # Check if we have an initial start time
        if start_time:
            run_date = start_time

        self.scheduler.add_job(
            self._start_scheduled_party,
            "date",
            args=[party_uuid],
            run_date=run_date,
            id=str(party_uuid),
        )

        party = Party(
            uuid=party_uuid,
            owner_id=user.id,
            members=[
                PartyMember(
                    user_id=user.id, name=user.display_name, cached_ssc=user_ssc
                )
            ],
            start_time=int(run_date.timestamp()),
            **party_kwargs,
        )

        self.parties[party_uuid] = party
        return party

    async def _start_scheduled_party(self, uuid: UUID) -> None:

        # Locally import here to avoid circular imports.
        # This is fine since this private function is only called internally.
        from views import PostPartyView, PartyView

        party = self.get_party(uuid)
        print(f"Running job {uuid}!")

        # If for any reason the party doesn't exist anymore, do nothing.
        if not party:
            return

        interaction = party.interaction
        # If for any reason the party doesn't have an interaction instance, do nothing.
        if not interaction:
            return

        # We need to edit/reply to the original message because our auth token for the followup channel may have expired.
        message = await interaction.original_response()

        # we need to refetch this message in order to edit it (auth)
        message = await message.channel.fetch_message(message.id)

        # Slightly stricter requirements here, the party needs to be full and more than 1 person to auto start.
        # If not, the party can still be started manually.
        async def unschedule_party():
            # Setting start_time to None will cause the party embed to not include a starting timestamp
            party.start_time = None

            # Edit the original message to reflect it
            await message.edit(
                embed=create_embed(**party.generate_embed()),
                view=PartyView(party, self, scheduled=False),
            )

        # We can't start parties with less than 2 members.
        if party.size < 2:
            await message.reply(
                f"<@{party.owner_id}> This party can't be started automatically since it has less than 2 people. You can make a new party to try again."
            )
            self.remove_party(party.uuid)
            party.start_time = None

            await message.edit(embed=create_embed(**party.generate_embed()), view=None)

            return

        # We can't start parties that aren't full.
        if party.size < party.max_size:
            await message.reply(
                f"<@{party.owner_id}> This party wasn't started automatically since it isn't full. You can still start it manually by clicking **Start** in the original message!"
            )
            await unschedule_party()
            return

        # Copy pasta -> transformed logic from the view.

        # Notify all party members.
        party_mentions = [f"<@{member.user_id}>" for member in party.members]

        report_msg = "For the next 5 minutes, any party member can click the **Report** button to report a flaker."

        next_view = PostPartyView(party, None)
        next_view.message = await message.reply(
            content="The party has started! Come join "
            + ", ".join(party_mentions)
            + ".",
            embed=create_embed(
                f"The party was started **automatically** for <@&{party.role.id}>!\n\n{report_msg}"
            ),
            view=next_view,
        )

        self.remove_party(party.uuid)

        await disable_buttons_and_stop_view(
            discord.ui.View().from_message(message), message
        )

    def get_party(self, uuid: UUID) -> Optional[Party]:
        return self.parties.get(uuid)

    def update_party_start_time(self, uuid: UUID, minutes: int) -> Optional[int]:
        job_id = str(uuid)
        job = self.scheduler.get_job(job_id=job_id)
        if job:
            delta = timedelta(minutes=abs(minutes))
            new_run_time = (
                job.trigger.run_date + delta
                if minutes > 0
                else job.trigger.run_date - delta
            )

            now = int(time.time())
            if new_run_time.timestamp() < now:
                new_run_time = datetime.now(tz=timezone.utc) + timedelta(seconds=10)
            elif new_run_time.timestamp() > (now + 3600 * 12):
                new_run_time = datetime.now(tz=timezone.utc) + timedelta(hours=12)

            self.scheduler.reschedule_job(job_id, run_date=new_run_time)
            self.parties[uuid].start_time = int(new_run_time.timestamp())

            return self.parties[uuid].start_time

    def remove_party(self, uuid: UUID) -> None:
        if uuid in self.parties:
            del self.parties[uuid]

        # Remove the queued start job.
        job_id = str(uuid)
        if self.scheduler.get_job(job_id=job_id):
            self.scheduler.remove_job(job_id=job_id)
