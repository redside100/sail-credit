from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from uuid import UUID, uuid4
from discord import User, Member


class PartyStatus(Enum):
    ACTIVE = "ACTIVE"
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
    type: str
    name: str
    owner_id: int
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


class PartyService:
    def __init__(self):
        self.parties: list[Party] = []

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
            party_kwargs["name"] = f"{user.name}'s {type} Party"

        party = Party(
            uuid=uuid4(),
            owner_id=user.id,
            members=[
                PartyMember(
                    user_id=user.id,
                )
            ],
            **party_kwargs,
        )
        self.parties.append(party)
        return party

    def get_party(self, uuid: UUID):
        for party in self.parties:
            if party.uuid == uuid:
                return party
        return None
