"""
Abstract base classes for parsers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
    """
    An abstract base class that encapsulates song and chart data.
    """

    chart_info: ChartInfo = field(default_factory=ChartInfo)
    song_info: SongInfo = field(default_factory=SongInfo)

    @abstractmethod
    def write_vox(self, f: TextIO) -> None:
        """Write the chart data in VOX format."""
        pass

    @abstractmethod
    def write_xml(self, f: TextIO) -> None:
        """Write the song and chart metadata in XML format."""
        pass


class Parser(ABC):
    """
    An abstract base class for parsers that read a specific format.
    """

    _file_path: Path

    @abstractmethod
    def parse(self, f: TextIO) -> SongChartContainer:
        """Parse a file, producing chart data and supporting metadata."""
        pass

    @property
    def file_path(self):
        """Path to the file to parse."""
        return self._file_path
