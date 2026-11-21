"""FMOD FSB5 sample banks with FADPCM audio (the game's dating-scene sounds), decoded to WAV without external tools.

FADPCM: 0x8C-byte frames per channel, 256 samples each, 8 groups of 32 samples; every frame restarts its predictor from
the two history samples in its header (layout and arithmetic as documented by vgmstream, verified against its output).
"""
import io
import struct
import wave
from typing import Any, Dict, List, Tuple

FRAME = 0x8C
FREQUENCIES = {1: 8000, 2: 11000, 3: 11025, 4: 16000, 5: 22050, 6: 24000, 7: 32000, 8: 44100, 9: 48000}
CODEC_FADPCM = 16
_COEFS = [(0, 0), (60, 0), (122, 60), (115, 52), (98, 55), (0, 0), (0, 0)]


def _decode_frame(frame: bytes, out: List[int]) -> None:
    coefs, shifts, h1, h2 = struct.unpack_from('<IIhh', frame, 0)
    for group in range(8):
        c1, c2 = _COEFS[((coefs >> (group * 4)) & 0xF) % 7]
        shift = 22 - ((shifts >> (group * 4)) & 0xF)
        for word in struct.unpack_from('<4I', frame, 0x0C + group * 0x10):
            for k in range(8):
                nibble = (word >> (k * 4)) & 0xF
                scaled = ((nibble - 16 if nibble & 8 else nibble) << 28) >> shift  # as the C `(s << 28) >> shift`
                value = (scaled - h2 * c2 + h1 * c1) >> 6
                value = -32768 if value < -32768 else 32767 if value > 32767 else value
                out.append(value)
                h2, h1 = h1, value


def decode_fadpcm(data: bytes, channels: int = 1) -> List[List[int]]:
    """Whole frames only; frames of the channels alternate."""
    result: List[List[int]] = [[] for _ in range(channels)]
    for n in range(len(data) // (FRAME * channels)):
        for c in range(channels):
            start = (n * channels + c) * FRAME
            _decode_frame(data[start:start + FRAME], result[c])
    return result


def parse_fsb5(blob: bytes) -> Tuple[List[Dict[str, Any]], int, int]:
    """Samples (name, rate, channels, byte range inside the data block, sample count), data block offset and codec."""
    base = blob.find(b'FSB5')
    if base < 0:
        raise ValueError('No FSB5 block in this bank')
    version, count, header_size, name_size, data_size, codec = struct.unpack_from('<6I', blob, base + 4)
    start = base + (60 if version == 1 else 56)
    pos, samples = start, []
    for _ in range(count):
        bits = struct.unpack_from('<Q', blob, pos)[0]
        pos += 8
        more = bits & 1
        # next(1) frequency(4) channels(1) offset/16(28) samples(30)
        samples.append({'rate': FREQUENCIES.get((bits >> 1) & 0xF, 44100), 'channels': 2 if (bits >> 5) & 1 else 1,
                        'offset': ((bits >> 6) & 0xFFFFFFF) * 16, 'samples': bits >> 34})
        while more:  # extra per-sample chunks: bit0 more, bits1-24 size, bits25-31 type
            chunk = struct.unpack_from('<I', blob, pos)[0]
            pos += 4 + ((chunk >> 1) & 0xFFFFFF)
            more = chunk & 1
    names_at = start + header_size
    if name_size:
        for i, offset in enumerate(struct.unpack_from(f'<{count}I', blob, names_at)):
            samples[i]['name'] = blob[names_at + offset:blob.find(b'\0', names_at + offset)].decode('latin1')
    data_at = names_at + name_size
    for i, s in enumerate(samples):
        s['end'] = samples[i + 1]['offset'] if i + 1 < count else data_size
        s.setdefault('name', f'sample_{i}')
    return samples, data_at, codec


def sample_to_wav(blob: bytes, data_at: int, sample: Dict[str, Any]) -> bytes:
    pcm = decode_fadpcm(blob[data_at + sample['offset']:data_at + sample['end']], sample['channels'])
    frames = min(len(pcm[0]), sample['samples'])
    interleaved = [pcm[c][i] for i in range(frames) for c in range(sample['channels'])]
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(sample['channels'])
        wav.setsampwidth(2)
        wav.setframerate(sample['rate'])
        wav.writeframes(struct.pack(f'<{len(interleaved)}h', *interleaved))
    return buffer.getvalue()
