from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from ..protocol.frame import ParsedFrame

ACK_TYPES: Set[int] = {0x82, 0x83, 0x84}

@dataclass
class AckEvent:
    frame: ParsedFrame
    acked_sno: Optional[int]
    kind: str  # e.g. "type82"

class AckTracker:
    def __init__(self):
        self._waiters: Dict[int, List[asyncio.Future]] = {}
        self._in_flight: Set[int] = set()
        self._events: List[AckEvent] = []

    def mark_in_flight(self, sno: int):
        self._in_flight.add(sno)

    def clear_in_flight(self, sno: int):
        self._in_flight.discard(sno)

    def on_frame(self, f: ParsedFrame) -> Optional[AckEvent]:
        if f.msg_type not in ACK_TYPES:
            return None
        acked = f.sno
        ev = AckEvent(frame=f, acked_sno=acked, kind=f"type{f.msg_type:02x}")
        self._events.append(ev)
        self._events = self._events[-200:]
        self._resolve_waiters(acked, ev)
        return ev

    async def wait_for_ack(self, sno: int, timeout_s: float = 2.0) -> AckEvent:
        fut = asyncio.get_running_loop().create_future()
        self._waiters.setdefault(sno, []).append(fut)
        try:
            return await asyncio.wait_for(fut, timeout=timeout_s)
        finally:
            lst = self._waiters.get(sno)
            if lst:
                self._waiters[sno] = [x for x in lst if not x.done()]
                if not self._waiters[sno]:
                    del self._waiters[sno]

    def _resolve_waiters(self, sno: int, ev: AckEvent):
        waiters = self._waiters.pop(sno, [])
        for fut in waiters:
            if not fut.done():
                fut.set_result(ev)
