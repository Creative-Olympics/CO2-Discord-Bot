import sys
from typing import Optional, Union

import discord
from discord.ext import commands

from src.firebase.client import FirebaseDB

from .boot_utils import setup_logger
from .config import Config


class CObot(commands.Bot):
    "Bot class, with everything required to run it"

    user: discord.ClientUser # type override because we consider the bot will always be logged in, as long as used

    def __init__(self, status: discord.Status, beta: bool):
        allowed_mentions = discord.AllowedMentions(everyone=False, roles=False)
        intents = discord.Intents.default()
        intents.typing = False
        intents.webhooks = False
        intents.integrations = False
        intents.members = True
        intents.presences = True
        self.config = Config() # load config from .json file
        owner_ids = self.config["ADMIN_IDS"]
        super().__init__(command_prefix=commands.when_mentioned, owner_ids=owner_ids, status=status,
                         allowed_mentions=allowed_mentions, intents=intents, enable_debug_events=True)
        self.beta = beta # if the bot is in beta mode
        self.log = setup_logger() # logs module
        self.zws = "\u200B"  # here's a zero width space
        self.fb = FirebaseDB("firebaseServiceAccount.json") # firebase client
        # app commands
        self.tree.on_error = self.on_app_cmd_error
        self.app_commands_list: Optional[list[discord.app_commands.AppCommand]] = None


    async def on_error(self, event_method: Union[Exception, str], *_args, **_kwargs):
        "Called when an event listener raises an uncaught exception"
        if isinstance(event_method, str) and event_method.startswith("on_") and event_method != "on_error":
            _, error, _ = sys.exc_info()
            self.dispatch("error", error, f"While handling event `{event_method}`")

    async def on_app_cmd_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        self.dispatch("interaction_error", interaction, error)

    async def fetch_app_commands(self):
        "Populate the app_commands_list attribute from the Discord API"
        self.app_commands_list = await self.tree.fetch_commands(guild=None)

    async def fetch_app_command_by_name(self, name: str) -> Optional[discord.app_commands.AppCommand]:
        "Get a specific app command from the Discord API"
        if self.app_commands_list is None:
            await self.fetch_app_commands()
        if self.app_commands_list is None:
            raise RuntimeError("app_commands_list is still None after fetching commands")
        for command in self.app_commands_list:
            if command.name == name:
                return command
        return None

    async def get_command_mention(self, command_name: str):
        "Get how a command should be mentionned (either app-command mention or raw name)"
        if command := await self.fetch_app_command_by_name(command_name.split(' ')[0]):
            return f"</{command_name}:{command.id}>"
        if command := self.get_command(command_name):
            return f"`{command.qualified_name}`"
        self.log.error("Trying to mention invalid command: %s", command_name)
        return f"`{command_name}`"


COInteraction = discord.Interaction[CObot] # use generic interaction class with custom bot class
