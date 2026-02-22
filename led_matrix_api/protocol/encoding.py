from __future__ import annotations

from typing import Iterable

MAGIC0 = 0xAA
MAGIC1 = 0x55

def u16le_from(buf: bytes, off: int) -> int:
    return buf[off] | (buf[off + 1] << 8)

def u16le(n: int) -> bytes:
    return bytes((n & 0xFF, (n >> 8) & 0xFF))

def u32le(n: int) -> bytes:
    return bytes((
        n & 0xFF,
        (n >> 8) & 0xFF,
        (n >> 16) & 0xFF,
        (n >> 24) & 0xFF,
    ))

def checksum16_sum(data: bytes) -> int:
    return sum(data) & 0xFFFF

def encode_len(n: int) -> bytes:
    if n < 128:
        return bytes([n])
    if n < 256:
        return bytes([0x81, n])
    return bytes([0x82]) + u16le(n)

def tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag & 0xFF]) + encode_len(len(value)) + value

def tlv_fixed_u8(tag: int, value_u8: int) -> bytes:
    return bytes([tag & 0xFF, 0x01, value_u8 & 0xFF])

def id_to_wire_u8(v: int) -> int:
    v = int(v)
    if v == 0:
        return 0xFF
    if v < 0:
        raise ValueError("IDs must be >= 0")
    return (v - 1) & 0xFF

def rgb3(color: int) -> bytes:
    return bytes([(color >> 0) & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF])

def rgb24_swap_rb(rgb: int) -> int:
    rgb = int(rgb) & 0xFFFFFF
    r = (rgb >> 16) & 0xFF
    g = (rgb >> 8) & 0xFF
    b = (rgb >> 0) & 0xFF
    return (b << 16) | (g << 8) | r

def iter_chunks(buf: bytes, chunk_size: int):
    for i in range(0, len(buf), chunk_size):
        yield buf[i:i+chunk_size]
