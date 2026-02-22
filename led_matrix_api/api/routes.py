from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request, render_template

from ..ble.service import LedBleService
from ..config import Settings
from ..commands.high_level import (
    cmd_power_payload,
    cmd_brightness_payload_fixed,
    cmd_brightness_payload_schedule,
    rt_show_text_payloads,
    rt_show_gif_payloads,
    rt_show_image_payloads,
)
from ..commands.protocol_builders import build_dispatch_play_payload
from ..models.animations import TextAnimation, TEXT_ANIMATION_ALIASES, TEXT_ANIMATION_DESCRIPTIONS, parse_text_animation, clamp_anim_speed
from ..utils.hex import ack_to_dict

def make_blueprint(*, ble: LedBleService | None, settings: Settings) -> Blueprint:
    bp = Blueprint("matrix", __name__)

    @bp.get("/api/status")
    def api_status():
        if not ble:
            return jsonify({"ok": False, "error": "DEVICE_ADDRESS not set"}), 500
        return jsonify({
            "ok": True,
            "connected": ble.is_connected(),
            "device": ble.address,
            "notify_uuid": ble.uuids.notify,
            "write_uuid": ble.uuids.write,
            "last_notifications_count": len(ble.last_notifications),
            "last_notification_hex": ble.last_notifications[-1].hex() if ble.last_notifications else None,
        })

    @bp.post("/api/connect")
    def api_connect():
        if not ble:
            return jsonify({"ok": False, "error": "DEVICE_ADDRESS not set"}), 500
        try:
            ble.connect()
            return jsonify({"ok": True, "connected": ble.is_connected()})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @bp.post("/api/disconnect")
    def api_disconnect():
        if not ble:
            return jsonify({"ok": False, "error": "DEVICE_ADDRESS not set"}), 500
        try:
            ble.disconnect()
            return jsonify({"ok": True, "connected": ble.is_connected()})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @bp.post("/api/power")
    def api_power():
        if not ble:
            return jsonify({"ok": False, "error": "DEVICE_ADDRESS not set"}), 500
        body = request.get_json(force=True, silent=True) or {}
        on = bool(body.get("on", True))
        wait_ack = bool(body.get("wait_ack", False))
        ack_timeout_s = float(body.get("ack_timeout_s", 2.0))
        try:
            if not ble.is_connected():
                ble.connect()
            payload = cmd_power_payload(on)
            if wait_ack:
                res = ble.send_and_wait_ack_sync(flags=settings.rt_show_flags, msg_type=settings.rt_show_type, payload=payload, timeout_s=ack_timeout_s)
                return jsonify({"ok": True, "sent": res, "payload_hex": payload.hex()})
            res = ble.send_payload(flags=settings.rt_show_flags, msg_type=settings.rt_show_type, payload=payload)
            return jsonify({"ok": True, "sent": res, "payload_hex": payload.hex()})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @bp.post("/api/brightness")
    def api_brightness():
        if not ble:
            return jsonify({"ok": False, "error": "DEVICE_ADDRESS not set"}), 500
        body = request.get_json(force=True, silent=True) or {}
        mode = body.get("mode", "fixed")
        wait_ack = bool(body.get("wait_ack", False))
        ack_timeout_s = float(body.get("ack_timeout_s", 2.0))
        try:
            if not ble.is_connected():
                ble.connect()
            if mode == "schedule":
                payload = cmd_brightness_payload_schedule(body.get("entries", []))
            else:
                payload = cmd_brightness_payload_fixed(body.get("value", 15), type_=body.get("type", 0))

            if wait_ack:
                res = ble.send_and_wait_ack_sync(flags=settings.rt_show_flags, msg_type=0x04, payload=payload, timeout_s=ack_timeout_s)
            else:
                res = ble.send_payload(flags=settings.rt_show_flags, msg_type=0x04, payload=payload)
            return jsonify({"ok": True, "sent": res, "payload_hex": payload.hex()})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @bp.post("/api/text")
    def api_text():
        if not ble:
            return jsonify({"ok": False, "error": "DEVICE_ADDRESS not set"}), 500
        body = request.get_json(force=True, silent=True) or {}
        text = str(body.get("text", ""))
        blocks = body.get("blocks") or body.get("list_text")
        if (text is None or text == "") and not blocks:
            return jsonify({"ok": False, "error": "text is required"}), 400
        try:
            if not ble.is_connected():
                ble.connect()

            payloads = rt_show_text_payloads(
                settings=settings,
                text=text,
                id_pro=int(body.get("id_pro", 1)),
                id_rect=int(body.get("id_rect", 1)),
                id_item=int(body.get("id_item", 1)),
                data_save=int(body.get("data_save", 0)),
                font_color=(body.get("font_color") if "font_color" in body else body.get("color")),
                bg_color=(body.get("bg_color") if "bg_color" in body else body.get("color_bg")),
                code=int(body.get("code", 1)),
                font=int(body.get("font", 0)),
                size=int(body.get("size", 16)),
                align_horizontal=body.get("align_horizontal") or body.get("alignHorizontal"),
                align_vertical=body.get("align_vertical") or body.get("alignVertical"),
                rotate=int(body.get("rotate", 0)),
                space_line=int(body.get("space_line", 0)),
                space_font=int(body.get("space_font", 0)),
                blocks=blocks,
                control_mode=str(body.get("control_mode", "loop")),
                control_value=int(body.get("control_value", 0)),
                anim_type=parse_text_animation(body.get("anim") or body.get("animation") or body.get("anim_type") or body.get("type_ani") or body.get("typeAni"), default=1),
                anim_speed=clamp_anim_speed(body.get("anim_speed") or body.get("speed") or body.get("speed_raw") or (int(body.get("speed_ui")) if "speed_ui" in body else None) or 9, default=9),
                anim_time_stay=int(body.get("anim_time_stay", body.get("time_stay", 3))),
                include_anim=bool(body.get("include_anim", True)),
                interval=int(body.get("interval", 0)),
            )
            msg_type = int(body.get("msg_type", settings.rt_show_type))
            res = ble.send_many_payloads(flags=settings.rt_show_flags, msg_type=msg_type, payloads=payloads)

            play_loop = int(body.get("play_loop", 1)) if str(body.get("play_loop", "")).strip() != "" else 1
            dispatch_payload = build_dispatch_play_payload(
                id_pro=int(body.get("id_pro", 1)),
                play_loop=play_loop,
                ignore_pgm_cmd=int(body.get("ignore_pgm_cmd", 0)),
            )
            ble.send_payload(flags=settings.rt_show_flags, msg_type=settings.rt_show_type, payload=dispatch_payload)

            return jsonify({"ok": True, "sent_count": len(res) + 1, "sent": res + [{"sno": None, "frame_len": len(dispatch_payload), "kind": "dispatch_play"}]})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @bp.get("/api/text/animations")
    def api_text_animations():
        animations = []
        aliases_by_id: Dict[int, List[str]] = {}
        for k, v in TEXT_ANIMATION_ALIASES.items():
            aliases_by_id.setdefault(int(v), []).append(k)
        for anim in TextAnimation:
            aid = int(anim.value)
            animations.append({
                "id": aid,
                "name": anim.name,
                "description": TEXT_ANIMATION_DESCRIPTIONS.get(aid, ""),
                "aliases": sorted(set(aliases_by_id.get(aid, []))),
            })
        animations.sort(key=lambda x: x["id"])
        return jsonify({"ok": True, "speed_range": [1, 15], "animations": animations})

    @bp.post("/api/gif")
    def api_gif():
        if not ble:
            return jsonify({"ok": False, "error": "DEVICE_ADDRESS not set"}), 500
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "file is required"}), 400
        b = request.files["file"].read()
        if not (len(b) >= 3 and b[0:3] == b"GIF"):
            return jsonify({"ok": False, "error": "Not a GIF (missing GIF header)"}), 400
        try:
            if not ble.is_connected():
                ble.connect()
            payloads = rt_show_gif_payloads(
                settings=settings,
                gif_bytes=b,
                id_pro=int(request.form.get("id_pro", 1)),
                id_rect=int(request.form.get("id_rect", 1)),
                id_item=int(request.form.get("id_item", 1)),
                data_save=int(request.form.get("data_save", 0)),
                control_mode_=request.form.get("control_mode", "loop"),
                control_value_=int(request.form.get("control_value", 0)),
            )
            msg_type = int(request.form.get("msg_type", settings.rt_show_type))
            res = ble.send_many_payloads(flags=settings.rt_show_flags, msg_type=msg_type, payloads=payloads)
            return jsonify({"ok": True, "sent_count": len(res), "sent": res})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @bp.post("/api/image")
    def api_image():
        if not ble:
            return jsonify({"ok": False, "error": "DEVICE_ADDRESS not set"}), 500
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "file is required"}), 400
        b = request.files["file"].read()
        try:
            if not ble.is_connected():
                ble.connect()
            payloads = rt_show_image_payloads(
                settings=settings,
                image_bytes=b,
                mode=str(request.form.get("mode", "gif")),
                target_size=(int(request.form.get("w", 64)), int(request.form.get("h", 64))) if request.form.get("w") or request.form.get("h") else (64, 64),
                id_pro=int(request.form.get("id_pro", 1)),
                id_rect=int(request.form.get("id_rect", 1)),
                id_item=int(request.form.get("id_item", 1)),
                data_save=int(request.form.get("data_save", 0)),
                control_mode_=request.form.get("control_mode", "loop"),
                control_value_=int(request.form.get("control_value", 0)),
            )
            msg_type = int(request.form.get("msg_type", settings.rt_show_type))
            res = ble.send_many_payloads(flags=settings.rt_show_flags, msg_type=msg_type, payloads=payloads)
            return jsonify({"ok": True, "sent_count": len(res), "sent": res})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @bp.route("/api/debug/acks", methods=["GET", "DELETE"])
    def api_debug_acks():
        if not ble:
            return jsonify({"ok": False, "error": "DEVICE_ADDRESS not set"}), 500
        if request.method == "DELETE":
            ble.ack_events.clear()
            return jsonify({"ok": True, "cleared": True})
        limit = int(request.args.get("limit", 50))
        acked_filter = request.args.get("acked_sno")
        include_payload = request.args.get("include_payload", "1") == "1"
        events = ble.ack_events[-limit:]
        if acked_filter is not None:
            try:
                target = int(acked_filter)
                events = [e for e in events if e.acked_sno == target]
            except ValueError:
                return jsonify({"ok": False, "error": "acked_sno must be int"}), 400
        result = []
        for ev in events:
            d = ack_to_dict(ev)
            if not include_payload:
                d.pop("payload_hex", None)
            result.append(d)
        return jsonify({"ok": True, "count": len(result), "acks": result})

    @bp.route("/api/debug/frames", methods=["GET", "DELETE"])
    def api_debug_frames():
        if not ble:
            return jsonify({"ok": False, "error": "DEVICE_ADDRESS not set"}), 500
        if request.method == "DELETE":
            ble.parsed_frames.clear()
            return jsonify({"ok": True, "cleared": True})
        limit = int(request.args.get("limit", 50))
        type_filter = request.args.get("type")
        sno_filter = request.args.get("sno")
        checksum_ok_filter = request.args.get("checksum_ok")
        include_payload = request.args.get("include_payload", "1") == "1"
        include_raw = request.args.get("include_raw", "0") == "1"
        frames = ble.parsed_frames[-limit:] if limit > 0 else ble.parsed_frames

        if type_filter is not None:
            try:
                t = int(type_filter)
                frames = [f for f in frames if f.msg_type == t]
            except ValueError:
                return jsonify({"ok": False, "error": "type must be int"}), 400
        if sno_filter is not None:
            try:
                s = int(sno_filter)
                frames = [f for f in frames if f.sno == s]
            except ValueError:
                return jsonify({"ok": False, "error": "sno must be int"}), 400
        if checksum_ok_filter is not None:
            if checksum_ok_filter not in ("0", "1"):
                return jsonify({"ok": False, "error": "checksum_ok must be 0 or 1"}), 400
            want = checksum_ok_filter == "1"
            frames = [f for f in frames if f.checksum_present and f.checksum_ok == want]

        out = []
        for f in frames:
            d: Dict[str, Any] = {
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
            if include_raw:
                d["raw_hex"] = f.raw.hex()
            out.append(d)
        return jsonify({"ok": True, "count": len(out), "frames": out})

    @bp.get("/")
    def control_panel():
        return render_template("control_panel.html")

    return bp
