from datetime import timedelta
from typing import Optional
from uuid import uuid4

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands, tasks

from src.cobot import CObot, COInteraction
from src.custom_args import ColorOption, DurationOption
from src.modules.giveaways.types import GiveawayData, GiveawayToSendData
from src.modules.giveaways.views import GiveawayView


class GiveawaysCog(commands.Cog):
    "Handle giveaways"

    def __init__(self, bot: CObot):
        self.bot = bot
        self.embed_color = 0x9933ff
        self.scheduler = AsyncIOScheduler()

    async def cog_load(self):
        """Start the scheduler on cog load"""
        self.scheduler.start()
        self.schedule_giveaways.start() # pylint: disable=no-member

    async def cog_unload(self):
        """Stop the scheduler on cog unload"""
        self.scheduler.shutdown()
        self.schedule_giveaways.stop() # pylint: disable=no-member

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Called when *any* interaction from the bot is received
        We use it to detect interactions with any giveaway Join button"""
        if not interaction.guild:
            return # ignore DMs
        if interaction.type != discord.InteractionType.component:
            return # ignore non-button interactions
        if not interaction.data or "custom_id" not in interaction.data:
            return
        custom_ids = interaction.data["custom_id"].split('-')
        if len(custom_ids) != 2 or custom_ids[0] != "gaw":
            return # not a giveaway button
        await interaction.response.defer(ephemeral=True)
        gaw_id = custom_ids[1]
        gaw = await self.bot.fb.get_giveaway(gaw_id)
        if gaw is None or gaw["ended"] or gaw["ends_at"] < discord.utils.utcnow():
            return # giveaway not found or ended
        await self.register_new_participant(interaction, gaw)

    @tasks.loop(minutes=5)
    async def schedule_giveaways(self):
        "Check for expired giveaways and schedule their closing"
        now = discord.utils.utcnow()
        date_treshold = now + timedelta(minutes=5)
        async for giveaway in self.bot.fb.get_active_giveaways():
            if giveaway["ends_at"] < date_treshold:
                self.bot.log.debug(f"[giveaways] Scheduling closing of giveaway {giveaway['id']}")
                run_date = max(giveaway["ends_at"], now)
                self.scheduler.add_job(self.close_giveaway, "date", run_date=run_date, args=[giveaway])

    @schedule_giveaways.before_loop
    async def on_schedule_giveaways_before(self):
        "Wait for the bot to be ready before starting the scheduler"
        await self.bot.wait_until_ready()

    @schedule_giveaways.error
    async def on_schedule_giveaways_error(self, error: BaseException):
        "Log errors from the scheduler"
        self.bot.dispatch("error", error)

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
            message_url = f"https://discord.com/channels/{gaw['guild']}/{gaw['channel']}/{gaw['message']}"
            text += f"- **[{name}]({message_url})**  -  "
            if participants := await self.bot.fb.get_giveaways_participants(gaw["id"]):
                participants_count = len(participants)
                if participants_count == 1:
                    text += "1 participant - "
                else:
                    text += f"{participants_count} participants - "
            else:
                text += "no participant - "
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
        }
        message = await self.send_gaw(target_channel, data)
        await self.bot.fb.create_giveaway({
            **data,
            "message": message.id,
            "winners": [] # gonna be deleted anyway when saved by Firebase
        })
        await interaction.followup.send(f"Giveaway created at {message.jump_url} !")

    async def create_active_gaw_embed(self, data: GiveawayToSendData, participants_count: int=0):
        "Create a Discord embed for an active giveaway"
        embed = discord.Embed(
            title=data["name"],
            description=data["description"],
            color=data["color"],
            timestamp=data["ends_at"]
        )
        if max_entries := data["max_entries"]:
            embed.add_field(name="Participants", value=f"{participants_count}/{max_entries}")
        else:
            embed.add_field(name="Participants", value=str(participants_count))
        embed.set_footer(text="Ends at")
        return embed

    async def send_gaw(self, channel: discord.TextChannel, data: GiveawayToSendData):
        "Send a giveaway message in a given channel"
        embed = await self.create_active_gaw_embed(data)
        view = GiveawayView(self.bot, data, "Join the giveaway!")
        msg = await channel.send(embed=embed, view=view)
        return msg

    async def fetch_gaw_message(self, data: GiveawayData):
        "Fetch the Discord message for a giveaway"
        channel = self.bot.get_channel(data["channel"])
        if not isinstance(channel, discord.TextChannel):
            return None
        try:
            message = await channel.fetch_message(data["message"])
        except discord.NotFound:
            return None
        return message

    async def increase_gaw_embed_participants(self, data: GiveawayData, participants_count: Optional[int]=None):
        "Fetch the Discord message for a giveaway, parse it and increment the participants count"
        message = await self.fetch_gaw_message(data)
        if message is None:
            return
        embed = message.embeds[0]
        if embed.fields[0].value is None:
            return
        field_value = embed.fields[0].value.split('/')
        if participants_count:
            field_value[0] = str(participants_count)
        else:
            field_value[0] = str(int(field_value[0]) + 1)
        embed.set_field_at(0, name="Participants", value="/".join(field_value))
        await message.edit(embed=embed)

    async def register_new_participant(self, interaction: discord.Interaction, giveaway: GiveawayData):
        """Register a new participant to a giveaway (when they click on the Join button)"""
        if await self.bot.fb.check_giveaway_participant(giveaway["id"], interaction.user.id):
            await interaction.followup.send(f"{interaction.user.mention} you already joined the giveaway!", ephemeral=True)
            return
        await self.bot.fb.add_giveaway_participant(giveaway["id"], interaction.user.id)
        await interaction.followup.send(f"{interaction.user.mention} you joined the giveaway, good luck!", ephemeral=True)
        if self.bot.fb.cache.are_participants_sync(giveaway["id"]) and (
                participants := self.bot.fb.cache.get_participants(giveaway["id"])):
            participants_count = len(participants)
        else:
            participants_count = None
        await self.increase_gaw_embed_participants(giveaway, participants_count=participants_count)

    async def close_giveaway(self, data: GiveawayData):
        "Close a giveaway and pick the winners"
        if data["ended"]:
            return
        self.bot.log.info(f"[giveaways] Closing giveaway {data['id']}")
        message = await self.fetch_gaw_message(data)
        if message is None:
            return
        embed = message.embeds[0]
        embed.set_footer(text="Ended at")
        await message.edit(embed=embed)
        # await self.bot.fb.close_giveaway(data["id"])
        # await self.pick_giveaway_winners(data)


async def setup(bot: CObot):
    "Load the cog"
    await bot.add_cog(GiveawaysCog(bot))
