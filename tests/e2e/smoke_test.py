import asyncio
import json

import pytest

from app.api.main import app as main_app


async def _asgi_get(path: str) -> tuple[int, bytes]:
    """Minimal ASGI GET runner for end-to-end HTTP smoke verification."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    sent_events = []
    request_sent = False
    response_done = asyncio.Event()

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await response_done.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        sent_events.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body", False):
            response_done.set()

    await main_app(scope, receive, send)
    status_code = next(e["status"] for e in sent_events if e["type"] == "http.response.start")
    body = b"".join(e.get("body", b"") for e in sent_events if e["type"] == "http.response.body")
    return status_code, body


@pytest.mark.asyncio
async def test_e2e_http_smoke_endpoints():
    # 1. Liveness probe
    status_live, body_live = await _asgi_get("/health/live")
    assert status_live == 200
    assert json.loads(body_live.decode("utf-8"))["status"] == "ok"

    # 2. Prometheus metrics endpoint
    status_metrics, body_metrics = await _asgi_get("/metrics")
    assert status_metrics == 200
    assert b"http_requests" in body_metrics or b"python_info" in body_metrics

    # 3. Protected API route rejects unauthenticated access (fail-closed)
    status_unauth, _ = await _asgi_get("/api/users/me/profile")
    assert status_unauth in (401, 403)

    # 4. Unknown route returns 404
    status_404, _ = await _asgi_get("/api/nonexistent_smoke_route")
    assert status_404 == 404
