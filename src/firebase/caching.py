import discord
from src.modules.giveaways.types import GiveawayData


class FirebaseCacheControler:
    """Controls the cache for the Firebase requests"""

    def __init__(self):
        self.participants_cache: dict[str, list[int]] = {}
        self.__synced_participants_giveaways: set[str] = set()
        self.giveaways_cache: dict[str, GiveawayData] = {}
        self.__are_giveaways_sync = False
        self.__are_active_giveaways_sync = False

    def are_participants_sync(self, giveaway_id: str):
        "Are the participants cached?"
        return giveaway_id in self.__synced_participants_giveaways

    @property
    def are_giveaways_sync(self):
        "Are the giveaways cached?"
        return self.__are_giveaways_sync

    @property
    def are_active_giveaways_sync(self):
        "Are the active giveaways cached?"
        return self.__are_active_giveaways_sync or self.__are_giveaways_sync

    def get_participants(self, giveaway_id: str):
        "Get the participants for a giveaway"
        return self.participants_cache.get(giveaway_id)

    def get_giveaway(self, giveaway_id: str):
        "Get a giveaway"
        return self.giveaways_cache.get(giveaway_id)

    def get_giveaways(self):
        "Get all giveaways"
        return self.giveaways_cache.values()

    def get_active_giveaways(self):
        "Get all active giveaways"
        return filter(lambda g: not g["ended"], self.giveaways_cache.values())

    def get_pending_giveaways(self):
        "Get all active giveaways whose end date is in the past"
        now = discord.utils.utcnow()
        return filter(lambda g: not g["ended"] and g["ends_at"] < now, self.giveaways_cache.values())

    def set_participants(self, giveaway_id: str, participants: list[int]):
        "Set the participants for all giveaways"
        self.participants_cache[giveaway_id] = participants
        self.__synced_participants_giveaways.add(giveaway_id)

    def add_participant(self, giveaway_id: str, participant: int):
        "Add a participant to a giveaway, if the full list is already cached"
        if participants := self.participants_cache.get(giveaway_id):
            participants.append(participant)

    def set_giveaways(self, giveaways: list[GiveawayData]):
        "Set the giveaways"
        self.giveaways_cache = {g["id"]: g for g in giveaways}
        self.__are_giveaways_sync = True

    def set_active_giveaways(self, giveaways: list[GiveawayData]):
        "Set the active giveaways"
        self.giveaways_cache = {g["id"]: g for g in giveaways}
        self.__are_active_giveaways_sync = True

    def set_new_giveaway(self, giveaway: GiveawayData):
        "Set a new giveaway"
        self.giveaways_cache[giveaway["id"]] = giveaway
        self.participants_cache[giveaway["id"]] = []
        self.__synced_participants_giveaways.add(giveaway["id"])

    def set_existing_giveaway(self, giveaway: GiveawayData):
        "Set an existing giveaway"
        self.giveaways_cache[giveaway["id"]] = giveaway

    def close_giveaway(self, giveaway_id: str):
        "Close a giveaway"
        if giveaway_id in self.giveaways_cache:
            self.giveaways_cache[giveaway_id]["ended"] = True
