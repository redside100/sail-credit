import os
import traceback
from typing import List

import discord
from pydantic import BaseModel
import json

from casino.casino import CasinoLobby, CasinoPitboss
from party import Party, PartyService
from aiofiles import open as async_open

STATE_FILE = "state.json"


class SerializedState(BaseModel):
    parties: List[Party] = []
    lobbies: List[CasinoLobby] = []


async def load_state(
    client: discord.Client, party_service: PartyService, casino_pitboss: CasinoPitboss
) -> None:
    """
    Load bot state (parties, lobbies) from a JSON file on disk, if it exists.
    """
    if not os.path.exists(STATE_FILE):
        print("No state file found!")
        return

    async with async_open(STATE_FILE, "r") as f:
        contents = await f.read()
        state = SerializedState(**json.loads(contents))

    await party_service.restore_from_state(state.parties, client)
    await casino_pitboss.restore_from_state(state.lobbies, client)


async def save_state(
    party_service: PartyService, casino_pitboss: CasinoPitboss
) -> None:
    """
    Save bot state (parties, lobbies) to a JSON file on disk.
    """
    try:
        state = SerializedState(
            parties=party_service.parties.values(), lobbies=casino_pitboss.lobbies
        )
        async with async_open(STATE_FILE, mode="w") as f:
            await f.write(state.model_dump_json(indent=4, ensure_ascii=True))
    except Exception as e:
        print(f"Error saving state: {e}")
        traceback.print_exc()
