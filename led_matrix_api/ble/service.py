from __future__ import annotations

import asyncio
import threading
import time
import concurrent.futures
from typing import List, Optional, Dict, Any

try:
    from bleak import BleakClient  # type: ignore
except Exception as e:  # pragma: no cover
    BleakClient = None  # type: ignore
    _BLEAK_IMPORT_ERROR = e
else:
    _BLEAK_IMPORT_ERROR = None


from ..config import BleUuids, Settings
from ..protocol.encoding import iter_chunks
from ..protocol.frame import BleFrameReassembler, ParsedFrame, build_frame
from .acks import AckTracker, AckEvent

class LedBleService:
    """Bleak client wrapper with a background asyncio loop.

    This is designed so synchronous Flask routes can call into BLE safely.
    """

    def __init__(self, address: str, *, settings: Settings | None = None, uuids: BleUuids | None = None):
        self.address = address
        self.settings = settings or Settings.from_env()
        self.uuids = uuids or BleUuids()

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        self._client: Optional[BleakClient] = None
        self._lock = threading.Lock()
        self._sno = 1

        self.last_notifications: List[bytes] = []
        self.last_frames: List[bytes] = []

        self.reasm = BleFrameReassembler()
        self.acks = AckTracker()
        self.parsed_frames: List[ParsedFrame] = []
        self.ack_events: List[AckEvent] = []

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run_coro_sync(self, coro, timeout: Optional[float] = None):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            fut.cancel()
            raise

    def is_connected(self) -> bool:
        c = self._client
        return bool(c and c.is_connected)

    async def _notify_handler(self, _char, data: bytearray):
        raw = bytes(data)
        self.last_notifications.append(raw)
        self.last_notifications = self.last_notifications[-200:]

        frames = self.reasm.feed(raw)
        for f in frames:
            self.parsed_frames.append(f)
            self.parsed_frames = self.parsed_frames[-200:]

            self.last_frames.append(f.raw)
            self.last_frames = self.last_frames[-200:]

            ev = self.acks.on_frame(f)
            if ev:
                self.ack_events.append(ev)
                self.ack_events = self.ack_events[-200:]

    async def _connect_async(self):
        if BleakClient is None:  # pragma: no cover
            raise RuntimeError(f"bleak is not installed or failed to import: {_BLEAK_IMPORT_ERROR}")

        if self._client and self._client.is_connected:
            return True
        self._client = BleakClient(self.address)
        await self._client.connect()
        await self._client.start_notify(self.uuids.notify, self._notify_handler)
        return True

    def connect(self) -> bool:
        return bool(self.run_coro_sync(self._connect_async()))

    async def _disconnect_async(self):
        if not self._client:
            return True
        try:
            if self._client.is_connected:
                try:
                    await self._client.stop_notify(self.uuids.notify)
                except Exception:
                    pass
                await self._client.disconnect()
        finally:
            self._client = None
        return True

    def disconnect(self) -> bool:
        return bool(self.run_coro_sync(self._disconnect_async()))

    async def _write_frame_async(self, frame: bytes):
        if not (self._client and self._client.is_connected):
            raise RuntimeError("Not connected")
        for chunk in iter_chunks(frame, self.settings.ble_write_chunk):
            await self._client.write_gatt_char(self.uuids.write, chunk, response=False)
            await asyncio.sleep(0.015)

    def _next_sno(self) -> int:
        with self._lock:
            sno = self._sno
            self._sno = (self._sno + 1) & 0xFFFF
            if self._sno == 0:
                self._sno = 1
            return sno

    async def send_and_wait_ack(self, *, flags: int, msg_type: int, payload: bytes, timeout_s: float = 2.0) -> Dict[str, Any]:
        sno = self._next_sno()
        self.acks.mark_in_flight(sno)
        try:
            frame = build_frame(sno=sno, flags=flags, msg_type=msg_type, payload=payload)
            await self._write_frame_async(frame)
            ev = await self.acks.wait_for_ack(sno, timeout_s=timeout_s)
            return {"sno": sno, "acked": True, "ack_kind": ev.kind, "ack_frame_type": ev.frame.msg_type}
        except asyncio.TimeoutError:
            return {"sno": sno, "acked": False}
        finally:
            self.acks.clear_in_flight(sno)

    def send_and_wait_ack_sync(self, *, flags: int, msg_type: int, payload: bytes, timeout_s: float = 2.0) -> Dict[str, Any]:
        return self.run_coro_sync(
            self.send_and_wait_ack(flags=flags, msg_type=msg_type, payload=payload, timeout_s=timeout_s),
            timeout=timeout_s + 2.0,
        )

    def send_payload(self, *, flags: int, msg_type: int, payload: bytes) -> Dict[str, Any]:
        sno = self._next_sno()
        frame = build_frame(sno=sno, flags=flags, msg_type=msg_type, payload=payload)
        self.run_coro_sync(self._write_frame_async(frame))
        return {"sno": sno, "frame_len": len(frame)}

    def send_many_payloads(self, *, flags: int, msg_type: int, payloads: List[bytes]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for i, p in enumerate(payloads):
            results.append(self.send_payload(flags=flags, msg_type=msg_type, payload=p))
            if i < len(payloads) - 1:
                time.sleep(0.05)
        return results
