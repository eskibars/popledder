from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
import io

from ..config import Settings
from ..protocol.encoding import (
    u16le,
    encode_len,
    tlv,
    tlv_fixed_u8,
    id_to_wire_u8,
    rgb3,
    rgb24_swap_rb,
)
from ..models.animations import clamp_anim_speed, parse_text_animation

def build_rect_def_payload(*, data_save: int, id_pro: int, id_rect: int, x: int = 0, y: int = 0, w: int = 64, h: int = 64, n_flag: int = 0) -> bytes:
    b = bytearray()
    b += tlv_fixed_u8(9, 1 - int(data_save))
    b += tlv_fixed_u8(12, id_to_wire_u8(id_pro))
    b += tlv_fixed_u8(13, id_to_wire_u8(id_rect))
    b += bytes([29, 9])
    b += u16le(x & 0xFFFF)
    b += u16le(y & 0xFFFF)
    b += u16le(w & 0xFFFF)
    b += u16le(h & 0xFFFF)
    b += bytes([n_flag & 0xFF])
    return bytes(b)

def control_bytes(mode: str, value: int) -> bytes:
    m = 0 if mode == "loop" else 1
    return bytes([m & 0xFF]) + u16le(int(value) & 0xFFFF)

def build_m_header_packet(
    *,
    data_save: int,
    id_pro: int,
    id_rect: int,
    id_item: int,
    control_mode: str,
    control_value: int,
    anim: Optional[dict] = None,
) -> bytes:
    out = bytearray()
    out += tlv_fixed_u8(9, 1 - int(data_save))
    out += tlv_fixed_u8(12, id_to_wire_u8(id_pro))
    out += tlv_fixed_u8(13, id_to_wire_u8(id_rect))
    out += tlv_fixed_u8(14, id_to_wire_u8(id_item))

    if anim:
        a_type = int(anim.get("type", 0)) & 0xFF
        speed = int(anim.get("speed", 0)) & 0xFF
        time_stay = int(anim.get("time_stay", 0)) & 0xFF
        out += tlv(20, bytes([a_type, speed, 0x00, time_stay]))

    val = control_bytes(control_mode, control_value) + bytes([0x0A])
    out += tlv(17, val)
    return bytes(out)

def build_text_header_packet_minimal(
    *,
    data_save: int,
    id_pro: int,
    id_rect: int,
    id_item: int,
    code: int = 1,
    font: int = 0,
    size: int = 16,
    rotate90: bool = False,
    interval: int = 0,
    control_mode: str = "loop",
    control_value: int = 0,
    text_kind: str = "text",
    anim_type: int = 1,
    anim_speed: int = 9,
    anim_time_stay: int = 3,
    include_anim: bool = True,
) -> bytes:
    out = bytearray()
    out += tlv_fixed_u8(9, 1 - int(data_save))
    out += tlv_fixed_u8(12, id_to_wire_u8(id_pro))
    out += tlv_fixed_u8(13, id_to_wire_u8(id_rect))
    out += tlv_fixed_u8(14, id_to_wire_u8(id_item))

    out += bytes([25, 4, 2, id_to_wire_u8(id_pro), id_to_wire_u8(id_rect), id_to_wire_u8(id_item)])

    if include_anim:
        out += bytes([20, 3, int(anim_type) & 0xFF, int(anim_speed) & 0xFF, int(anim_time_stay) & 0xFF])

    o = 9 if text_kind == "text_audio" else 6
    rot = 3 if rotate90 else 0

    val = bytearray()
    val += control_bytes(control_mode, control_value)
    val += bytes([o & 0xFF])
    val += bytes([int(code) & 0xFF, int(font) & 0xFF, int(size) & 0xFF, rot & 0xFF])
    val += u16le(int(interval) & 0xFFFF)
    out += tlv(17, bytes(val))
    return bytes(out)

def build_text_layout_prefix(
    *,
    align_horizontal: Optional[str] = None,
    align_vertical: Optional[str] = None,
    rotate: int = 0,
    space_line: int = 0,
    space_font: int = 0,
) -> bytes:
    line = 0
    page = 0
    font_flag = 0

    ah = (align_horizontal or "").lower().strip()
    if ah in ("left", "l"):
        line = 0
    elif ah in ("center", "centre", "c", "middle"):
        line = 1
    elif ah in ("right", "r"):
        line = 2

    av = (align_vertical or "").lower().strip()
    if av in ("top", "t"):
        page = 0
    elif av in ("center", "centre", "c", "middle"):
        page = 1
    elif av in ("bottom", "b", "down"):
        page = 2

    rot = int(rotate or 0) % 360
    if rot > 0:
        if rot == 270:
            font_flag = 1
        elif rot == 90:
            page, line = line, page

    out = bytearray()
    out += bytes([3, 0, page, 3, 1, line])
    if font_flag > 0:
        out += bytes([3, 2, font_flag])

    if rot > 0:
        out += bytes([2, int(rot / 90) & 0xFF])

    sl = int(space_line or 0)
    sf = int(space_font or 0)
    if sl != 0:
        out += bytes([4, 0, sl & 0xFF])
    if sf != 0:
        out += bytes([4, 1, sf & 0xFF])
    return bytes(out)

def build_text_stream_bytes(
    *,
    text: str = "",
    font_color: Optional[int] = None,
    bg_color: Optional[int] = None,
    code: int = 1,
    font: int = 0,
    size: int = 16,
    include_font_update: bool = True,
    align_horizontal: Optional[str] = None,
    align_vertical: Optional[str] = None,
    rotate: int = 0,
    space_line: int = 0,
    space_font: int = 0,
    blocks: Optional[List[Dict[str, Any]]] = None,
) -> bytes:
    body = bytearray()
    body += build_text_layout_prefix(
        align_horizontal=align_horizontal,
        align_vertical=align_vertical,
        rotate=rotate,
        space_line=space_line,
        space_font=space_font,
    )

    def _emit_segment(seg_text: str, seg_fc: Optional[int], seg_bc: Optional[int], seg_code: int, seg_font: int, seg_size: int):
        nonlocal body
        if seg_fc is not None or seg_bc is not None:
            fc = rgb24_swap_rb(int(seg_fc or 0))
            bc = rgb24_swap_rb(int(seg_bc or 0))
            body += bytes([0x00]) + rgb3(fc) + rgb3(bc)
        if include_font_update:
            body += bytes([0x01, int(seg_code) & 0xFF, int(seg_font) & 0xFF, int(seg_size) & 0xFF])
        if int(seg_code) < 16:
            txt = (seg_text or "").encode("gbk", errors="replace")
        else:
            txt = (seg_text or "").encode("utf-8", errors="replace")
        body += txt

    if blocks:
        for b in blocks:
            _emit_segment(
                str(b.get("text", "")),
                (b.get("font_color") if "font_color" in b else b.get("color", font_color)),
                (b.get("bg_color") if "bg_color" in b else b.get("color_bg", bg_color)),
                int(b.get("code", code)),
                int(b.get("font", font)),
                int(b.get("size", size)),
            )
    else:
        _emit_segment(text, font_color, bg_color, int(code), int(font), int(size))
    return bytes(body)

def build_stream_chunk_packet(
    *,
    data_save: int,
    id_pro: int,
    id_rect: int,
    id_item: int,
    chunk_count: int,
    chunk_index: int,
    payload: bytes,
    stream_chunk: int,
) -> bytes:
    out = bytearray()
    out += tlv_fixed_u8(9, 1 - int(data_save))
    out += tlv_fixed_u8(12, id_to_wire_u8(id_pro))
    out += tlv_fixed_u8(13, id_to_wire_u8(id_rect))
    out += tlv_fixed_u8(14, id_to_wire_u8(id_item))

    out += bytes([0x12, 0x07])
    out += u16le(chunk_count)
    out += u16le(chunk_index)
    out += u16le(stream_chunk)
    out += bytes([0x00])
    out += bytes([0x13])

    out += encode_len(len(payload))
    out += payload
    return bytes(out)

def stream_packets_for_bytes(
    *,
    data_save: int,
    id_pro: int,
    id_rect: int,
    id_item: int,
    data: bytes,
    settings: Settings,
) -> List[bytes]:
    stream_chunk = settings.stream_chunk
    chunks = [data[i:i+stream_chunk] for i in range(0, len(data), stream_chunk)]
    c = len(chunks)
    packets: List[bytes] = []
    for idx, payload in enumerate(chunks):
        packets.append(build_stream_chunk_packet(
            data_save=data_save,
            id_pro=id_pro,
            id_rect=id_rect,
            id_item=id_item,
            chunk_count=c,
            chunk_index=idx,
            payload=payload,
            stream_chunk=stream_chunk,
        ))
    return packets

def build_dispatch_play_payload(*, id_pro: int, play_loop: int = 1, ignore_pgm_cmd: int = 0) -> bytes:
    p = max(0, int(id_pro) - 1) & 0xFF
    loop = max(1, int(play_loop)) & 0xFFFF
    play_mode = 0
    return bytes([24, 6, 2, p, ignore_pgm_cmd & 0xFF, play_mode, loop & 0xFF, (loop >> 8) & 0xFF])

def build_ystp01_from_image(
    img: Image.Image,
    *,
    target_size: Optional[Tuple[int, int]] = (64, 64),
    mode: str = "rgb24",
    max_colors: int = 256,
) -> bytes:
    if target_size:
        img = img.resize(tuple(target_size), Image.Resampling.NEAREST)
    img = img.convert("RGB")
    w, h = img.size

    mode = (mode or "rgb24").lower().strip()
    if mode not in ("rgb24", "palette"):
        mode = "rgb24"

    if mode == "rgb24":
        raw = bytearray()
        for (r, g, b) in list(img.getdata()):
            raw += bytes([r, g, b])
        header = bytearray()
        header += b"YSTP01"
        header += u16le(w)
        header += u16le(h)
        header += u16le(1)
        header += u16le(0)
        header += bytes([24])
        return bytes(header + raw)

    pal_img = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=max_colors)

    color_count = min(max_colors, 256)
    if color_count <= 2:
        o = 1
    elif color_count <= 4:
        o = 2
    elif color_count <= 16:
        o = 4
    else:
        o = 8

    palette = pal_img.getpalette() or []
    needed_entries = 1 << o
    pal_bytes = bytearray()
    for i in range(needed_entries):
        base = 3 * i
        r = palette[base + 0] if base + 0 < len(palette) else 0
        g = palette[base + 1] if base + 1 < len(palette) else 0
        b = palette[base + 2] if base + 2 < len(palette) else 0
        pal_bytes += bytes([r, g, b])

    idxs = list(pal_img.getdata())

    packed = bytearray()
    if o == 8:
        packed += bytes(idxs)
    else:
        per_byte = 8 // o
        mask = (1 << o) - 1
        for y in range(h):
            row = idxs[y*w:(y+1)*w]
            i = 0
            while i < len(row):
                acc = 0
                for _ in range(per_byte):
                    acc <<= o
                    if i < len(row):
                        acc |= (row[i] & mask)
                    i += 1
                packed.append(acc & 0xFF)

    header = bytearray()
    header += b"YSTP01"
    header += u16le(w)
    header += u16le(h)
    header += u16le(1)
    header += u16le(len(pal_bytes))
    header += bytes([o & 0xFF])
    return bytes(header + pal_bytes + packed)

def build_gif_from_image(
    img: Image.Image,
    *,
    target_size: Optional[Tuple[int, int]] = (64, 64),
    dither: bool = False,
    clear_first: bool = True,
) -> bytes:
    if target_size:
        img = img.resize(tuple(target_size), Image.Resampling.NEAREST)
    img = img.convert("RGB")

    frames_rgb = []
    if clear_first:
        frames_rgb.append(Image.new("RGB", img.size, (0, 0, 0)))
    frames_rgb.append(img)

    frames_p = []
    for fr in frames_rgb:
        frames_p.append(
            fr.convert(
                "P",
                palette=Image.Palette.ADAPTIVE,
                colors=256,
                dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE,
            )
        )

    buf = io.BytesIO()
    frames_p[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames_p[1:],
        loop=0,
        duration=40,
        disposal=2,
        optimize=False,
    )
    return buf.getvalue()
