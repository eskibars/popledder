from __future__ import annotations

from typing import Any, Dict

def frame_to_dict(f: Any, include_payload: bool = True) -> Dict[str, Any]:
    d = {
        "recv_ts": f.recv_ts,
        "sno": f.sno,
        "flags": f.flags,
        "msg_type": f.msg_type,
        "checksum_present": f.checksum_present,
        "checksum_ok": f.checksum_ok,
        "payload_len": len(f.payload),
        "raw_len": len(f.raw),
    }
    if include_payload:
        d["payload_hex"] = f.payload.hex()
        d["raw_hex"] = f.raw.hex()
    return d

def ack_to_dict(ev: Any) -> Dict[str, Any]:
    status = ev.frame.payload[0] if len(ev.frame.payload) else None
    return {
        "recv_ts": ev.frame.recv_ts,
        "ack_kind": ev.kind,
        "ack_frame_sno": ev.frame.sno,
        "ack_frame_type": ev.frame.msg_type,
        "acked_sno": ev.acked_sno,
        "status": status,
        "payload_hex": ev.frame.payload.hex(),
    }
