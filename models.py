from typing import Optional, cast

import logging
from discord import Message
import discord
from pydantic import BaseModel


class MessageState(BaseModel):
    id: int
    channel_id: int


class SerializableMessage(Message):
    @staticmethod
    def from_message(message: Message) -> "SerializableMessage":
        return cast(SerializableMessage, message)

    @staticmethod
    async def from_state(
        data: MessageState, client: discord.Client
    ) -> Optional["SerializableMessage"]:
        try:
            channel = client.get_channel(data.channel_id)
            if not channel:
                logging.warning(
                    f"Channel {data.channel_id} not found for message {data.id}"
                )
                return None

            message = await channel.fetch_message(data.id)
            return cast(SerializableMessage, message)
        except discord.NotFound:
            logging.warning(
                f"Message with ID {data.id} not found in channel {data.channel_id}"
            )
            return None

    def to_state(self) -> MessageState:
        return MessageState(id=self.id, channel_id=self.channel.id)
