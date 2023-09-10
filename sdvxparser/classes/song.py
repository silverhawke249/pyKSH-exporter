"""
Classes that encapsulate song metadata.
"""
from dataclasses import dataclass
from decimal import Decimal
from time import strftime

from .enums import GameBackground, InfVer

__all__ = [
    "SongInfo",
]


@dataclass
class SongInfo:
    """A class that contains all song metadata, which applies to all charts of it."""

    id: int = 0
    title: str = ""
    title_yomigana: str = ""
    artist: str = ""
    artist_yomigana: str = ""
    ascii_label: str = ""
    min_bpm: Decimal = Decimal()
    max_bpm: Decimal = Decimal()
    release_date: str = ""
    music_volume: int = 100
    background: GameBackground = GameBackground.EXCEED_GEAR_TOWER_1
    inf_ver: InfVer = InfVer.INFINITE

    def __post_init__(self):
        self.release_date = strftime("%Y%m%d")
