from datetime import timedelta
from typing import Optional
from uuid import uuid4

import discord
from discord.ext import commands

from src.cobot import CObot, COInteraction
from src.custom_args import ColorOption, DurationOption
from src.modules.giveaways.types import GiveawayToSendData
from src.modules.giveaways.views import GiveawayView


class GiveawaysCog(commands.Cog):
    "Handle giveaways"

    def __init__(self, bot: CObot):
        self.bot = bot
        self.embed_color = 0x9933ff

    group = discord.app_commands.Group(
        name="giveaways",
        description="Manage giveaways in your server",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True
    )

    @group.command(name="list")
    async def gw_list(self, interaction: COInteraction, *, include_stopped: bool=False):
        "List all the giveaways in the server"
        await interaction.response.defer()
        text = ""
        now = discord.utils.utcnow()
        docs = self.bot.fb.get_giveaways() if include_stopped else self.bot.fb.get_active_giveaways()
        async for gaw in docs:
            name = gaw["name"]
            text += f"**{name}**  -  "
            if participants := await self.bot.fb.get_giveaways_participants(gaw["id"]):
                participants_count = len(participants)
                if participants_count == 0:
                    text += "no participant - "
                elif participants_count == 1:
                    text += "1 participant - "
                else:
                    text += f"{participants_count} participants - "
            else:
                self.bot.log.warning("Could not get participants for giveaway %s", gaw["id"])
            end_date = discord.utils.format_dt(gaw["ends_at"], "R")
            if gaw["ends_at"] > now:
                text += f"ends in {end_date}\n"
            else:
                text += f"ended {end_date}\n"
        embed = discord.Embed(
            title=("List of all giveaways" if include_stopped else "List of active giveaways"),
            description=text,
            color=self.embed_color
        )
        await interaction.followup.send(embed=embed)

    @group.command(name="create")
    async def gw_create(self, interaction: COInteraction, *, name: str, description: str,
                        duration: DurationOption, channel: Optional[discord.TextChannel]=None,
                        color: Optional[ColorOption]=None, max_entries: Optional[int]=None,
                        winners_count: int=1):
        "Create a giveaway"
        if interaction.guild is None:
            return
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message("Giveaways can only be sent in text channels!")
            return
        if target_channel is None:
            return
        await interaction.response.defer()
        ends_date = discord.utils.utcnow() + timedelta(seconds=duration)
        data: GiveawayToSendData = {
            "id": uuid4().hex,
            "guild": interaction.guild.id,
            "channel": target_channel.id,
            "name": name,
            "description": description,
            "color": color.value if color else self.embed_color,
            "max_entries": max_entries,
            "winners_count": winners_count,
            "ends_at": ends_date,
            "ended": False,
            "winners": []
        }
        message = await self.send_gaw(target_channel, data)
        await self.bot.fb.create_giveaway({
            **data,
            "message": message.id
        })
        await interaction.followup.send(f"Giveaway created at {message.jump_url} !")

    async def create_new_gaw_embed(self, data: GiveawayToSendData):
        "Create a Discord embed for a newly created giveaway"
        embed = discord.Embed(
            title=data["name"],
            description=data["description"],
            color=data["color"],
            timestamp=data["ends_at"]
        )
        if max_entries := data["max_entries"]:
            embed.add_field(name="Participants", value=f"0/{max_entries}")
        else:
            embed.add_field(name="Participants", value="0")
        embed.set_footer(text="Ends at")
        return embed

    async def send_gaw(self, channel: discord.TextChannel, data: GiveawayToSendData):
        "Send a giveaway message in a given channel"
        embed = await self.create_new_gaw_embed(data)
        view = GiveawayView(self.bot, data, "Join the giveaway!")
        msg = await channel.send(embed=embed, view=view)
        return msg



async def setup(bot: CObot):
    "Load the cog"
    await bot.add_cog(GiveawaysCog(bot))
