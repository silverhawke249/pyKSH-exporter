import struct
import wave

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from pydub import AudioSegment


class MSADPCMWave:
    # For fmt chunk
    wFormat         : int = 2
    nChannels       : int = 2
    nSamplesPerSec  : int = 44100
    nAvgBytesPerSec : int = 46269
    nBlockAlign     : int = 256
    wBitsPerSample  : int = 4
    wSamplesPerBlock: int = 244
    wNumCoef        : int = 7
    aCoef           : list[tuple[int, int]] = [
        (256, 0),
        (512, -256),
        (0, 0),
        (192, 64),
        (240, 0),
        (460, -208),
        (392, -232),
    ]

    # For fact chunk
    nFrames         : int = 0

    # For data chunk
    waveData        : bytes = b''

    # Cached serialized data
    _serialized_self: bytes = b''

    def __init__(self, wave_in: wave.Wave_read):
        self.nFrames = wave_in.getnframes()

        available_frames = self.nFrames
        while available_frames > 0:
            # TODO: Implement MS ADPCM encoding
            one_sec = wave_in.readframes(44100)

            available_frames -= 44100

    def serialize(self) -> bytes:
        if not self._serialized_self:
            # RIFF container
            blob: bytes = b'RIFF'
            blob += struct.pack('<L', 82 + len(self.waveData))

            blob += b'WAVE'

            # fmt chunk
            blob += b'fmt '
            blob += struct.pack('<L', 50)
            blob += struct.pack('<H', self.wFormat)
            blob += struct.pack('<H', self.nChannels)
            blob += struct.pack('<L', self.nSamplesPerSec)
            blob += struct.pack('<L', self.nAvgBytesPerSec)
            blob += struct.pack('<H', self.nBlockAlign)
            blob += struct.pack('<H', self.wBitsPerSample)
            blob += struct.pack('<H', 32)
            blob += struct.pack('<H', self.wSamplesPerBlock)
            blob += struct.pack('<H', self.wNumCoef)
            for coef1, coef2 in self.aCoef:
                blob += struct.pack('<H', coef1)
                blob += struct.pack('<H', coef2)

            # fact chunk
            blob += b'fact'
            blob += struct.pack('<H', 4)
            blob += struct.pack('<H', self.nFrames)

            # data chunk
            blob += b'data'
            blob += struct.pack('<H', len(self.waveData))
            blob += self.waveData

            self._serialized_self = blob

        return self._serialized_self


@dataclass
class Blob2DX:
    wav: bytes
    _serialized_self: bytes = field(default=b'', init=False)

    def __init__(self, wave_obj: MSADPCMWave):
        self.wav = wave_obj.serialize()

    def serialize(self) -> bytes:
        if not self._serialized_self:
            blob: bytes = b'2DX9'
            blob += struct.pack('<L', 24)
            blob += struct.pack('<L', len(self.wav))
            blob += b'\x31\x32'
            blob += struct.pack('<h', -1)
            blob += struct.pack('<h', 64)
            blob += struct.pack('<h', 1)
            blob += struct.pack('<l', 0)
            blob += self.wav

            self._serialized_self = blob

        return self._serialized_self


@dataclass
class Container2DX:
    filename: str
    blobs: list[Blob2DX] = field(default_factory=list, init=False)

    def serialize(self) -> bytes:
        blob: bytes = b''

        encoded_fn = self.filename.encode()
        blob += encoded_fn[:16]
        if len(encoded_fn) < 16:
            blob += b'\x00' * (16 - len(encoded_fn))

        blob += struct.pack('<L', 72 + 4 * len(self.blobs))
        blob += struct.pack('<L', len(self.blobs))
        blob += b'\x00' * 48

        wav_offset = len(blob) + 4 * len(self.blobs)

        prev_blob: bytes = b''
        for wav_blob in self.blobs:
            blob += struct.pack('<L', wav_offset)
            if prev_blob:
                wav_offset += len(prev_blob)
            prev_blob = wav_blob.serialize()

        for wav_blob in self.blobs:
            blob += wav_blob.serialize()

        return blob


# Preview start must be in ms
def prepare_audio(file_path: Path, preview_start: int) -> tuple[wave.Wave_read, wave.Wave_read]:
    audio = AudioSegment.from_file(str(file_path))
    audio = audio.set_frame_rate(44100)
    audio = audio.set_channels(2)

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
    song_wave, preview_wave = prepare_audio(file_path, preview_start)

    song_container = Container2DX(f'{song_label}.2dx')
    preview_container = Container2DX(f'{song_label}_pre.2dx')

    song_container.blobs.append(Blob2DX(MSADPCMWave(song_wave)))
    preview_container.blobs.append(Blob2DX(MSADPCMWave(preview_wave)))

    return song_container.serialize(), preview_container.serialize()
