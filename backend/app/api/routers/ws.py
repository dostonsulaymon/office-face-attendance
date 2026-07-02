from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.services.broadcast import broadcaster

router = APIRouter()


@router.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket, token: str | None = Query(None)):
    # Dashboard WS auth via the same JWT, passed as a query param.
    if not token or not decode_access_token(token):
        await ws.close(code=4401)
        return
    await broadcaster.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive pings; content ignored
    except WebSocketDisconnect:
        broadcaster.disconnect(ws)
