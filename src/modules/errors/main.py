import logging
import os
import sys
import traceback
from typing import Optional, Union

import discord
from discord.ext import commands, tasks

from src.cobot import CObot, COInteraction

AllowedCtx = Union[commands.Context, discord.Message, COInteraction, str]

def get_channel_name(ctx: Union[commands.Context, discord.Message, COInteraction]):
    "Compute the name of the channel from a given error context"
    if ctx.channel is None or isinstance(ctx.channel, discord.PartialMessageable):
        return "unknown channel"
    if isinstance(ctx.channel, discord.DMChannel):
        if ctx.channel.recipient is None:
            return "unknown DM"
        return "DM with " + ctx.channel.recipient.name
    if ctx.channel.name is None:
        return "unknown channel"
    return ctx.channel.name

class ErrorsCog(commands.Cog):
    "Handle error events"

    def __init__(self, bot: CObot):
        self.bot = bot
        # map of user ID and number of cooldown errors recently hit
        self.cooldown_pool: dict[int, int] = {}
        self.log = logging.getLogger("cobot.errors")

    async def cog_load(self):
        # pylint: disable=no-member
        self.reduce_cooldown_pool.start()

    async def cog_unload(self):
        # pylint: disable=no-member
        if self.reduce_cooldown_pool.is_running():
            self.reduce_cooldown_pool.cancel()

    @tasks.loop(seconds=5)
    async def reduce_cooldown_pool(self):
        "Reduce the cooldown score by 1 every 5 seconds"
        to_delete: set[int] = set()
        for user_id in self.cooldown_pool:
            self.cooldown_pool[user_id] -= 1
            if self.cooldown_pool[user_id] <= 0:
                to_delete.add(user_id)
        for user_id in to_delete:
            del self.cooldown_pool[user_id]

    @reduce_cooldown_pool.error
    async def on_reduce_cooldown_pool_error(self, error: BaseException):
        "Log errors from the reduce_cooldown_pool task"
        self.bot.dispatch("error", error)

    async def can_send_cooldown_error(self, user_id: int):
        "Check if we can send a cooldown error to a user, to avoid spam"
        spam_score = self.cooldown_pool.get(user_id, 0)
        self.cooldown_pool[user_id] = spam_score + 1
        return spam_score < 4


    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """The event triggered when an error is raised while invoking a prefix-based command"""
        # This prevents any commands with local handlers being handled here in on_command_error.
        if hasattr(ctx.command, 'on_error'):
            return

        ignored = (
            commands.errors.CommandNotFound,
            commands.errors.CheckFailure,
            commands.errors.ConversionError,
            discord.errors.Forbidden
        )
        actually_not_ignored = (commands.errors.NoPrivateMessage,)

        # Allows us to check for original exceptions raised and sent to CommandInvokeError.
        # If nothing is found. We keep the exception passed to on_command_error.
        error = getattr(error, 'original', error)

         # Anything in ignored will return and prevent anything happening.
        if isinstance(error, ignored) and not isinstance(error, actually_not_ignored):
            if isinstance(error, commands.CheckFailure) and ctx.interaction:
                await ctx.send(
                    "Oops, it looks like you're not allowed to use this command. Contact our staff to find out why!",
                    ephemeral=True)
            if self.bot.beta and ctx.guild:
                await ctx.send(f"`Ignored error:` [{error.__class__.__module__}.{error.__class__.__name__}] {error}")
            return
        elif isinstance(error, commands.ExpectedClosingQuoteError):
            await ctx.send(
                "Oops, a quotation mark error has occured. Be sure to correctly use the quotes \" so that each open quote will be closed further on.",
                ephemeral=True)
            return
        elif isinstance(error, commands.errors.CommandOnCooldown):
            if await self.can_send_cooldown_error(ctx.author.id):
                delay = round(error.retry_after, 2 if error.retry_after < 60 else None)
                await ctx.send(
                    f"You are on cooldown for this command :confused: Please wait %{delay} more seconds...",
                    ephemeral=True)
            return
        elif isinstance(error, commands.BadLiteralArgument):
            await ctx.send(
                "Oops, unknown argument detected",
                ephemeral=True)
            return
        elif isinstance(error,commands.errors.MissingRequiredArgument):
            await ctx.send(
                f"Oops, the {error.param.name} argument is missing :eyes:",
                ephemeral=True)
            return
        elif isinstance(error,commands.errors.DisabledCommand):
            await ctx.send(
                f"The command {ctx.invoked_with} is currently disabled :confused:",
                ephemeral=True)
            return
        elif isinstance(error,commands.errors.NoPrivateMessage):
            await ctx.send(
                "Oops, this command cannot be used in private messages :confused:",
                ephemeral=True)
            return

        # All other Errors not returned come here... And we can just print the default TraceBack.
        self.log.warning('Ignoring exception in command %s:', ctx.message.content)
        await self.on_error(error,ctx)

    @commands.Cog.listener()
    async def on_interaction_error(self, interaction: COInteraction, error: BaseException):
        "Called when an error is raised during an interaction"
        send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            if await self.can_send_cooldown_error(interaction.user.id):
                delay = round(error.retry_after, 2 if error.retry_after < 60 else None)
                await send(
                    f"You are on cooldown for this command :confused: Please wait %{delay} more seconds...",
                    ephemeral=True)
            return
        if isinstance(error, discord.app_commands.CheckFailure):
            await send("Oops, it looks like you're not allowed to use this command. Contact our staff to find out why!", 
                       ephemeral=True)
        if interaction.guild:
            guild = f"{interaction.guild.name} | {get_channel_name(interaction)}"
        elif interaction.guild_id:
            guild = f"guild {interaction.guild_id}"
        else:
            guild = f"DM with {interaction.user}"
        if interaction.type == discord.InteractionType.application_command:
            await self.on_error(error, interaction)
        elif interaction.type == discord.InteractionType.ping:
            await self.on_error(error, f"Ping interaction | {guild}")
        elif interaction.type == discord.InteractionType.modal_submit:
            await self.on_error(error, f"Modal submission interaction | {guild}")
        elif interaction.type == discord.InteractionType.component:
            await self.on_error(error, f"Component interaction | {guild}")
        elif interaction.type == discord.InteractionType.autocomplete:
            await self.on_error(error, f"Command autocompletion | {guild}")
        else:
            self.log.warning("Unhandled interaction error type: %s", interaction.type)
            await self.on_error(error, None)
        await send("Oops, an error occured while executing this command :confused:", ephemeral=True)

    
    @commands.Cog.listener()
    async def on_error(self, error: BaseException, ctx: Optional[AllowedCtx] = None):
        """Called when an error is raised
        
        Its only purpose is to log the error, ctx parameter is only used for traceability"""
        if sys.exc_info()[0] is None:
            exc_info = (type(error), error, error.__traceback__)
        else:
            exc_info = sys.exc_info()
        try:
            # if this is only an interaction too slow, don't report in bug channel
            if isinstance(error, discord.NotFound) and error.text == "Unknown interaction":
                self.log.warning(error, exc_info=exc_info)
                return
            # get traceback info
            if isinstance(ctx, discord.Message):
                ctx = await self.bot.get_context(ctx)
            trace = " ".join(traceback.format_exception(*exc_info))
            trace = trace.replace(os.getcwd(), ".")
            # get context clue
            if ctx is None:
                context = "Internal error"
            elif isinstance(ctx, str):
                context = ctx
            elif ctx.guild is None:
                recipient = ctx.user if isinstance(ctx, discord.Interaction) else ctx.author
                context = f"DM with {recipient}"
            elif isinstance(ctx, discord.Interaction):
                cmd_name = ctx.command.name if ctx.command else "unknown command"
                channel_name = get_channel_name(ctx)
                context = f"Slash command `{cmd_name}` | {ctx.guild.name} | {channel_name}"
            else:
                channel_name = get_channel_name(ctx)
                context = f"{ctx.guild.name} | {channel_name}"
            await self.send_error_msg_autoformat(context, trace)
            self.log.warning(error, exc_info=exc_info)
        except Exception as err: # pylint: disable=broad-except
            self.log.error(err, exc_info=sys.exc_info())

    async def send_error_msg_autoformat(self, context: str, python_message: str):
        """Envoie un message dans le salon d'erreur"""
        success = True
        for i in range(0, len(python_message), 1950):
            if i == 0:
                msg = context + f"\n```py\n{python_message[i:i+1950]}\n```"
            else:
                msg = f"```py\n{python_message[i:i+1950]}\n```"
            success = success and await self.senf_err_msg(msg)
        return success

    async def senf_err_msg(self, msg: str):
        """Envoie un message dans le salon d'erreur"""
        errors_channel: discord.TextChannel = self.bot.get_channel(self.bot.config["ERRORS_CHANNEL_ID"]) # type: ignore
        if errors_channel is None:
            self.log.critical("Cannot find errors channel")
            return False
        if len(msg) > 2000:
            if msg.endswith("```"):
                msg = msg[:1997]+"```"
            else:
                msg = msg[:2000]
        await errors_channel.send(msg)
        return True


async def setup(bot: CObot):
    await bot.add_cog(ErrorsCog(bot))
