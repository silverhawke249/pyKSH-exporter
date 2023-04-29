import struct
import wave

import construct as cs

from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

from pydub import AudioSegment

# MS ADPCM code adapted (heh) off FFmpeg's libavcodec/adpcmenc.c
ADPCM_ADAPTATION_TABLE = [
    230, 230, 230, 230, 307, 409, 512, 614,
    768, 614, 512, 409, 307, 230, 230, 230,
]

MSADPCMWaveStruct = cs.Struct(
    # RIFF container
    cs.Const(b'RIFF'),

    'wave' / cs.Prefixed(cs.Int32ul, cs.Struct(
        # WAVE format
        cs.Const(b'WAVE'),

        # fmt chunk
        cs.Const(b'fmt '),
        cs.Const(50, cs.Int32ul) * 'Chunk size',
        'wFormat' / cs.Int16ul,
        'nChannels' / cs.Int16ul,
        'nSamplesPerSec' / cs.Int32ul,
        'nAvgBytesPerSec' / cs.Int32ul,
        'nBlockAlign' / cs.Int16ul,
        'wBitsPerSample' / cs.Int16ul,
        cs.Const(32, cs.Int16ul) * 'Extra data size',
        'wSamplesPerBlock' / cs.Int16ul,
        'wNumCoef' / cs.Int16ul,
        'aCoef' / cs.Array(cs.this.wNumCoef, cs.Int16sl[2]),

        # fact chunk
        cs.Const(b'fact'),
        cs.Const(4, cs.Int32ul) * 'Chunk size',
        'nFrames' / cs.Int32ul,

        # data chunk
        cs.Const(b'data'),
        'waveBlobLength' / cs.Rebuild(cs.Int32ul, cs.len_(cs.this.waveBlob)),
        'waveBlob' / cs.Bytes(cs.this.waveBlobLength)
    ))
)

def getOffsets(this) -> list[int]:
    offsets = []
    for i in range(this.fileCount):
        if i == 0:
            offsets.append(this.headerSize)
        else:
            offsets.append(offsets[-1] + len(this._.files.blob[i]))
    return offsets

TwoDXFileStruct = cs.Struct(
    'header' / cs.Struct(
        'fileName' / cs.Bytes(16),
        'headerSize' / cs.Rebuild(cs.Int32ul, 72 + 4 * cs.len_(cs.this._.files)),
        'fileCount' / cs.Rebuild(cs.Int32ul, cs.len_(cs.this._.files)),
        cs.Padding(48),
        'offsets' / cs.Rebuild(cs.Int32ul[cs.this.fileCount], getOffsets)
    ),
    'files' / cs.Struct(
        cs.Const(b'2DX9'),
        cs.Const(24, cs.Int32ul),
        'size' / cs.Rebuild(cs.Int32ul, cs.len_(cs.this.blob)),
        cs.Const(b'\x31\x32'),
        cs.Const(-1, cs.Int16sl),
        cs.Const(64, cs.Int16sl),
        cs.Const(1, cs.Int16sl),
        cs.Const(0, cs.Int32sl),
        'blob' / cs.Bytes(cs.this.size)
    )[cs.this.header.fileCount]
)


@dataclass
class MSADPCMChannelStatus:
    predictor : int = 0
    step_index: int = 0
    step      : int = 0

    # for encoding
    prev_sample: int = 0

    # MS version
    sample1: int = 0
    sample2: int = 0
    coeff1 : int = 0
    coeff2 : int = 0
    idelta : int = 0


@dataclass
class MSADPCMWave:
    """ Converts a wave object of the correct specs to Microsoft ADPCM WAV. """
    # For fmt chunk
    wFormat         : int = 2
    nChannels       : int = 2
    nSamplesPerSec  : int = 44100
    nAvgBytesPerSec : int = 46269
    nBlockAlign     : int = 256
    wBitsPerSample  : int = 4
    wSamplesPerBlock: int = 244
    # Adaptation coefficients
    wNumCoef        : int = 7
    aCoef           : list[tuple[int, int]] = field(default_factory=list)

    # For fact chunk
    nFrames         : int = 0

    # For data chunk
    cStatus         : list[MSADPCMChannelStatus] = field(default_factory=list)
    waveData        : BytesIO = field(default_factory=BytesIO)
    waveBlob        : bytes = field(default=b'')

    _serialized_self: bytes = field(default=b'')

    def __init__(self, wave_in: wave.Wave_read):
        if wave_in.getframerate() != 44100 and wave_in.getnchannels() != 2 and wave_in.getsampwidth() != 2:
            raise ValueError('Wave file not in the correct spec (must be 44.1kHz 16-bit stereo)')

        self.aCoef = [
            (256, 0),
            (512, -256),
            (0, 0),
            (192, 64),
            (240, 0),
            (460, -208),
            (392, -232),
        ]
        self.nFrames = wave_in.getnframes()
        self.cStatus = [MSADPCMChannelStatus() for _ in range(self.nChannels)]
        self.waveData = BytesIO()

        available_frames = self.nFrames
        while available_frames > 0:
            one_block = wave_in.readframes(self.wSamplesPerBlock)
            frames_read = len(one_block) // self.nChannels // wave_in.getsampwidth()
            # Align to a full block
            if frames_read < self.wSamplesPerBlock:
                one_block += b'\x00' * ((self.wSamplesPerBlock - frames_read) * self.nChannels * wave_in.getsampwidth())
            self.encode_frame(t[0] for t in struct.iter_unpack('<h', one_block))

            available_frames -= frames_read

        self.waveBlob = self.waveData.getvalue()
        wave_in.close()

    def compress_sample(self, status: MSADPCMChannelStatus, sample: int) -> int:
        if not -32_768 <= sample <= 32_767:
            raise ValueError(f'sample out of range (got {sample})')

        predictor = (((status.sample1) * (status.coeff1)) +
                     ((status.sample2) * (status.coeff2))) // 256

        nibble = sample - predictor
        if (nibble >= 0):
            bias = status.idelta // 2
        else:
            bias = -status.idelta // 2

        nibble = (nibble + bias) // status.idelta
        if nibble < -8:
            nibble = -8
        if nibble > 7:
            nibble = 7
        nibble = nibble & 0x0F

        predictor += (nibble - (0x10 if nibble & 0x08 else 0)) * status.idelta

        status.sample2 = status.sample1
        status.sample1 = (-32_768 if predictor < -32_768 else
                           32_767 if predictor > 32_767 else predictor)

        status.idelta = (ADPCM_ADAPTATION_TABLE[nibble] * status.idelta) >> 8
        if status.idelta < 16:
            status.idelta = 16

        return nibble

    def encode_frame(self, sample_iter: Iterator[int]):
        for i in range(self.nChannels):
            predictor = 0
            self.waveData.write(struct.pack('<B', predictor))
            self.cStatus[i].coeff1 = self.aCoef[predictor][0]
            self.cStatus[i].coeff2 = self.aCoef[predictor][1]

        for i in range(self.nChannels):
            if self.cStatus[i].idelta < 16:
                self.cStatus[i].idelta = 16
            self.waveData.write(struct.pack('<h', self.cStatus[i].idelta))

        for i in range(self.nChannels):
            self.cStatus[i].sample2 = next(sample_iter)
        for i in range(self.nChannels):
            self.cStatus[i].sample1 = next(sample_iter)
            self.waveData.write(struct.pack('<h', self.cStatus[i].sample1))

        for i in range(self.nChannels):
            self.waveData.write(struct.pack('<h', self.cStatus[i].sample2))

        for i in range(7 * self.nChannels, self.nBlockAlign):
            nibble = 0
            nibble = self.compress_sample(self.cStatus[0], next(sample_iter)) << 4
            nibble |= self.compress_sample(self.cStatus[1], next(sample_iter))
            self.waveData.write(struct.pack('<B', nibble))

    def serialize(self) -> bytes:
        if not self._serialized_self:
            self._serialized_self = MSADPCMWaveStruct.build({'wave': asdict(self)})

        return self._serialized_self


@dataclass
class Container2DX:
    filename: str
    waves: list[MSADPCMWave] = field(default_factory=list, init=False)
    _serialized_self: bytes = field(default=b'', init=False)

    def serialize(self) -> bytes:
        if not self._serialized_self:
            filename_bytes = self.filename.encode()[:16]
            if len(filename_bytes) < 16:
                filename_bytes += b'\x00' * (16 - len(filename_bytes))
            self._serialized_self = TwoDXFileStruct.build({
                'header': {'fileName': filename_bytes},
                'files': [{'blob': wave.serialize()} for wave in self.waves],
            })

        return self._serialized_self


# Preview start must be in ms
def prepare_audio(file_path: Path, preview_start: int) -> tuple[wave.Wave_read, wave.Wave_read]:
    audio = AudioSegment.from_file(str(file_path))
    audio = audio.set_frame_rate(44100)
    audio = audio.set_channels(2)
    audio = audio.set_sample_width(2)

    # 10s preview sample
    preview = audio[preview_start:preview_start + 10_000]
    preview = preview.fade_in(1000).fade_out(1000)

    audio_out = BytesIO()
    preview_out = BytesIO()
    audio.export(audio_out, 'wav')
    preview.export(preview_out, 'wav')

    audio_out.seek(0)
    preview_out.seek(0)

    return wave.open(audio_out, 'rb'), wave.open(preview_out, 'rb')


def get_2dxs(file_path: Path, song_label: str, preview_start: int) -> tuple[bytes, bytes]:
    """ Return song files as 2DX blobs at full length and preview length, in that order. """
    song_wave, preview_wave = prepare_audio(file_path, preview_start)

    song_container = Container2DX(f'{song_label}.2dx')
    preview_container = Container2DX(f'{song_label}_pre.2dx')

    song_container.waves.append(MSADPCMWave(song_wave))
    preview_container.waves.append(MSADPCMWave(preview_wave))

    return song_container.serialize(), preview_container.serialize()
