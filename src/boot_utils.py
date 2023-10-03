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
    # console logging
    stream_handler = logging.StreamHandler(sys.stdout)
    # file logging
    file_handler = RotatingFileHandler("logs/debug.log", maxBytes=int(1e6), backupCount=2, delay=True)

    log_format = logging.Formatter(
        "[{asctime}] {levelname:<7}: [{name}] {message}",
        datefmt="%Y-%m-%d %H:%M:%S", style='{'
    )

    file_handler.setFormatter(log_format)
    stream_handler.setFormatter(log_format)

    # add handlers to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    root_logger.setLevel(logging.INFO)

    # set cobot logger to debug
    logging.getLogger("cobot").setLevel(logging.DEBUG)

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
