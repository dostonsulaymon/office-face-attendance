"""Async client for CompreFace's recognition service (via the FE gateway).

Only the recognition REST API is used (x-api-key auth) — never the admin OAuth
flow, which is buggy headlessly (see docs/BUILD_PLAN.md).
"""
import httpx

from app.core.config import get_settings

settings = get_settings()


class CompreFaceError(RuntimeError):
    pass


def _base() -> str:
    return settings.compreface_url.rstrip("/") + "/api/v1/recognition"


def _headers() -> dict:
    if not settings.compreface_recognition_api_key:
        raise CompreFaceError("COMPREFACE_RECOGNITION_API_KEY is not configured")
    return {"x-api-key": settings.compreface_recognition_api_key}


async def add_face(subject: str, image: bytes, filename: str = "face.jpg") -> dict:
    """Enroll one example face under a subject; returns {image_id, subject}."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_base()}/faces",
            params={"subject": subject},
            headers=_headers(),
            files={"file": (filename, image, "image/jpeg")},
        )
    if resp.status_code >= 400:
        raise CompreFaceError(f"add_face failed ({resp.status_code}): {resp.text}")
    return resp.json()


async def recognize(image: bytes, limit: int = 1, prediction_count: int = 1) -> dict:
    """Run recognition on an image; returns CompreFace's raw result payload."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_base()}/recognize",
            params={"limit": limit, "prediction_count": prediction_count},
            headers=_headers(),
            files={"file": ("frame.jpg", image, "image/jpeg")},
        )
    if resp.status_code >= 400:
        raise CompreFaceError(f"recognize failed ({resp.status_code}): {resp.text}")
    return resp.json()


async def best_match(image: bytes) -> tuple[str | None, float]:
    """Return (subject, similarity) of the top match for the largest face, or (None, 0)."""
    data = await recognize(image, limit=1, prediction_count=1)
    results = data.get("result") or []
    if not results:
        return None, 0.0
    subjects = results[0].get("subjects") or []
    if not subjects:
        return None, 0.0
    top = subjects[0]
    return top.get("subject"), float(top.get("similarity", 0.0))


async def delete_subject(subject: str) -> None:
    """Purge a subject and all its enrolled faces (right-to-erasure)."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(f"{_base()}/subjects/{subject}", headers=_headers())
    if resp.status_code >= 400 and resp.status_code != 404:
        raise CompreFaceError(f"delete_subject failed ({resp.status_code}): {resp.text}")
