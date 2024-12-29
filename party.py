from dataclasses import dataclass, field
import time
from typing import Dict, Optional
from enum import Enum
from uuid import UUID, uuid4
from discord import User, Member
import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta, timezone


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
    start_time: int
    message: Optional[discord.Message] = None
    size: int = 5
    status: PartyStatus = PartyStatus.ASSEMBLING
    description: str = ""
    members: list[PartyMember] = field(default_factory=[])

    def generate_embed(self) -> str:
        content = (
            f"`{self.size - len(self.members)}` spots left.\n\nStarts: <t:{self.start_time}:R>\n\n"
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
            role_id = party_kwargs["role"]
            party_kwargs["name"] = f"{user.name}'s <@&{role_id}> Party"

        party_uuid = uuid4()

        # add start job to scheduler with default 5 mins
        run_date = datetime.now(tz=timezone.utc) + timedelta(minutes=5)
        self.scheduler.add_job(
            self.start_scheduled_party,
            "date",
            args=[party_uuid],
            run_date=run_date,
            id=str(party_uuid),
        )

        party = Party(
            uuid=party_uuid,
            owner_id=user.id,
            members=[PartyMember(user_id=user.id, name=user.name)],
            start_time=int(run_date.timestamp()),
            **party_kwargs,
        )

        self.parties[party_uuid] = party
        return party

    async def start_scheduled_party(self, uuid: UUID) -> None:
        print(f"Job running {uuid}!")
        pass

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
