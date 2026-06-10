from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Literal, Optional
import uuid
from casino.models import CasinoGame, CasinoGameAlias, DegenerateGambler
from casino.views import CasinoLobbyView
from util import create_embed
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import discord

from casino.crash import Crash

GAME_MAP: Dict[CasinoGameAlias, type[CasinoGame]] = {
    "crash": Crash
}


@dataclass
class CasinoLobby:
    uuid: uuid.UUID
    name: str
    created_at: int
    start_time: int
    interaction: discord.Interaction
    game: CasinoGame
    members: List[DegenerateGambler] = field(default_factory=list)
    started: bool = False

    @property
    def size(self) -> int:
        return len(self.members)
    
    def generate_embed(self):
        content = f"{self.game.description}\n\nStarts: <t:{self.start_time}:R>\n"
        for member in sorted(self.members, key=lambda m: m.bet_amount, reverse=True):
            content += f"- <@{member.user_id}> **({member.bet_amount} SSC)**"
            content += "\n"

        embed_contents = {"message": content, "title": self.game.name, **self.game.embed_details}

        return create_embed(**embed_contents)


class CasinoPitboss:
    def __init__(self):
        self.lobbies: List[CasinoLobby] = []
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.scheduler.start()

    async def start_lobby(self, game: CasinoGameAlias, interaction: discord.Interaction):

        game_class = GAME_MAP[game]

        for lobby in self.lobbies:
            if isinstance(lobby.game, game_class):
                await interaction.response.send_message(
                    embed=create_embed(f"There is already a {game} game active!"), ephemeral=True
                )
                return


        initialized_game = game_class(interaction)
        now = int(time.time())
        start_time = now + initialized_game.lobby_time
        lobby = CasinoLobby(
            uuid=uuid.uuid4(),
            name=initialized_game.name,
            game=initialized_game,
            created_at=now,
            start_time=start_time,
            interaction=interaction
        )

        initialized_game.finish_callback = lambda: self.finish_lobby(lobby)

        self.lobbies.append(lobby)
        run_date = datetime.now(tz=timezone.utc) + timedelta(seconds=lobby.game.lobby_time)

        async def start(casino_lobby: CasinoLobby):
            casino_lobby.started = True
            await casino_lobby.game.start(casino_lobby.members)

        self.scheduler.add_job(
            start,
            "date",
            args=[lobby],
            run_date=run_date,
            id=str(lobby.uuid),
        )

        await interaction.response.send_message(embed=lobby.generate_embed(), view=CasinoLobbyView(lobby))
    
    async def finish_lobby(self, lobby: CasinoLobby):
        if lobby in self.lobbies:
            self.lobbies.remove(lobby)