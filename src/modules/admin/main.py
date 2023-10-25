import io
import logging
import os
import sys
import textwrap
import time
import traceback
from contextlib import redirect_stdout
from typing import Any, Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands
from git import GitCommandError
from git.repo import Repo

from src.cobot import CObot, COInteraction
from src.utils.checks import is_bot_admin


def cleanup_code(content: str):
    """Automatically removes code blocks from the code."""
    # remove ```py\n```
    if content.startswith('```') and content.endswith('```'):
        return '\n'.join(content.split('\n')[1:-1])
    # remove `foo`
    return content.strip('` \n')


class AdminCog(commands.Cog):
    "A few commands to manage the bot"

    def __init__(self, bot: CObot):
        self.bot = bot
        self._last_result: Any = None
        self.log = logging.getLogger("cobot.admin")

    group = discord.app_commands.Group(
        name="admin",
        description="Admin commands to manage the bot",
        default_permissions=discord.Permissions(administrator=True)
    )

    async def cleanup_workspace(self):
        "Delete python cache files"
        for folder_name, _, filenames in os.walk('.'):
            for filename in filenames:
                if filename.endswith('.pyc'):
                    os.unlink(folder_name+'/'+filename)
            if  folder_name.endswith('__pycache__'):
                os.rmdir(folder_name)

    @group.command(name="pull")
    @app_commands.check(is_bot_admin)
    async def git_pull(self, interaction: COInteraction, branch: Optional[str]=None, install_requirements: bool=False):
        """Pull du code depuis le dépôt git"""
        txt = "Pulling the branch"
        await interaction.response.send_message(txt)
        repo = Repo(os.getcwd())
        assert not repo.bare
        if branch:
            try:
                repo.git.checkout(branch)
            except GitCommandError as err:
                self.bot.dispatch("interaction_error", interaction, err)
            else:
                txt += f"\nGit branch '{branch}' has been selected"
                await interaction.edit_original_response(content=txt)
        origin = repo.remotes.origin
        origin.pull()
        txt += f"\nGit pull done on branch {repo.active_branch.name}"
        await interaction.edit_original_response(content=txt)
        if install_requirements:
            txt += "\nInstalling requirements..."
            await interaction.edit_original_response(content=txt)
            os.system("pip install -qr requirements.txt")
            txt += "\nRequirements installed"
            await interaction.edit_original_response(content=txt)

    @group.command(name="reboot")
    @app_commands.check(is_bot_admin)
    async def reboot(self, interaction: COInteraction):
        "Restart the bot"
        await interaction.response.send_message(content="Reboot in progress...")
        await self.cleanup_workspace()
        self.log.info("Restarting the process")
        os.execl(sys.executable, sys.executable, *sys.argv)

    @group.command(name="shutdown")
    @app_commands.check(is_bot_admin)
    async def shutdown(self, interaction: COInteraction):
        "Shutdown the whole program"
        await interaction.response.send_message("Cleaning up...")
        await self.cleanup_workspace()
        await interaction.edit_original_response(content="Shutting down...")
        await self.bot.change_presence(status=discord.Status('offline'))
        self.log.info("Shutting down the process, requested by %s", interaction.user)
        await self.bot.close()

    @group.command(name="sync-commands")
    @app_commands.check(is_bot_admin)
    async def sync_app_commands(self, interaction: COInteraction):
        "Sync app commands"
        await interaction.response.defer()
        cmds = await self.bot.tree.sync()
        txt = f"{len(cmds)} global commands synced"
        self.log.info(txt)
        await interaction.followup.send(txt + '!')

    @group.command(name="change-activity")
    async def change_activity(self, _interaction: COInteraction,
                              activity_type: Literal["play", "watch", "listen", "stream"], *, text: str):
        "Change the bot status activity"
        if activity_type == "play":
            activity = discord.Game(name=text)
        elif activity_type == "watch":
            activity = discord.Activity(type=discord.ActivityType.watching, name=text, timestamps={'start':time.time()})
        elif activity_type == "listen":
            activity = activity=discord.Activity(type=discord.ActivityType.listening, name=text, timestamps={'start':time.time()})
        elif activity_type == "stream":
            activity = discord.Activity(type=discord.ActivityType.streaming, name=text, timestamps={'start':time.time()})
        await self.bot.change_presence(activity=activity)


    @commands.command(name='eval', hidden=True)
    @commands.is_owner()
    async def _eval(self, ctx: commands.Context, *, body: str):
        """Evaluates a code
        Credits: Rapptz (https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/admin.py)"""
        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }
        env.update(globals())

        body = cleanup_code(body)
        stdout = io.StringIO()
        try:
            to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'
        except Exception as err: # pylint: disable=broad-except
            self.bot.dispatch("error", err, ctx)
            return
        try:
            exec(to_compile, env) # pylint: disable=exec-used
        except Exception as err: # pylint: disable=broad-except
            return await ctx.reply(f'```py\n{err.__class__.__name__}: {err}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as err: # pylint: disable=broad-except
            value = stdout.getvalue()
            await ctx.reply(f'```py\n{value}{traceback.format_exc()[:1990]}\n```')
        else:
            value = stdout.getvalue()
            await ctx.message.add_reaction('\u2705')

            if ret is None:
                if value:
                    await ctx.reply(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                await ctx.reply(f'```py\n{value}{ret}\n```')


    @app_commands.command(name="ping")
    @app_commands.checks.cooldown(3, 15)
    async def ping(self, interaction: COInteraction):
        """Pong!"""
        await interaction.response.send_message("Ping...")
        msg = await interaction.original_response()
        bot_delta = (msg.created_at - interaction.created_at).total_seconds()
        try:
            api_latency = round(self.bot.latency*1000)
        except OverflowError:
            api_latency = "∞"
        await msg.edit(content=f":ping_pong:  Pong!\nBot ping: {bot_delta*1000:.0f}ms\nDiscord ping: {api_latency}ms")


async def setup(bot: CObot):
    await bot.add_cog(AdminCog(bot))
