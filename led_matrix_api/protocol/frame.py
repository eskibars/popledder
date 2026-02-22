from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

from .encoding import MAGIC0, MAGIC1, u16le_from, u16le, checksum16_sum

MAGIC = b"\xAA\x55"
FFFF  = b"\xFF\xFF"

@dataclass
class ParsedFrame:
    raw: bytes
    sno: int
    flags: int
    msg_type: int
    payload: bytes
    checksum_present: bool
    checksum_ok: Optional[bool]
    recv_ts: float

class BleFrameReassembler:
    """Reassembles frames with layout:
      AA55 FFFF LEN(2) SNO(2) FLAGS(1) TYPE(1) PAYLOAD [CHK16 if flags&0x80]
    total_len = len_field + 6
    """

    def __init__(self, *, max_buffer: int = 64_000):
        self._buf = bytearray()
        self._max_buffer = max_buffer

    def feed(self, data: bytes) -> List[ParsedFrame]:
        self._buf += data
        if len(self._buf) > self._max_buffer:
            self._buf = self._buf[-self._max_buffer:]

        out: List[ParsedFrame] = []
        while True:
            idx = self._find_magic(self._buf)
            if idx < 0:
                if len(self._buf) > 1:
                    self._buf = self._buf[-1:]
                return out

            if idx > 0:
                del self._buf[:idx]

            if len(self._buf) < 10:
                return out

            len_field = u16le_from(self._buf, 4)
            total_len = len_field + 6
            if total_len <= 0 or total_len > 65535:
                del self._buf[0:1]
                continue

            if len(self._buf) < total_len:
                return out

            frame_bytes = bytes(self._buf[:total_len])
            del self._buf[:total_len]

            parsed = self._parse_one(frame_bytes)
            if parsed:
                out.append(parsed)

    def _find_magic(self, buf: bytearray) -> int:
        for i in range(0, len(buf) - 1):
            if buf[i] == MAGIC0 and buf[i + 1] == MAGIC1:
                return i
        return -1

    def _parse_one(self, raw: bytes) -> Optional[ParsedFrame]:
        if len(raw) < 10:
            return None
        if raw[0] != MAGIC0 or raw[1] != MAGIC1:
            return None

        len_field = u16le_from(raw, 4)
        total_len = len_field + 6
        if total_len != len(raw):
            return None

        sno = u16le_from(raw, 6)
        flags = raw[8]
        msg_type = raw[9]

        checksum_present = (flags & 0x80) != 0
        if checksum_present:
            if len(raw) < 12:
                return None
            payload = raw[10:-2]
            got_chk = u16le_from(raw, len(raw) - 2)
            calc_chk = checksum16_sum(raw[:-2])
            checksum_ok = (got_chk == calc_chk)
        else:
            payload = raw[10:]
            checksum_ok = None

        return ParsedFrame(
            raw=raw,
            sno=sno,
            flags=flags,
            msg_type=msg_type,
            payload=payload,
            checksum_present=checksum_present,
            checksum_ok=checksum_ok,
            recv_ts=time.time(),
        )

def build_frame(*, sno: int, flags: int, msg_type: int, payload: bytes) -> bytes:
    use_chk = (flags & 0x80) != 0
    chk_len = 2 if use_chk else 0
    len_field = len(payload) + chk_len + 4  # SNO+FLAGS+TYPE

    frame = bytearray()
    frame += MAGIC
    frame += FFFF
    frame += u16le(len_field)
    frame += u16le(sno & 0xFFFF)
    frame += bytes([flags & 0xFF, msg_type & 0xFF])
    frame += payload
    if use_chk:
        chk = checksum16_sum(bytes(frame))
        frame += u16le(chk)
    return bytes(frame)
