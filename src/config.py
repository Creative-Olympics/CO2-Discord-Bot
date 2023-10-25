import json
from typing import Literal, TypedDict, overload

import discord


class _ConfigType(TypedDict):
    DISCORD_RELEASE_TOKEN: str
    DISCORD_BETA_TOKEN: str
    MAIN_GUILD_ID: int
    ERRORS_CHANNEL_ID: int
    ADMIN_IDS: list[int]
    FIREBASE_REALTIME_DATABASE_URL: str
    FIREBASE_REALTIME_AUTH_UUID: str
    DONATION_URL: str


class Config:
    "Load the config.json file and check its integrity"

    def __init__(self):
        with open("config.json", "r", encoding="utf-8") as file:
            self.data: _ConfigType = json.load(file)
        self.check_integrity()

    @overload
    def __getitem__(self, key: Literal["DISCORD_RELEASE_TOKEN"]) -> str: ...

    @overload
    def __getitem__(self, key: Literal["DISCORD_BETA_TOKEN"]) -> str: ...

    @overload
    def __getitem__(self, key: Literal["MAIN_GUILD_ID"]) -> int: ...

    @overload
    def __getitem__(self, key: Literal["ERRORS_CHANNEL_ID"]) -> int: ...

    @overload
    def __getitem__(self, key: Literal["ADMIN_IDS"]) -> list[int]: ...

    @overload
    def __getitem__(self, key: Literal["FIREBASE_REALTIME_DATABASE_URL"]) -> str: ...

    @overload
    def __getitem__(self, key: Literal["FIREBASE_REALTIME_AUTH_UUID"]) -> str: ...

    @overload
    def __getitem__(self, key: Literal["DONATION_URL"]) -> str: ...

    def __getitem__(self, key: str):
        return self.data[key]

    def check_integrity(self):
        "Check if the loaded config is valid (ie. respects the typing class)"
        if not isinstance(self.data, dict):
            raise TypeError("config.json is not a dict")
        for key in _ConfigType.__annotations__: # pylint: disable=no-member
            if key not in self.data:
                raise KeyError(f"config.json is missing key {key}")
            annotation_value = _ConfigType.__annotations__[key] # pylint: disable=no-member
            if hasattr(annotation_value, "__origin__"):
                annotation_value = annotation_value.__origin__
            if not isinstance(self.data[key], annotation_value):
                raise TypeError(
                    f"config.json key {key} is not of type {annotation_value}")
        for user_id in self.data["ADMIN_IDS"]:
            if not isinstance(user_id, int):
                raise TypeError("config.json key ADMIN_IDS contains non-integers")

def get_guild_snowflake_object():
    "Create a discord.Object from the MAIN_GUILD_ID key in config.json"
    with open("config.json", "r", encoding="utf-8") as file:
        data: _ConfigType = json.load(file)
    guild_id = data["MAIN_GUILD_ID"]
    if not isinstance(guild_id, int):
        raise TypeError("config.json key MAIN_GUILD_ID is not an integer")
    return discord.Object(id=guild_id)

GUILD_ID = get_guild_snowflake_object()


if __name__ == "__main__":
    config = Config()
    # will automatically run the integrity check
