from dataclasses import dataclass
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
    GOOD = "GOOD"
    FLAKER = "FLAKER"


@dataclass
class Party:
    uuid: UUID
    type: str
    name: str
    owner_id: int
    size: int = 5
    status: PartyStatus = PartyStatus.ACTIVE
    description: str = ""


@dataclass
class PartyMember:
    party_id: int
    user_id: int
    status: PartyMemberStatus = PartyMemberStatus.NEUTRAL


class PartyService:
    def __init__(self):
        self.parties: list[Party] = []
        self.party_members: list[PartyMember] = []

    def create_party(
        self,
        user: User | Member,
        **kwargs,
    ) -> Party:

        print(f"create_party() called with {type(user)}")

        # We don't want to pass None values to the Party constructor, preserving
        # the default values of the dataclass.
        party_kwargs = {kwarg: kwargs for kwarg in kwargs if kwargs[kwarg] is not None}

        # Pre-processing.
        if party_kwargs.get("name") is None:
            party_kwargs["name"] = f"{user.name}'s {type} Party"

        party = Party(uuid=uuid4(), owner_id=user.id, **kwargs)
        self.parties.append(party)
        return party

    def get_party(self, uuid: UUID):
        for party in self.parties:
            if party.uuid == uuid:
                return party
        return None
