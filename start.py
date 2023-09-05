#!/usr/bin/env python
#coding=utf-8

# check python version
import sys
py_version = sys.version_info
if py_version.major != 3 or py_version.minor < 9:
    print("You must use at least Python 3.9!", file=sys.stderr)
    sys.exit(1)

import pkg_resources

def check_libs():
    """Check if the required libraries are installed and can be imported"""
    with open("requirements.txt", 'r', encoding="utf-8") as file:
        packages = pkg_resources.parse_requirements(file.readlines())
    pkg_resources.working_set.resolve(packages)


check_libs()

import discord
import asyncio

from src.boot_utils import load_cogs, setup_start_parser
from src.cobot import CObot


async def main():
    "Instanciate and start the bot"
    parser = setup_start_parser()
    args = parser.parse_args()
    if not isinstance(args.beta, bool):
        raise TypeError("Beta argument must be a boolean")

    client = CObot(status=discord.Status.online, beta=args.beta)
    client.log.info("Starting bot")

    @client.event
    async def on_ready():
        client.log.info("Bot is ready")
        print("Name:", client.user)
        print("ID:", client.user.id)
        guild_names = (x.name for x in client.guilds)
        print("Connected on ["+str(len(client.guilds))+"] "+", ".join(guild_names))
        print('------')

    async with client:
        await load_cogs(client)
        if args.beta:
            token = client.config["DISCORD_BETA_TOKEN"]
        else:
            token = client.config["DISCORD_RELEASE_TOKEN"]
        await client.start(token)


if __name__ == "__main__":
    asyncio.run(main())
