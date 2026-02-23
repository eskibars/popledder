#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from urllib import error, request


def post_json(url: str, payload: dict, timeout_s: float = 5.0) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else {"ok": True}


def build_text_payload(*, align_h: str, align_v: str) -> dict:
    now = datetime.now()
    time_text = now.strftime("%H:%M:%S")
    day_text = now.strftime("%b %d")
    payload = {
      "align_horizontal": align_h,
      "align_vertical": align_v,
      "rotate": 0,
      "space_line": 0,
      "space_font": 0,
      "list_text": [
        {
          "text": time_text + "\n",
          "size": 16,
          "code": 1,
          "font": 0,
          "color": 16589591,
          "color_bg": 0
        },
        {
          "text": day_text,
          "size": 8,
          "code": 1,
          "font": 0,
          "color": 2368763,
          "color_bg": 0
        }
      ],
      "clear_before_send": True,
      "anim": "appear",
      "anim_speed": 1,
      "anim_time_stay": 3
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Clock demo app for matrix LED Flask API")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="API base URL")
    parser.add_argument("--interval", type=float, default=1.0, help="Refresh interval in seconds")
    parser.add_argument("--align-h", default="center", choices=["left", "center", "right"])
    parser.add_argument("--align-v", default="center", choices=["top", "center", "bottom"])
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/api/text"

    try:
        while True:
            payload = build_text_payload(
                align_h=args.align_h,
                align_v=args.align_v,
            )
            try:
                result = post_json(url, payload)
            except error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                print(f"HTTP {e.code}: {body}")
            except Exception as e:
                print(f"Request failed: {e}")
            time.sleep(max(0.1, args.interval))
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
