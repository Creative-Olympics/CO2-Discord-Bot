import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from uuid import uuid4

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.app_commands import Choice, Range
from discord.ext import commands, tasks

from src.cobot import CObot, COInteraction
from src.modules.giveaways.types import GiveawayData, GiveawayToSendData
from src.modules.giveaways.views import GiveawayView, ParticipantsPaginator
from src.utils.confirm_view import ConfirmView
from src.utils.custom_args import ColorOption, DateOption, DurationOption

AcceptableChannel = (discord.TextChannel, discord.Thread, discord.StageChannel, discord.VoiceChannel)
AcceptableChannelType = Union[discord.TextChannel, discord.Thread, discord.StageChannel, discord.VoiceChannel]


class GiveawaysCog(commands.Cog):
    "Handle giveaways"

    def __init__(self, bot: CObot):
        self.bot = bot
        self.embed_color = 0x9933ff
        self.scheduler = AsyncIOScheduler()
        self.log = logging.getLogger("cobot.giveaways")

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
                self.log.debug("Scheduling closing of giveaway %s", giveaway['id'])
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
            else:
                participants_count = 0
            if max_entries := gaw.get("max_entries"):
                text += f"{participants_count}/{max_entries} participants - "
            else:
                text += f"{participants_count} participants - "
            max_winners_count = gaw['winners_count']
            if gaw["ended"]:
                winners_count = len(gaw["winners"])
                text += f"{winners_count}/{max_winners_count} winners - "
            else:
                text += f"{max_winners_count} max winners - "
            end_date = discord.utils.format_dt(gaw["ends_at"], "R")
            if gaw["ends_at"] > now:
                text += f"ends {end_date}\n"
            else:
                text += f"ended {end_date}\n"
        if not text:
            text = "No giveaways" if include_stopped else "No active giveaways"
        embed = discord.Embed(
            title=("List of all giveaways" if include_stopped else "List of active giveaways"),
            description=text,
            color=self.embed_color
        )
        await interaction.followup.send(embed=embed)

    @group.command(name="create")
    async def gw_create(self, interaction: COInteraction, *, name: Range[str, 2, 30], description: Range[str, 2, 256],
                        duration: DurationOption, channel: Optional[AcceptableChannelType]=None,
                        color: Optional[ColorOption]=None, max_entries: Optional[int]=None,
                        winners_count: int=1):
        "Create a giveaway"
        if interaction.guild is None:
            return
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, AcceptableChannel):
            await interaction.response.send_message("Giveaways can only be sent in text channels!")
            return
        if target_channel is None:
            return
        bot_perms = target_channel.permissions_for(interaction.guild.me)
        if not (bot_perms.send_messages and bot_perms.embed_links):
            await interaction.response.send_message("I need the permission to send messages and embed links in this channel!")
            return
        await interaction.response.defer()
        ends_date = discord.utils.utcnow() + timedelta(seconds=duration)
        if max_entries is not None and winners_count > max_entries:
            winners_count = max_entries
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

    @group.command(name="delete")
    async def gw_delete(self, interaction: COInteraction, giveaway: str):
        "Permanently delete a giveaway from the database"
        if interaction.guild is None:
            return
        await interaction.response.defer()
        gaw = await self.bot.fb.get_giveaway(giveaway)
        if gaw is None:
            await interaction.followup.send("Giveaway not found!")
            return
        if gaw["guild"] != interaction.guild.id:
            await interaction.followup.send("You can only delete giveaways in your own server!")
            return
        if not gaw["ended"]:
            confirm_view = ConfirmView(
                validation=lambda inter: inter.user.id == interaction.user.id,
                send_confirmation=False
            )
            await interaction.followup.send("This giveaway is still ongoing! Are you sure you want to delete it?",
                                            view=confirm_view)
            await confirm_view.wait()
            if confirm_view.value is None:
                await confirm_view.disable(interaction)
                return
            if not confirm_view.value:
                await confirm_view.disable(interaction)
                return
        await self.bot.fb.delete_giveaway(giveaway)
        await interaction.followup.send("Giveaway deleted!")

    @gw_delete.autocomplete("giveaway")
    async def gw_delete_autocomplete(self, interaction: COInteraction, current: str):
        "Autocomplete for the giveaway argument of the delete command"
        if interaction.guild_id is None:
            return []
        current = current.lower()
        choices: list[tuple[bool, str, Choice[str]]] = []
        async for gaw in self.bot.fb.get_giveaways():
            if gaw["guild"] == interaction.guild_id and current in gaw["name"].lower():
                priority = not gaw["name"].lower().startswith(current)
                choice = Choice(name=gaw["name"], value=gaw["id"])
                choices.append((priority, gaw["name"], choice))
        return [choice for _, _, choice in sorted(choices, key=lambda x: x[0:2])]

    @group.command(name="edit")
    async def gw_edit(self, interaction: COInteraction, giveaway: str, *,
                      name: Optional[ Range[str, 2, 30]]=None, description: Optional[ Range[str, 2, 256]]=None,
                      utc_end_date: Optional[DateOption]=None, color: Optional[ColorOption]=None,
                      max_entries: Optional[int]=None, winners_count: Optional[int]=None):
        "Edit an existing giveaway"
        if interaction.guild is None:
            return
        if all(arg is None for arg in (name, description, utc_end_date, color, max_entries, winners_count)):
            await interaction.response.send_message("You must provide at least one argument to edit!")
            return
        if utc_end_date is not None and utc_end_date < discord.utils.utcnow():
            await interaction.response.send_message("The end date must be in the future!")
            return
        await interaction.response.defer()
        gaw = await self.bot.fb.get_giveaway(giveaway)
        if gaw is None:
            await interaction.followup.send("Giveaway not found!")
            return
        # run basic tests
        if gaw["guild"] != interaction.guild.id:
            await interaction.followup.send("You can only delete giveaways in your own server!")
            return
        if gaw["ended"]:
            await interaction.followup.send("You can't edit an ended giveaway!")
            return
        # edit original data
        gaw = await self._merge_giveaways_data(gaw, name, description, utc_end_date, color, max_entries, winners_count)
        # edit embed
        message = await self.fetch_gaw_message(gaw)
        if message is None:
            await interaction.followup.send("Giveaway message not found!")
            return
        embed = await self.create_active_gaw_embed(gaw)
        await message.edit(embed=embed)
        # edit database
        await self.bot.fb.edit_giveaway(giveaway, gaw)
        await interaction.followup.send("Giveaway edited!")

    @gw_edit.autocomplete("giveaway")
    async def gw_edit_autocomplete(self, interaction: COInteraction, current: str):
        "Autocomplete for the giveaway argument of the edit command"
        if interaction.guild_id is None:
            return []
        current = current.lower()
        choices: list[tuple[bool, str, Choice[str]]] = []
        async for gaw in self.bot.fb.get_giveaways():
            if gaw["guild"] == interaction.guild_id and current in gaw["name"].lower():
                priority = not gaw["name"].lower().startswith(current)
                choice = Choice(name=gaw["name"], value=gaw["id"])
                choices.append((priority, gaw["name"], choice))
        return [choice for _, _, choice in sorted(choices, key=lambda x: x[0:2])]

    @group.command(name="list-participants")
    async def gw_list_participants(self, interaction: COInteraction, giveaway: str):
        "List all participants in a giveaway"
        if interaction.guild is None:
            return
        await interaction.response.defer()
        gaw = await self.bot.fb.get_giveaway(giveaway)
        if gaw is None:
            await interaction.followup.send("Giveaway not found!")
            return
        if gaw["guild"] != interaction.guild.id:
            await interaction.followup.send("You can only list participants of giveaways in your own server!")
            return
        participants = await self.bot.fb.get_giveaways_participants(giveaway)
        if not participants:
            await interaction.followup.send("No participants!")
            return
        view = ParticipantsPaginator(self.bot, self.embed_color, interaction.user, gaw, participants)
        await view.send_init(interaction)

    @gw_list_participants.autocomplete("giveaway")
    async def gw_list_participants_autocomplete(self, interaction: COInteraction, current: str):
        "Autocomplete for the giveaway argument of the list-participants command"
        if interaction.guild_id is None:
            return []
        current = current.lower()
        choices: list[tuple[bool, str, Choice[str]]] = []
        async for gaw in self.bot.fb.get_giveaways():
            if gaw["guild"] == interaction.guild_id and current in gaw["name"].lower():
                priority = not gaw["name"].lower().startswith(current)
                choice = Choice(name=gaw["name"], value=gaw["id"])
                choices.append((priority, gaw["name"], choice))
        return [choice for _, _, choice in sorted(choices, key=lambda x: x[0:2])]

    @group.command(name="reroll")
    async def gw_reroll_winners(self, interaction: COInteraction, giveaway: str):
        "Reroll winners of a giveaway"
        if interaction.guild is None:
            return
        await interaction.response.defer(ephemeral=True)
        gaw = await self.bot.fb.get_giveaway(giveaway)
        if gaw is None:
            await interaction.followup.send("Giveaway not found!")
            return
        if gaw["guild"] != interaction.guild.id:
            await interaction.followup.send("You can only reroll winners of giveaways in your own server!")
            return
        if not gaw["ended"]:
            await interaction.followup.send("You can only reroll winners of ended giveaways!")
            return
        gaw["ended"] = False
        await self.close_giveaway(gaw)
        winners = gaw["winners"]
        if len(winners) == 0:
            txt = "No new winners picked"
        elif len(winners) == 1:
            txt = f"1 new winner picked: <@{winners[0]}>"
        else:
            txt = f"{len(winners)} new winners picked: {' '.join(f'<@{winner}>' for winner in winners)}"
        await interaction.followup.send("Giveaway rerolled!\n" + txt, allowed_mentions=discord.AllowedMentions.none())

    @gw_reroll_winners.autocomplete("giveaway")
    async def gw_reroll_winners_autocomplete(self, interaction: COInteraction, current: str):
        "Autocomplete for the giveaway argument of the reroll command"
        if interaction.guild_id is None:
            return []
        current = current.lower()
        choices: list[tuple[bool, str, Choice[str]]] = []
        async for gaw in self.bot.fb.get_giveaways():
            if gaw["guild"] == interaction.guild_id and gaw["ended"] and current in gaw["name"].lower():
                priority = not gaw["name"].lower().startswith(current)
                choice = Choice(name=gaw["name"], value=gaw["id"])
                choices.append((priority, gaw["name"], choice))
        return [choice for _, _, choice in sorted(choices, key=lambda x: x[0:2])]

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

    async def send_gaw(self, channel: AcceptableChannelType, data: GiveawayToSendData):
        "Send a giveaway message in a given channel"
        embed = await self.create_active_gaw_embed(data)
        view = GiveawayView(self.bot, data, "Join the giveaway!")
        msg = await channel.send(embed=embed, view=view)
        return msg

    async def fetch_gaw_message(self, data: GiveawayData):
        "Fetch the Discord message for a giveaway"
        channel = self.bot.get_channel(data["channel"])
        if not isinstance(channel, AcceptableChannel):
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
        if max_entries := giveaway.get("max_entries"):
            participants = await self.bot.fb.get_giveaways_participants(giveaway["id"])
            if participants is not None and len(participants) >= max_entries:
                await interaction.followup.send(
                    f"{interaction.user.mention} the limit of participants for this giveaway has been reached! \
Maybe you'll be luckier next time...",
                    ephemeral=True
                )
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
        self.log.info("Closing giveaway %s", data['id'])
        message = await self.fetch_gaw_message(data)
        if message is None:
            return
        # edit initial embed
        embed = message.embeds[0]
        embed.set_footer(text="Ended at")
        winners = await self.pick_giveaway_winners(data)
        if len(winners) == 0:
            embed.add_field(name="Winners", value="No one joined the giveaway...")
        elif len(winners) < 35:
            embed.add_field(name="Winners", value=", ".join(f"<@{winner}>" for winner in winners))
        else:
            embed.add_field(name="Winners", value=f"{len(winners)} winners picked")
        await message.edit(embed=embed, view=None)
        # send a new message mentionning winners
        if len(winners) == 1:
            await message.reply(
                f"The winner of the **{data['name']}** giveaways has been picked!\nCongratulations to <@{winners[0]}>!",
            )
        elif len(winners) != 0:
            winners_mentions = " ".join(f"<@{winner}>" for winner in winners)
            await message.reply(
                f"The winners of the **{data['name']}** giveaways have been picked!\nCongratulations to {winners_mentions}!",
            )
        else:
            await message.reply(
                f"Unfortunately, no one joined the **{data['name']}** giveaways...\nBetter luck next time!",
            )
        # mark the giveaway as ended in the database
        await self.bot.fb.close_giveaway(data["id"], winners)

    async def pick_giveaway_winners(self, data: GiveawayData) -> list[int]:
        "Fetch participants of a giveaway and randomly pick winners"
        participants = await self.bot.fb.get_giveaways_participants(data["id"])
        if not participants:
            return []
        winners_count = min(data["winners_count"], len(participants))
        return random.sample(participants, winners_count)

    async def _merge_giveaways_data(self, original_data: GiveawayData,
                                    name: Optional[str], description: Optional[str],
                                    utc_end_date: Optional[datetime], color: Optional[discord.Colour],
                                    max_entries: Optional[int], winners_count: Optional[int]) -> GiveawayData:
        "Update a given giveaway data with new values"
        if name is not None:
            original_data["name"] = name
        if description is not None:
            original_data["description"] = description
        if utc_end_date is not None:
            original_data["ends_at"] = utc_end_date.astimezone(timezone.utc)
        if color is not None:
            original_data["color"] = color.value
        if max_entries is not None:
            original_data["max_entries"] = max_entries
        if winners_count is not None:
            original_data["winners_count"] = winners_count
        return original_data



async def setup(bot: CObot):
    "Load the cog"
    await bot.add_cog(GiveawaysCog(bot))
