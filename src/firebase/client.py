from typing import AsyncGenerator

import firebase_admin
from firebase_admin import credentials, firestore_async
from firebase_admin.firestore import firestore


class FirebaseDB:
    "Firebase client class to access the database"

    def __init__(self, filename: str):
        cred = credentials.Certificate(filename)
        app = firebase_admin.initialize_app(cred)
        self.__client = firestore_async.client(app)

    async def get_user_ids(self) -> AsyncGenerator[str, None]:
        "Get a generator of user IDs"
        async for user in self.__client.collection("users").stream(): # type: ignore
            yield user.id

    async def get_user_general(self, user_id: str):
        "Get the General document snapshot for a user"
        return await self.__client.document(f"users/{user_id}/public/general").get()

    async def get_giveaways(self):
        "Get a generator of giveaway documents"
        async for doc in self.__client.collection("giveaways").stream(): # type: ignore
            yield doc

    async def get_active_giveaways(self) -> AsyncGenerator[firestore.DocumentSnapshot, None]:
        """Get a generator of active giveaway documents (ie. not 'ended')
        Note: this may include giveaways that have a past end date but have not been marked as ended yet"""
        ended_filter = firestore.FieldFilter("ended", "==", False)
        docs = self.__client.collection("giveaways").where(filter=ended_filter).stream()
        async for doc in docs: # type: ignore
            yield doc

    async def get_pending_ending_giveaways(self) -> AsyncGenerator[firestore.DocumentSnapshot, None]:
        "Get a generator of giveaway documents that are pending ending (ie. not 'ended' but have a past end date)"
        now = firestore.SERVER_TIMESTAMP
        ended_filter = firestore.FieldFilter("ended", "==", False)
        date_filter = firestore.FieldFilter("ends_at", "<=", now)
        docs = self.__client.collection("giveaways").where(filter=ended_filter).where(filter=date_filter).stream()
        async for doc in docs: # type: ignore
            yield doc
