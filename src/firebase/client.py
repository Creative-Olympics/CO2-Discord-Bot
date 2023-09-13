from datetime import datetime as dt
from typing import AsyncGenerator, Optional

import firebase_admin
from firebase_admin import credentials, db

from src.firebase.caching import FirebaseCacheControler
from src.modules.giveaways.types import GiveawayData, RawGiveawayData


class FirebaseDB:
    "Firebase client class to access the database"

    def __init__(self, filename: str, realtime_url: str, auth_uuid: str):
        cred = credentials.Certificate(filename)
        self.app = firebase_admin.initialize_app(cred, {
            'databaseURL': realtime_url,
            # 'databaseAuthVariableOverride': {
            #     'uid': auth_uuid
            # }
        })
        self.cache = FirebaseCacheControler()

    async def get_giveaways(self) -> AsyncGenerator[GiveawayData, None]:
        "Get a generator of giveaway documents"
        if self.cache.are_giveaways_sync:
            for gaw in self.cache.get_giveaways():
                yield gaw
            return
        print("Fetching giveaways")
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
        print("Fetching active giveaways")
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

    async def create_giveaway(self, data: GiveawayData):
        "Create a giveaway document"
        ref = db.reference("giveaways")
        ref.child(data["id"]).set({
            **data,
            "ends_at": data["ends_at"].isoformat()
        })
        self.cache.set_new_giveaway(data)

    async def get_giveaways_participants(self, giveaway_id: str) -> Optional[list[int]]:
        "Get a list of participants for a giveaway"
        if self.cache.are_participants_sync(giveaway_id):
            return self.cache.get_participants(giveaway_id)
        print(f"Fetching participants for giveaway {giveaway_id}")
        ref = db.reference(f"participants/{giveaway_id}")
        snapshot: Optional[list[int]] = ref.get() # type: ignore
        self.cache.set_participants(giveaway_id, snapshot or [])
        return snapshot
