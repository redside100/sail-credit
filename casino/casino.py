from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional
import uuid
from casino.coinflip import Coinflip
from casino.jackpot import Jackpot
from casino.models import CasinoGame, CasinoGameAlias, DegenerateGambler
from casino.util import get_log_source
from casino.views import CasinoLobbyView
import db
from util import create_embed
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import discord

from casino.crash import Crash

GAME_MAP: Dict[CasinoGameAlias, type[CasinoGame]] = {
    "crash": Crash,
    "coinflip": Coinflip,
    "jackpot": Jackpot,
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
    max_size: Optional[int] = None
    finished: bool = False

    @property
    def size(self) -> int:
        return len(self.members)

    def generate_embed(self):
        content = f"{self.game.description}\n\nStarts: <t:{self.start_time}:R>\n"
        for member in sorted(self.members, key=lambda m: m.bet_amount, reverse=True):
            content += f"- {self.game.player_descriptor(member, self.members)}\n"

        embed_contents = {
            "message": content,
            "title": self.game.name,
            **self.game.embed_details,
        }

        return create_embed(**embed_contents)


class CasinoPitboss:
    def __init__(self):
        self.lobbies: List[CasinoLobby] = []
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.scheduler.start()

    async def start_lobby(
        self,
        game: CasinoGameAlias,
        interaction: discord.Interaction,
        on_lobby_create: Optional[Callable] = None,
        **kwargs,
    ):

        game_class = GAME_MAP[game]

        for lobby in self.lobbies:
            if isinstance(lobby.game, game_class) and not isinstance(
                lobby.game, Coinflip
            ):
                await interaction.response.send_message(
                    embed=create_embed(f"There is already a {game} game active!"),
                    ephemeral=True,
                )
                return

        initialized_game = game_class(interaction, **kwargs)
        now = int(time.time())
        start_time = now + initialized_game.lobby_time
        lobby = CasinoLobby(
            uuid=uuid.uuid4(),
            name=initialized_game.name,
            game=initialized_game,
            created_at=now,
            start_time=start_time,
            interaction=interaction,
            max_size=initialized_game.max_size,
        )

        if on_lobby_create:
            on_lobby_create(lobby)

        initialized_game.finish_callback = lambda: self.finish_lobby(lobby)

        self.lobbies.append(lobby)
        run_date = datetime.now(tz=timezone.utc) + timedelta(
            seconds=lobby.game.lobby_time
        )

        async def start(casino_lobby: CasinoLobby):
            casino_lobby.started = True

            try:
                await casino_lobby.game.start(casino_lobby.members)
            except Exception:
                if not casino_lobby.finished:
                    # Refund all bets if the game fails
                    for member in casino_lobby.members:
                        user_data = await db.get_user(member.user_id)
                        ssc = user_data["sail_credit"]
                        await db.change_and_log_sail_credit(
                            member.user_id,
                            -1,
                            -1,
                            -1,
                            ssc,
                            ssc + member.bet_amount,
                            source=get_log_source(
                                casino_lobby.game.canonical_name, "CREDIT"
                            ),
                        )
                    await self.finish_lobby(casino_lobby)
                    await casino_lobby.interaction.channel.send(
                        embed=create_embed(
                            f"An error occurred during the last **{casino_lobby.game.name}** lobby.\nAll bets have been refunded.",
                            color=discord.Colour.red(),
                        ),
                        view=None,
                    )
                raise

        self.scheduler.add_job(
            start,
            "date",
            args=[lobby],
            run_date=run_date,
            id=str(lobby.uuid),
        )

        await interaction.response.send_message(
            embed=lobby.generate_embed(), view=CasinoLobbyView(lobby)
        )

    async def finish_lobby(self, lobby: CasinoLobby):
        if lobby in self.lobbies:
            self.lobbies.remove(lobby)

        end_time = int(time.time())
        await db.create_casino_lobby_log(
            str(lobby.uuid),
            lobby.start_time,
            end_time,
            lobby.game.get_metadata(),
            lobby.game.canonical_name,
        )
