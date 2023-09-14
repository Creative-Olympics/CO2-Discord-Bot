import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

import discord
from LRFutils import progress

if TYPE_CHECKING:
    from .cobot import CObot


def setup_start_parser():
    "Create a parser for the command-line interface"
    parser = argparse.ArgumentParser()
    parser.add_argument('--beta', '-b', help="Use the beta bot instead of the release", action="store_true")

    return parser

def setup_logger():
    """Setup the logger used by the bot
    It should use both console and a debug file"""
    log = logging.getLogger("cobot")
    log_format = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", datefmt="[%d/%m/%Y %H:%M:%S]")

    # file logging
    file_handler = RotatingFileHandler("logs/debug.log", maxBytes=int(1e6), backupCount=2, delay=True)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)

    # console logging
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(log_format)

    log.addHandler(file_handler)
    log.addHandler(stream_handler)

    log.setLevel(logging.DEBUG)
    return log

async def load_cogs(bot: "CObot"):
    "Load the bot modules"
    extensions = [
        "admin",
        "errors",
        "giveaways",
    ]
    progress_bar = progress.Bar(max=len(extensions), width=60, prefix="Loading extensions", eta=False, show_duration=False)

    # Here we load our extensions (cogs) listed above in [extensions]
    count = 0
    for i, extension in enumerate(extensions):
        progress_bar(i)
        try:
            await bot.load_extension(f"src.modules.{extension}.main")
        except discord.DiscordException:
            bot.log.critical('Failed to load extension %s', extension, exc_info=True)
            count += 1
        if count  > 0:
            bot.log.critical("%s modules not loaded\nEnd of program", count)
            sys.exit()
    progress_bar(len(extensions), stop=True)
