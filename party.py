from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum
from uuid import UUID, uuid4
from discord import User, Member
import discord


class PartyStatus(Enum):
    ACTIVE = "ACTIVE"
    STARTED = "STARTED"
    INACTIVE = "INACTIVE"
    DELETED = "DELETED"


class PartyMemberStatus(Enum):
    NEUTRAL = "NEUTRAL"
    SHOWED_UP = "SHOWED_UP"
    FLAKED = "FLAKED"


@dataclass
class PartyMember:
    user_id: int
    status: PartyMemberStatus = PartyMemberStatus.NEUTRAL


@dataclass
class Party:
    uuid: UUID
    role: discord.Role
    name: str
    owner_id: Optional[int]
    size: int = 5
    status: PartyStatus = PartyStatus.ACTIVE
    description: str = ""
    members: list[PartyMember] = field(default_factory=[])

    def generate_embed(self) -> str:
        content = (
            f"`{self.size - len(self.members)}` spots left.\n\n" + f"Current Party:\n"
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
        party = Party(
            uuid=party_uuid,
            owner_id=user.id,
            members=[
                PartyMember(
                    user_id=user.id,
                )
            ],
            **party_kwargs,
        )
        self.parties[party_uuid] = party
        return party

    def get_party(self, uuid: UUID) -> Optional[Party]:
        return self.parties.get(uuid)

    def remove_party(self, uuid: UUID) -> None:
        if uuid in self.parties:
            del self.parties[uuid]
