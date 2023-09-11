from datetime import datetime
from typing import TypedDict

class GiveawayToSendData(TypedDict):
    "Data for a giveaway instance stored in Firestore"
    guild: int
    channel: int
    name: str
    description: str
    color: int
    max_entries: int
    winners_count: int
    ends_at: datetime
    ended: bool
    participants: list[int]
    winners: list[int]

class RawGiveawayData(TypedDict):
    "Data for a giveaway instance stored in Firestore"
    guild: int
    channel: int
    message: int
    name: str
    description: str
    color: int
    max_entries: int
    winners_count: int
    ends_at: str
    ended: bool
    participants: list[int]
    winners: list[int]

class GiveawayData(TypedDict):
    "Data for a giveaway instance stored in Firestore"
    guild: int
    channel: int
    message: int
    name: str
    description: str
    color: int
    max_entries: int
    winners_count: int
    ends_at: datetime
    ended: bool
    participants: list[int]
    winners: list[int]
