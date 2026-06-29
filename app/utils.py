import base64
import io
import json
import math
import time
import uuid
from typing import Any, Dict, Generator

import qrcode
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


def _serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key=secret_key, salt="qr-attendance")


def make_session_token(secret_key: str, session_id: int) -> str:
    """Create a short-lived signed token embedded in the QR scan URL."""
    payload = {
        "sid": int(session_id),
        "jti": uuid.uuid4().hex,
        "iat": int(time.time()),
    }
    return _serializer(secret_key).dumps(payload)


def verify_session_token(secret_key: str, token: str, max_age_seconds: int) -> Dict[str, Any]:
    """Verify signed token and enforce expiry."""
    data = _serializer(secret_key).loads(token, max_age=max_age_seconds)
    if not isinstance(data, dict) or "sid" not in data:
        raise BadSignature("Invalid token payload")
    return data


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters using the Haversine formula."""
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def qr_png_base64(text: str) -> str:
    """Return PNG bytes base64 (without data: prefix) for quick embedding."""
    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# --- Real-time (SSE) helpers ---
# In-memory pub/sub queues (fine for demo + final year project)

_SESSION_SUBSCRIBERS: Dict[int, list] = {}


def sse_push(session_id: int, event: Dict[str, Any]) -> None:
    """Publish an event to all subscribers of the session."""
    payload = json.dumps(event)
    for q in list(_SESSION_SUBSCRIBERS.get(session_id, [])):
        try:
            q.put_nowait(payload)
        except Exception:
            pass


def sse_stream_generator(session_id: int) -> Generator[str, None, None]:
    """SSE generator: yields keep-alive pings + attendance events."""
    import queue

    q = queue.Queue()
    _SESSION_SUBSCRIBERS.setdefault(session_id, []).append(q)

    # First message so browser knows connection is ok
    yield "event: ping\ndata: {}\n\n"

    try:
        while True:
            try:
                msg = q.get(timeout=15)
                yield f"event: attendance\ndata: {msg}\n\n"
            except queue.Empty:
                yield "event: ping\ndata: {}\n\n"
    finally:
        subs = _SESSION_SUBSCRIBERS.get(session_id, [])
        if q in subs:
            subs.remove(q)
