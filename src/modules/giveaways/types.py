from datetime import datetime
from typing import Literal, Optional, TypedDict, Union

class GiveawayToSendData(TypedDict):
    "Data for a giveaway instance stored in Firestore"
    id: str
    guild: int
    channel: int
    name: str
    description: str
    color: int
    max_entries: Optional[int]
    winners_count: int
    ends_at: datetime
    ended: bool

class _RawGiveawayDataWithWinners(TypedDict):
    "Data for a giveaway instance stored in Firestore"
    guild: int
    channel: int
    message: int
    name: str
    description: str
    color: int
    max_entries: Optional[int]
    winners_count: int
    ends_at: str
    ended: Literal[True]
    winners: list[int]

class _RawGiveawayDataWithoutWinners(TypedDict):
    "Data for a giveaway instance stored in Firestore"
    guild: int
    channel: int
    message: int
    name: str
    description: str
    color: int
    max_entries: Optional[int]
    winners_count: int
    ends_at: str
    ended: Literal[False]

RawGiveawayData = Union[_RawGiveawayDataWithoutWinners, _RawGiveawayDataWithWinners]

class GiveawayData(TypedDict):
    "Data for a giveaway instance stored in Firestore"
    id: str
    guild: int
    channel: int
    message: int
    name: str
    description: str
    color: int
    max_entries: Optional[int]
    winners_count: int
    ends_at: datetime
    ended: bool
    winners: list[int]
