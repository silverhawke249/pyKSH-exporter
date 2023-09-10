from abc import abstractmethod
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import TextIO

from ..classes.base import AbstractDataclass
from ..classes.chart import ChartInfo
from ..classes.song import SongInfo

__all__ = [
    "SongChartContainer",
    "Parser",
]


@dataclass
class SongChartContainer(AbstractDataclass):
    chart_info: ChartInfo = field(default_factory=ChartInfo)
    song_info: SongInfo = field(default_factory=SongInfo)

    @abstractmethod
    def write_vox(self, f: TextIO) -> None:
        pass

    @abstractmethod
    def write_xml(self, f: TextIO) -> None:
        pass


@dataclass
class Parser(AbstractDataclass):
    file: InitVar[TextIO]

    _file_path: Path = field(init=False)
    _song_chart_data: SongChartContainer = field(init=False)

    @property
    def file_path(self):
        return self._file_path

    @property
    def chart_info(self):
        return self._song_chart_data.chart_info

    @property
    def song_info(self):
        return self._song_chart_data.song_info

    def write_vox(self, f: TextIO):
        self._song_chart_data.write_vox(f)

    def write_xml(self, f: TextIO):
        self._song_chart_data.write_xml(f)
