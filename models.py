from typing import Optional, cast

from discord import Message
import discord
from pydantic import BaseModel, ConfigDict, Field


class SerializableMessage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    message_id: int
    channel_id: int
    discord_message: Optional[Message] = Field(exclude=True, default=None)

    @staticmethod
    def from_message(message: Message) -> "SerializableMessage":
        return SerializableMessage(
            message_id=message.id,
            channel_id=message.channel.id,
            discord_message=message,
        )

    @staticmethod
    def initialize_from_state(
        serializable_message: "SerializableMessage", client: discord.Client
    ) -> "SerializableMessage":
        channel = client.get_channel(serializable_message.channel_id)
        if not channel:
            raise ValueError(
                f"Channel with ID {serializable_message.channel_id} not found."
            )

        discord_message = channel.fetch_message(serializable_message.message_id)
        return SerializableMessage(
            message_id=serializable_message.message_id,
            channel_id=serializable_message.channel_id,
            discord_message=discord_message,
        )
