import struct
import wave

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from pydub import AudioSegment

# MS ADPCM code adapted (heh) off FFmpeg's libavcodec/adpcmenc.c
ADPCM_ADAPTATION_TABLE = [
    230, 230, 230, 230, 307, 409, 512, 614,
    768, 614, 512, 409, 307, 230, 230, 230,
]


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


class MSADPCMWave:
    """ Converts a wave object of the correct specs """
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
    cStatus         : list[MSADPCMChannelStatus]
    waveData        : bytes = b''

    # Cached serialized data
    _serialized_self: bytes = b''

    def __init__(self, wave_in: wave.Wave_read):
        if wave_in.getframerate() != 44100 and wave_in.getnchannels() != 2 and wave_in.getsampwidth() != 2:
            raise ValueError('Wave file not in the correct spec (must be 44.1kHz 16-bit stereo)')

        self.cStatus = [MSADPCMChannelStatus() for _ in range(self.nChannels)]

        available_frames = wave_in.getnframes()
        while available_frames > 0:
            one_block = wave_in.readframes(self.wSamplesPerBlock)
            samples = [t[0] for t in struct.iter_unpack('<h', one_block)]
            while len(samples) < 2 * self.wSamplesPerBlock:
                samples.append(0)
            self.encode_frame(samples)

            available_frames -= self.wSamplesPerBlock
            self.nFrames += self.wSamplesPerBlock

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

    def encode_frame(self, samples: list[int]):
        sample_iter = iter(samples)
        dst = BytesIO()

        for i in range(self.nChannels):
            predictor = 0
            dst.write(struct.pack('<B', predictor))
            self.cStatus[i].coeff1 = self.aCoef[predictor][0]
            self.cStatus[i].coeff2 = self.aCoef[predictor][1]

        for i in range(self.nChannels):
            if self.cStatus[i].idelta < 16:
                self.cStatus[i].idelta = 16
            dst.write(struct.pack('<h', self.cStatus[i].idelta))

        for i in range(self.nChannels):
            self.cStatus[i].sample2 = next(sample_iter)
        for i in range(self.nChannels):
            self.cStatus[i].sample1 = next(sample_iter)
            dst.write(struct.pack('<h', self.cStatus[i].sample1))

        for i in range(self.nChannels):
            dst.write(struct.pack('<h', self.cStatus[i].sample2))

        for i in range(7 * self.nChannels, self.nBlockAlign):
            nibble = 0
            nibble = self.compress_sample(self.cStatus[0], next(sample_iter)) << 4
            nibble |= self.compress_sample(self.cStatus[1], next(sample_iter))
            dst.write(struct.pack('<B', nibble))

        self.waveData += dst.getvalue()

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
                blob += struct.pack('<h', coef1)
                blob += struct.pack('<h', coef2)

            # fact chunk
            blob += b'fact'
            blob += struct.pack('<L', 4)
            blob += struct.pack('<L', self.nFrames)

            # data chunk
            blob += b'data'
            blob += struct.pack('<L', len(self.waveData))
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
    song_wave, preview_wave = prepare_audio(file_path, preview_start)

    song_container = Container2DX(f'{song_label}.2dx')
    preview_container = Container2DX(f'{song_label}_pre.2dx')

    song_container.blobs.append(Blob2DX(MSADPCMWave(song_wave)))
    preview_container.blobs.append(Blob2DX(MSADPCMWave(preview_wave)))

    return song_container.serialize(), preview_container.serialize()
