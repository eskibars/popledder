from __future__ import annotations

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class BleUuids:
    service: str = "0000FFF0-0000-1000-8000-00805F9B34FB"
    notify: str  = "0000FFF1-0000-1000-8000-00805F9B34FB"
    write: str   = "0000FFF2-0000-1000-8000-00805F9B34FB"

@dataclass(frozen=True)
class Settings:
    device_address: str
    ble_write_chunk: int = 180
    stream_chunk: int = 960

    # Outer frame flags/type commonly used for rt_show
    rt_show_flags: int = 0xC1  # checksum enabled
    rt_show_type: int = 0x02

    # Flask
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = True

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            device_address=os.environ.get("DEVICE_ADDRESS", "").strip(),
            ble_write_chunk=int(os.environ.get("BLE_WRITE_CHUNK", "180")),
            stream_chunk=int(os.environ.get("STREAM_CHUNK", "960")),
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "5000")),
            debug=os.environ.get("DEBUG", "1") not in ("0", "false", "False", "no", "NO"),
        )
