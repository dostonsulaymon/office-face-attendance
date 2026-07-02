import time

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()
redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)


async def in_cooldown(device_id: str, employee_id: int, seconds: int) -> bool:
    """True if this (device, employee) pair fired within the cooldown window.

    Uses SET NX EX atomically: if the key was freshly set we're NOT in cooldown;
    if it already existed we ARE (and should skip processing).
    """
    key = f"cooldown:{device_id}:{employee_id}"
    was_set = await redis_client.set(key, "1", nx=True, ex=seconds)
    return not bool(was_set)


async def rate_limited(device_id: str, limit: int = 60, window: int = 60) -> bool:
    """Fixed-window per-device rate limit. True if the device exceeded `limit`."""
    key = f"rl:{device_id}:{int(time.time() // window)}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, window)
    return count > limit
