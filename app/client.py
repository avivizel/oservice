from __future__ import annotations

import re

from fastapi import Request

_MOBILE = re.compile(
    r"Mobile|iPhone|iPod|Android.+Mobile|Windows Phone|Opera Mini|IEMobile|webOS|BlackBerry|MeeGo",
    re.I,
)
_TABLET = re.compile(r"iPad|Android(?!.*Mobile)|Tablet|Silk", re.I)


def detect_client(request: Request) -> str:
    forced = (request.query_params.get("view") or "").strip().lower()
    if forced in {"mobile", "desktop"}:
        return forced
    ua = request.headers.get("user-agent") or ""
    if _TABLET.search(ua) and "Mobile" not in ua:
        return "mobile"
    if _MOBILE.search(ua):
        return "mobile"
    return "desktop"


def client_context(request: Request) -> dict[str, object]:
    client = detect_client(request)
    return {
        "client": client,
        "is_mobile": client == "mobile",
        "view_locked": (request.query_params.get("view") or "").strip().lower() in {"mobile", "desktop"},
    }
