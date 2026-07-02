"""In-process WebSocket fan-out to connected dashboards.

Single-instance broadcaster. For multi-instance deployments this would sit
behind Redis pub/sub (noted in docs/BUILD_PLAN.md); the publish() interface
stays the same.
"""
from fastapi import WebSocket


class Broadcaster:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)

    async def publish(self, message: dict) -> None:
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


broadcaster = Broadcaster()
