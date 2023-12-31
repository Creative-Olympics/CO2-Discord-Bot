import logging
import time
from datetime import datetime as dt
from typing import AsyncGenerator, Literal, Optional

import firebase_admin
from firebase_admin import credentials, db

from src.firebase.caching import FirebaseCacheControler
from src.firebase.rc_rest_api import RemoteConfigClient
from src.modules.giveaways.types import GiveawayData, RawGiveawayData


class FirebaseDB:
    "Firebase client class to access the database"

    def __init__(self, config_filename: str, realtime_url: str):
        cred = credentials.Certificate(config_filename)
        self.app = firebase_admin.initialize_app(cred, {
            'databaseURL': realtime_url,
        })
        self.rc = RemoteConfigClient(cred)
        self.cache = FirebaseCacheControler()
        self.log = logging.getLogger("cobot.firebase")

    async def get_giveaways(self) -> AsyncGenerator[GiveawayData, None]:
        "Get a generator of giveaway documents"
        if self.cache.are_giveaways_sync:
            for gaw in self.cache.get_giveaways():
                yield gaw
            return
        self.log.debug("Fetching giveaways")
        ref = db.reference("giveaways")
        snapshot: dict[str, RawGiveawayData] = ref.get() # type: ignore
        parsed_giveaways: list[GiveawayData] = [
            {
                **gaw, # type: ignore
                "id": gaw_id,
                "ends_at": dt.fromisoformat(gaw["ends_at"]),
                "winners": gaw.get("winners", [])
            }
            for gaw_id, gaw in snapshot.items()
        ]
        self.cache.set_giveaways(parsed_giveaways)
        for data in parsed_giveaways:
            yield data

    async def get_active_giveaways(self) -> AsyncGenerator[GiveawayData, None]:
        """Get a generator of active giveaway documents (ie. not 'ended')
        Note: this may include giveaways that have a past end date but have not been marked as ended yet"""
        if self.cache.are_active_giveaways_sync:
            for gaw in self.cache.get_active_giveaways():
                yield gaw
            return
        self.log.debug("Fetching active giveaways")
        ref = db.reference("giveaways")
        snapshot: dict[str, RawGiveawayData] = ref.order_by_child("ended").equal_to(False).get() # type: ignore
        parsed_giveaways: list[GiveawayData] = [
            {
                **gaw, # type: ignore
                "id": gaw_id,
                "ends_at": dt.fromisoformat(gaw["ends_at"]),
                "winners": gaw.get("winners", [])
            }
            for gaw_id, gaw in snapshot.items()
        ]
        self.cache.set_active_giveaways(parsed_giveaways)
        for data in parsed_giveaways:
            yield data

    async def get_giveaway(self, giveaway_id: str) -> Optional[GiveawayData]:
        "Get a giveaway document"
        if gaw := self.cache.get_giveaway(giveaway_id):
            return gaw
        self.log.debug("Fetching giveaway %s", giveaway_id)
        ref = db.reference(f"giveaways/{giveaway_id}")
        snapshot: Optional[RawGiveawayData] = ref.get() # type: ignore
        if snapshot is None:
            return None
        data: GiveawayData = {
            **snapshot, # type: ignore
            "id": giveaway_id,
            "ends_at": dt.fromisoformat(snapshot["ends_at"]),
            "winners": snapshot.get("winners", [])
        }
        self.cache.set_existing_giveaway(data)
        return data

    async def create_giveaway(self, data: GiveawayData):
        "Create a giveaway document"
        self.log.info("Creating new giveaway %s", data["id"])
        ref = db.reference("giveaways")
        ref.child(data["id"]).set({
            **data,
            "ends_at": data["ends_at"].isoformat()
        })
        self.cache.set_new_giveaway(data)

    async def close_giveaway(self, giveaway_id: str, winners: list[int]):
        "Mark a giveaway as ended"
        self.log.info("Marking giveaway %s as ended", giveaway_id)
        ref = db.reference(f"giveaways/{giveaway_id}")
        ref.update({
            "ended": True,
            "winners": winners
        })
        self.cache.close_giveaway(giveaway_id, winners)

    async def delete_giveaway(self, giveaway_id: str):
        "Delete a giveaway document and its participants"
        self.log.info("Deleting giveaway %s", giveaway_id)
        # remove giveaway entry
        ref = db.reference(f"giveaways/{giveaway_id}")
        ref.delete()
        # remove participants list
        ref = db.reference(f"giveaways_participants/{giveaway_id}")
        ref.delete()
        # update cache
        self.cache.delete_giveaway(giveaway_id)

    async def edit_giveaway(self, giveaway_id: str, data: GiveawayData):
        "Edit a giveaway document"
        self.log.info("Editing giveaway %s", giveaway_id)
        ref = db.reference(f"giveaways/{giveaway_id}")
        ref.update({
            **data,
            "ends_at": data["ends_at"].isoformat()
        })
        self.cache.edit_giveaway(giveaway_id, data)

    async def get_giveaways_participants(self, giveaway_id: str) -> Optional[list[int]]:
        "Get a list of participants for a giveaway"
        if self.cache.are_participants_sync(giveaway_id):
            return self.cache.get_participants(giveaway_id)
        self.log.debug("Fetching participants for giveaway %s", giveaway_id)
        ref = db.reference(f"giveaways_participants/{giveaway_id}")
        snapshot: Optional[dict[str, Literal[True]]] = ref.get() # type: ignore
        if snapshot is None:
            return None
        participants = [int(user_id) for user_id in snapshot.keys()]
        self.cache.set_participants(giveaway_id, participants)
        return participants

    async def check_giveaway_participant(self, giveaway_id: str, user_id: int) -> bool:
        "Check if a user is a participant of a giveaway"
        if self.cache.are_participants_sync(giveaway_id):
            if participants := self.cache.get_participants(giveaway_id):
                return user_id in participants
        self.log.debug("Fetching participant %s for giveaway %s", user_id, giveaway_id)
        ref = db.reference(f"giveaways_participants/{giveaway_id}/{user_id}")
        snapshot: Optional[Literal[True]] = ref.get() # type: ignore
        return snapshot is not None

    async def add_giveaway_participant(self, giveaway_id: str, user_id: int):
        "Add a participant to a giveaway"
        self.log.debug("Adding participant %s to giveaway %s", user_id, giveaway_id)
        ref = db.reference(f"giveaways_participants/{giveaway_id}/{user_id}")
        ref.set(True)
        self.cache.add_participant(giveaway_id, user_id)


    async def get_event_start_timestamp(self) -> Optional[int]:
        "Get the event start date"
        if ts := self.cache.event_start_timestamp:
            return ts
        self.log.debug("Fetching event start date from RC")
        value = await self.rc.get_parameter_default_value("eventTimestamp")
        if not isinstance(value, (int, float)):
            return None
        self.cache.event_start_timestamp = int(value)
        return int(value)

    async def check_has_event_started(self) -> bool:
        "Check if the event has started"
        ts = await self.get_event_start_timestamp()
        if ts is None: # start date is none means the event has finished
            return True
        return ts < time.time()

    async def check_has_event_finished(self) -> bool:
        "Check if the event has finished"
        ts = await self.get_event_start_timestamp()
        return ts is None # start date is none means the event has finished
