import redis
from app.core.config import REDIS_URL


def get_redis_client():
    return redis.from_url(REDIS_URL)
