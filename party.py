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
    status: PartyMemberStatus = PartyMemberStatus.NEUTRAL


@dataclass
class Party:
    uuid: UUID
    role: discord.Role
    name: str
    owner_id: Optional[int]
    creation_time: int
    start_time: Optional[int]
    interaction: Optional[discord.Interaction] = None
    jump_url: Optional[str] = None
    size: int = 5
    status: PartyStatus = PartyStatus.ASSEMBLING
    description: str = ""
    members: list[PartyMember] = field(default_factory=[])

    def generate_embed(self) -> str:
        start_string = f"\n\nStarts: <t:{self.start_time}:R>" if self.start_time else ""
        content = (
            f"`{self.size - len(self.members)}` spots left.{start_string}\n\n"
            + f"Current Party:\n"
        )
        for member in self.members:
            content += f"- <@{member.user_id}>\n"

        return content

    def leave_party(self, user_id: int):
        self.members = [member for member in self.members if member.user_id != user_id]
        if user_id == self.owner_id:
            self.owner_id = self.members[0].user_id if self.members else None


class PartyService:
    def __init__(self):
        self.parties: Dict[UUID, Party] = {}
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.scheduler.start()

    def create_party(
        self,
        user: User | Member,
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

        # add start job to scheduler with default 5 mins
        run_date = datetime.now(tz=timezone.utc) + timedelta(minutes=5)
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
            members=[PartyMember(user_id=user.id, name=user.display_name)],
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

        # Copy pasta -> transformed logic from the view.
        # Slightly stricter requirements here, the party needs to be full to auto start.
        # If not, the party can still be started manually.
        if len(party.members) < party.size:
            await interaction.followup.send(
                f"<@{party.owner_id}> This party wasn't started automatically since it isn't full. You can still start it manually by clicking **Start** in the original message!"
            )
            # Setting start_time to None will cause the party embed to not include a starting timestamp
            party.start_time = None

            # Edit the original message to reflect it
            await interaction.edit_original_response(
                embed=create_embed(party.generate_embed()),
                view=PartyView(party, self, scheduled=False),
            )
            return

        # Notify all party members.
        party_mentions = [f"<@{member.user_id}>" for member in party.members]

        report_msg = "For the next 5 minutes, any party member can click the **Report** button to report a flaker."

        next_view = PostPartyView(party, None)
        next_view.message = await interaction.followup.send(
            content="The party has started! Come join "
            + ", ".join(party_mentions)
            + ".",
            embed=create_embed(
                f"The party was started **automatically** for <@&{party.role.id}>!\n\n{report_msg}"
            ),
            view=next_view,
        )

        self.remove_party(party.uuid)

        message = await interaction.original_response()
        await disable_buttons_and_stop_view(
            discord.ui.View().from_message(message), interaction
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
