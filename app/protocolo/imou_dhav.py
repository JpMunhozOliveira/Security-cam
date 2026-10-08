"""Empacotamento de áudio AAC/ADTS em frames DHAV para o talk da câmera Imou."""

from __future__ import annotations

import struct
import time
from collections.abc import Iterable

SAMPLE_RATE_CODES = {
    8000: 2,
    11025: 3,
    16000: 4,
    20000: 5,
    22050: 6,
    32000: 7,
    44100: 8,
    48000: 9,
}

DHAV_AUDIO_INFO = b"\x83\x01\x1a"
DHAV_OVERHEAD = 36  # 28 de cabeçalho + 8 de rodapé ("dhav" + tamanho)


def _sample_rate_code(sample_rate: int) -> int:
    try:
        return SAMPLE_RATE_CODES[sample_rate]
    except KeyError:
        suportados = ", ".join(str(x) for x in sorted(SAMPLE_RATE_CODES))
        raise ValueError(f"sample rate {sample_rate} não suportado; use: {suportados}") from None


def _checksum(header: bytes | bytearray) -> int:
    """Soma dos bytes 0x00..0x16 do cabeçalho, módulo 256."""
    return sum(header[:0x17]) & 0xFF


def pack_dhav_audio(
    payload: bytes,
    *,
    seq: int,
    sample_rate: int,
    timestamp: int,
    tick: int,
    frame_type: int = 0xF0,
) -> bytes:
    """Empacota um payload de áudio como um frame DHAV."""
    total_len = len(payload) + DHAV_OVERHEAD
    header = bytearray(28)
    struct.pack_into("<4sB3xII", header, 0, b"DHAV", frame_type & 0xFF, seq & 0xFFFFFFFF, total_len)
    struct.pack_into("<I", header, 0x10, timestamp & 0xFFFFFFFF)
    struct.pack_into("<H", header, 0x14, tick & 0xFFFF)
    header[0x16] = 0x04
    header[0x17] = _checksum(header)
    header[0x18:0x1B] = DHAV_AUDIO_INFO
    header[0x1B] = _sample_rate_code(sample_rate)
    return bytes(header) + payload + b"dhav" + struct.pack("<I", total_len)


def pack_dhhttp_interleaved(frame: bytes, *, track_id: int) -> bytes:
    """Envolve o frame DHAV no formato interleaved do DHHTTP:
    "$" + canal (2 * trackID) + tamanho (4 bytes, big-endian) + frame."""
    channel = track_id * 2
    if not 0 <= channel <= 0xFF:
        raise ValueError("track_id gera um canal interleaved inválido")
    return b"$" + bytes([channel]) + struct.pack(">I", len(frame)) + frame


def adts_frames(data: bytes) -> Iterable[bytes]:
    """Separa um stream ADTS em frames (cabeçalho incluso)."""
    offset = 0
    while offset < len(data):
        if offset + 7 > len(data) or data[offset] != 0xFF or (data[offset + 1] & 0xF0) != 0xF0:
            raise ValueError(f"sync ADTS inválido no offset {offset}")
        header_len = 7 if data[offset + 1] & 0x01 else 9
        frame_len = ((data[offset + 3] & 0x03) << 11) | (data[offset + 4] << 3) | ((data[offset + 5] & 0xE0) >> 5)
        if frame_len < header_len or offset + frame_len > len(data):
            raise ValueError(f"tamanho de frame ADTS inválido ({frame_len}) no offset {offset}")
        yield data[offset : offset + frame_len]
        offset += frame_len


def build_frames(data: bytes, *, sample_rate: int, frame_ms: int, track_id: int) -> Iterable[bytes]:
    """Gera os frames prontos para enviar (DHAV + interleaved) a partir de AAC/ADTS."""
    seq = 0
    tick = int(time.monotonic() * 1000)
    timestamp = int(time.time())
    for payload in adts_frames(data):
        frame = pack_dhav_audio(payload, seq=seq, sample_rate=sample_rate, timestamp=timestamp, tick=tick)
        yield pack_dhhttp_interleaved(frame, track_id=track_id)
        seq += 1
        tick += frame_ms