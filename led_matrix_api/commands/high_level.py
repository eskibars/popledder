from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import io
from PIL import Image

from ..config import Settings
from ..protocol.encoding import encode_len

from .protocol_builders import (
    build_rect_def_payload,
    build_text_header_packet_minimal,
    build_text_stream_bytes,
    stream_packets_for_bytes,
    build_gif_from_image,
    build_gif_normalized_from_bytes,
    build_pkts_program_header_payload,
    build_pkts_program_graphic_item_header,
)

def cmd_power_payload(on: bool) -> bytes:
    state = 1 if on else 0
    return bytes([0x04]) + encode_len(2) + bytes([0x00, state])

def cmd_brightness_payload_fixed(value: int, type_: int = 0) -> bytes:
    v = int(value)
    if v <= 0:
        v = 15
    return bytes([0x06]) + encode_len(2) + bytes([type_ & 0xFF, v & 0xFF])

def cmd_brightness_payload_schedule(entries: List[dict]) -> bytes:
    count = len(entries)
    body = bytearray()
    body.append(count & 0xFF)
    for e in entries:
        v = int(e.get("value", 15))
        if v <= 0:
            v = 15
        t = str(e.get("time", "00:00"))
        hh = int(t[0:2])
        mm = int(t[3:5])
        body += bytes([v & 0xFF, hh & 0xFF, mm & 0xFF])
    return bytes([0x06]) + encode_len(len(body)) + bytes(body)

def rt_show_text_payloads(
    *,
    settings: Settings,
    text: str = "",
    id_pro: int = 1,
    id_rect: int = 1,
    id_item: int = 1,
    data_save: int = 0,
    font_color: Optional[int] = None,
    bg_color: Optional[int] = None,
    code: int = 1,
    font: int = 0,
    size: int = 16,
    align_horizontal: Optional[str] = None,
    align_vertical: Optional[str] = None,
    rotate: int = 0,
    space_line: int = 0,
    space_font: int = 0,
    blocks: Optional[List[Dict[str, Any]]] = None,
    control_mode: str = "loop",
    control_value: int = 0,
    anim_type: int = 1,
    anim_speed: int = 9,
    anim_time_stay: int = 3,
    include_anim: bool = True,
    interval: int = 0,
) -> List[bytes]:
    rotate90 = (int(rotate or 0) % 360) == 90
    header = build_text_header_packet_minimal(
        data_save=data_save,
        id_pro=id_pro,
        id_rect=id_rect,
        id_item=id_item,
        control_mode=control_mode,
        control_value=control_value,
        anim_type=anim_type,
        anim_speed=anim_speed,
        anim_time_stay=anim_time_stay,
        include_anim=include_anim,
        interval=interval,
        code=int(code),
        font=int(font),
        size=int(size),
        rotate90=rotate90,
    )
    stream_bytes = build_text_stream_bytes(
        text=text,
        font_color=font_color,
        bg_color=bg_color,
        code=int(code),
        font=int(font),
        size=int(size),
        align_horizontal=align_horizontal,
        align_vertical=align_vertical,
        rotate=int(rotate or 0),
        space_line=int(space_line or 0),
        space_font=int(space_font or 0),
        blocks=blocks,
    )
    stream_pkts = stream_packets_for_bytes(
        data_save=data_save,
        id_pro=id_pro,
        id_rect=id_rect,
        id_item=id_item,
        data=stream_bytes,
        settings=settings,
    )
    rect_def = build_rect_def_payload(data_save=data_save, id_pro=id_pro, id_rect=id_rect)
    return [rect_def, header] + stream_pkts

def pkts_program_gif_payloads(
    *,
    settings: Settings,
    gif_bytes: bytes,
    id_pro: int = 1,
    id_rect: int = 1,
    id_item: int = 1,
    data_save: int = 0,
    target_size: Optional[Tuple[int, int]] = (64, 64),
) -> List[bytes]:
    w, h = target_size if target_size else (64, 64)
    program_header = build_pkts_program_header_payload(
        data_save=data_save,
        id_pro=id_pro,
        id_rect=id_rect,
        width=int(w),
        height=int(h),
    )
    normalized_gif = build_gif_normalized_from_bytes(
        gif_bytes,
        target_size=target_size,
        dither=False,
    )
    stream_pkts = stream_packets_for_bytes(
        data_save=data_save,
        id_pro=id_pro,
        id_rect=id_rect,
        id_item=id_item,
        data=normalized_gif,
        settings=settings,
    )
    
    item_header = build_pkts_program_graphic_item_header(
        data_save=data_save,
        id_pro=id_pro,
        id_rect=id_rect,
        id_item=id_item,
        anim_time_stay=0,
    )
    return [program_header, item_header] + stream_pkts

def pkts_program_image_payloads(
    *,
    settings: Settings,
    image_bytes: bytes,
    mode: str = "gif",
    target_size: Optional[Tuple[int, int]] = (64, 64),
    id_pro: int = 1,
    id_rect: int = 1,
    id_item: int = 1,
    data_save: int = 0,
) -> List[bytes]:
    img = Image.open(io.BytesIO(image_bytes))
    m = (mode or "gif").lower().strip()
    is_source_gif = len(image_bytes) >= 3 and image_bytes[:3] == b"GIF"
    if m == "gif" and is_source_gif:
        # Preserve original animated GIF frames.
        data = build_gif_normalized_from_bytes(image_bytes, target_size=target_size, dither=False)
    else:
        # Static image path: single-frame GIF transport is reliable on this panel.
        data = build_gif_from_image(img, target_size=target_size, dither=False, clear_first=False)

    w, h = target_size if target_size else img.size
    program_header = build_pkts_program_header_payload(
        data_save=data_save,
        id_pro=id_pro,
        id_rect=id_rect,
        width=int(w),
        height=int(h),
    )
    stream_pkts = stream_packets_for_bytes(
        data_save=data_save,
        id_pro=id_pro,
        id_rect=id_rect,
        id_item=id_item,
        data=data,
        settings=settings,
    )
    item_header = build_pkts_program_graphic_item_header(
        data_save=data_save,
        id_pro=id_pro,
        id_rect=id_rect,
        id_item=id_item,
        anim_time_stay=0,
    )
    return [program_header, item_header] + stream_pkts
