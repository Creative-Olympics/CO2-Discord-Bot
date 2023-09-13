from datetime import datetime as dt
from typing import AsyncGenerator, Optional

import firebase_admin
from firebase_admin import credentials, db

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

    async def get_giveaways(self) -> AsyncGenerator[GiveawayData, None]:
        "Get a generator of giveaway documents"
        ref = db.reference("giveaways")
        snapshot: dict[str, RawGiveawayData] = ref.get() # type: ignore
        for gaw_id, gaw in snapshot.items():
            yield {
                **gaw,
                "id": gaw_id,
                "ends_at": dt.fromisoformat(gaw["ends_at"]),
                "winners": gaw.get("winners", [])
            } # type: ignore

    async def get_active_giveaways(self) -> AsyncGenerator[GiveawayData, None]:
        """Get a generator of active giveaway documents (ie. not 'ended')
        Note: this may include giveaways that have a past end date but have not been marked as ended yet"""
        ref = db.reference("giveaways")
        snapshot: dict[str, RawGiveawayData] = ref.order_by_child("ended").equal_to(False).get() # type: ignore
        for gaw_id, gaw in snapshot.items():
            yield {
                **gaw,
                "id": gaw_id,
                "ends_at": dt.fromisoformat(gaw["ends_at"]),
                "winners": gaw.get("winners", [])
            } # type: ignore

    async def create_giveaway(self, data: GiveawayData):
        "Create a giveaway document"
        ref = db.reference("giveaways")
        ref.child(data["id"]).set({
            **data,
            "ends_at": data["ends_at"].isoformat()
        })

    async def get_giveaways_participants(self, giveaway_id: str) -> Optional[list[int]]:
        "Get a list of participants for a giveaway"
        ref = db.reference(f"participants/{giveaway_id}")
        return ref.get() # type: ignore
