"""Async client for the server-side liveness / anti-spoofing microservice."""
import httpx

from app.core.config import get_settings

settings = get_settings()


class LivenessError(RuntimeError):
    pass


async def check(image: bytes) -> dict:
    """Return {is_live, score, label, face_detected, ...} for a captured frame."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            settings.liveness_url.rstrip("/") + "/check-liveness",
            files={"file": ("frame.jpg", image, "image/jpeg")},
        )
    if resp.status_code >= 400:
        raise LivenessError(f"liveness check failed ({resp.status_code}): {resp.text}")
    return resp.json()


async def is_live(image: bytes) -> tuple[bool, float]:
    """Apply the configured threshold. Returns (passed, score)."""
    data = await check(image)
    score = float(data.get("score", 0.0))
    passed = bool(data.get("is_live")) and score >= settings.liveness_threshold
    return passed, score
