from datetime import datetime
from typing import TypedDict

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
    participants: list[int]
    winners: list[int]
