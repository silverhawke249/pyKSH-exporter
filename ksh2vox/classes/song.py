from dataclasses import dataclass
from decimal import Decimal
from time import strftime

from .enums import GameBackground, InfVer


@dataclass
class SongInfo:
    id: int = 0
    title: str = ''
    title_yomigana: str = ''
    artist: str = ''
    artist_yomigana: str = ''
    ascii_label: str = ''
    max_bpm: Decimal = Decimal(0)
    min_bpm: Decimal = Decimal(0)
    release_date: str = ''
    music_volume: int = 100
    background: GameBackground = GameBackground.EXCEED_GEAR_TOWER_1
    inf_ver: InfVer = InfVer.INFINITE

    def __post_init__(self):
        self.release_date = strftime('%Y%m%d')
