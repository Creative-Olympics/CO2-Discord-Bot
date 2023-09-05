from typing import AsyncGenerator

import firebase_admin
from firebase_admin import credentials, firestore_async


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
