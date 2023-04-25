import struct
import wave

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from pydub import AudioSegment

ADPCM_ADAPTATION_TABLE = [
    230, 230, 230, 230, 307, 409, 512, 614,
    768, 614, 512, 409, 307, 230, 230, 230,
]
ADPCM_ADAPTATION_COEFF = [256, 512, 0, 192, 240, 460, 392]
ADPCM_ADAPTATION_COEFF = [0, -256, 0, 64, 0, -208, -232]


@dataclass
class MSADPCMEncoder:
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

    def compress_sample(self, sample: int) -> int:
        if not -32_768 <= sample <= 32_767:
            raise ValueError(f'sample out of range (got {sample})')

        predictor = (((self.sample1) * (self.coeff1)) +
                     ((self.sample2) * (self.coeff2))) / 64
        nibble = sample - predictor
        if (nibble >= 0):
            bias = self.idelta / 2
        else:
            bias = -self.idelta / 2

        nibble = (nibble + bias) / self.idelta
        if nibble < -8:
            nibble = -8
        if nibble > 7:
            nibble = 7
        nibble = nibble & 0x0F

        predictor += (nibble - (0x10 if nibble & 0x08 else 0)) * self.idelta

        self.sample2 = self.sample1
        self.sample1 = (-32_768 if predictor < -32_768 else
                         32_767 if predictor > 32_767 else predictor)

        self.idelta = (ADPCM_ADAPTATION_TABLE[nibble] * self.idelta) >> 8
        if self.idelta < 16:
            self.idelta = 16

        return nibble

    def encode_frame():
        channels = 2
        samples = (const int16_t *)frame->data[0];
        samples_p = (const int16_t *const *)frame->extended_data;
        st = True
        pkt_size = 256

        dst = b'';

        for i in range(2) {
            predictor = 0;
            *dst++ = predictor;
            c->status[i].coeff1 = ff_adpcm_AdaptCoeff1[predictor];
            c->status[i].coeff2 = ff_adpcm_AdaptCoeff2[predictor];
        }
        for (int i = 0; i < channels; i++) {
            if (c->status[i].idelta < 16)
                c->status[i].idelta = 16;
            bytestream_put_le16(&dst, c->status[i].idelta);
        }
        for (int i = 0; i < channels; i++)
            c->status[i].sample2= *samples++;
        for (int i = 0; i < channels; i++) {
            c->status[i].sample1 = *samples++;
            bytestream_put_le16(&dst, c->status[i].sample1);
        }
        for (int i = 0; i < channels; i++)
            bytestream_put_le16(&dst, c->status[i].sample2);

        if (avctx->trellis > 0) {
            const int n  = avctx->block_align - 7 * channels;
            uint8_t *buf = av_malloc(2 * n);
            if (!buf)
                return AVERROR(ENOMEM);
            if (channels == 1) {
                adpcm_compress_trellis(avctx, samples, buf, &c->status[0], n,
                                       channels);
                for (int i = 0; i < n; i += 2)
                    *dst++ = (buf[i] << 4) | buf[i + 1];
            } else {
                adpcm_compress_trellis(avctx, samples,     buf,
                                       &c->status[0], n, channels);
                adpcm_compress_trellis(avctx, samples + 1, buf + n,
                                       &c->status[1], n, channels);
                for (int i = 0; i < n; i++)
                    *dst++ = (buf[i] << 4) | buf[n + i];
            }
            av_free(buf);
        } else {
            for (int i = 7 * channels; i < avctx->block_align; i++) {
                int nibble;
                nibble  = adpcm_ms_compress_sample(&c->status[ 0], *samples++) << 4;
                nibble |= adpcm_ms_compress_sample(&c->status[st], *samples++);
                *dst++  = nibble;
            }
        }


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
