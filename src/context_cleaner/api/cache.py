"""
Caching Service Implementation

Provides multi-level caching with Redis and in-memory fallback,
optimized for dashboard and telemetry data patterns.
"""

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict
import json
import logging
import asyncio
from datetime import datetime, timedelta
import weakref

logger = logging.getLogger(__name__)


class CacheService(ABC):
    """Abstract cache service interface"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL"""
        pass

    @abstractmethod
    async def invalidate(self, pattern: str) -> bool:
        """Invalidate cache entries matching pattern"""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Clear all cache entries"""
        pass


class MultiLevelCache(CacheService):
    """Multi-level cache implementation with memory and Redis layers"""

    def __init__(
        self, redis_url: str = "redis://localhost:6379", max_memory_items: int = 1000
    ):
        self.max_memory_items = max_memory_items
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.redis_client = None
        self.redis_url = redis_url
        self._init_lock = asyncio.Lock()
        self._redis_available = False

        # LRU tracking for memory cache
        self._access_order = []
        self._cleanup_task = None

    async def _ensure_redis_connection(self):
        """Ensure Redis connection is established"""
        if self.redis_client is None:
            async with self._init_lock:
                if self.redis_client is None:
                    try:
                        import redis.asyncio as redis

                        self.redis_client = redis.from_url(
                            self.redis_url,
                            decode_responses=True,
                            retry_on_timeout=True,
                            socket_connect_timeout=5,
                            socket_timeout=5,
                        )
                        # Test connection
                        await self.redis_client.ping()
                        self._redis_available = True
                        logger.info("Redis connection established successfully")
                    except Exception as e:
                        logger.warning(
                            f"Redis not available, using memory-only cache: {e}"
                        )
                        self.redis_client = None
                        self._redis_available = False

    async def get(self, key: str) -> Optional[Any]:
        """Get value from multi-level cache"""
        try:
            # Level 1: Memory cache
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                if not self._is_expired(entry):
                    self._update_access_order(key)
                    logger.debug(f"Cache hit (memory): {key}")
                    return entry["value"]
                else:
                    # Remove expired entry
                    del self.memory_cache[key]
                    if key in self._access_order:
                        self._access_order.remove(key)

            # Level 2: Redis cache
            await self._ensure_redis_connection()
            if self._redis_available and self.redis_client:
                try:
                    cached_data = await self.redis_client.get(key)
                    if cached_data:
                        data = json.loads(cached_data)
                        # Populate L1 cache
                        await self._set_memory_cache(
                            key, data, 300
                        )  # Default TTL for L1
                        logger.debug(f"Cache hit (redis): {key}")
                        return data
                except Exception as e:
                    logger.warning(f"Redis get error for {key}: {e}")

            logger.debug(f"Cache miss: {key}")
            return None

        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in multi-level cache"""
        try:
            success = True

            # Set in memory cache
            await self._set_memory_cache(key, value, ttl)

            # Set in Redis cache
            await self._ensure_redis_connection()
            if self._redis_available and self.redis_client:
                try:
                    serialized = json.dumps(value, default=self._json_serializer)
                    await self.redis_client.setex(key, ttl, serialized)
                    logger.debug(f"Cache set (redis): {key}")
                except Exception as e:
                    logger.warning(f"Redis set error for {key}: {e}")
                    success = False

            logger.debug(f"Cache set (memory): {key}")
            return success

        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False

    async def invalidate(self, pattern: str) -> bool:
        """Invalidate cache entries matching pattern"""
        try:
            invalidated_count = 0

            # Invalidate memory cache
            keys_to_remove = []
            for key in self.memory_cache:
                if self._matches_pattern(key, pattern):
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.memory_cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                invalidated_count += 1

            # Invalidate Redis cache
            await self._ensure_redis_connection()
            if self._redis_available and self.redis_client:
                try:
                    # Redis pattern matching
                    keys = await self.redis_client.keys(pattern)
                    if keys:
                        await self.redis_client.delete(*keys)
                        invalidated_count += len(keys)
                except Exception as e:
                    logger.warning(
                        f"Redis invalidation error for pattern {pattern}: {e}"
                    )

            logger.info(
                f"Cache invalidated {invalidated_count} keys for pattern: {pattern}"
            )
            return True

        except Exception as e:
            logger.error(f"Cache invalidation error for pattern {pattern}: {e}")
            return False

    async def clear(self) -> bool:
        """Clear all cache entries"""
        try:
            # Clear memory cache
            self.memory_cache.clear()
            self._access_order.clear()

            # Clear Redis cache (optional, be careful in production!)
            await self._ensure_redis_connection()
            if self._redis_available and self.redis_client:
                try:
                    await self.redis_client.flushdb()
                except Exception as e:
                    logger.warning(f"Redis clear error: {e}")

            logger.info("Cache cleared completely")
            return True

        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            memory_size = len(self.memory_cache)
            redis_info = {}

            if self._redis_available and self.redis_client:
                try:
                    redis_info = await self.redis_client.info("memory")
                except Exception as e:
                    logger.warning(f"Could not get Redis stats: {e}")

            return {
                "memory_cache_size": memory_size,
                "redis_available": self._redis_available,
                "redis_info": redis_info,
                "max_memory_items": self.max_memory_items,
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    # Private helper methods
    async def _set_memory_cache(self, key: str, value: Any, ttl: int):
        """Set value in memory cache with LRU eviction"""
        # Ensure we don't exceed max items
        if len(self.memory_cache) >= self.max_memory_items:
            await self._evict_lru_items()

        self.memory_cache[key] = {
            "value": value,
            "expires_at": datetime.now() + timedelta(seconds=ttl),
        }
        self._update_access_order(key)

    async def _evict_lru_items(self):
        """Evict least recently used items"""
        # Remove 10% of items to avoid frequent evictions
        items_to_remove = max(1, len(self.memory_cache) // 10)

        for _ in range(items_to_remove):
            if self._access_order:
                lru_key = self._access_order.pop(0)
                if lru_key in self.memory_cache:
                    del self.memory_cache[lru_key]

    def _update_access_order(self, key: str):
        """Update LRU access order"""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """Check if cache entry is expired"""
        return datetime.now() > entry["expires_at"]

    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Simple pattern matching for cache invalidation"""
        if pattern.endswith("*"):
            return key.startswith(pattern[:-1])
        elif pattern.startswith("*"):
            return key.endswith(pattern[1:])
        elif "*" in pattern:
            parts = pattern.split("*")
            return key.startswith(parts[0]) and key.endswith(parts[-1])
        else:
            return key == pattern

    def _json_serializer(self, obj):
        """Custom JSON serializer for cache values"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, "dict"):  # Pydantic models
            return obj.dict()
        elif hasattr(obj, "__dict__"):  # Other objects
            return obj.__dict__
        else:
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class InMemoryCache(CacheService):
    """Simple in-memory cache for development/testing"""

    def __init__(self, max_items: int = 1000):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_items = max_items
        self._access_order = []

    async def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            entry = self.cache[key]
            if not self._is_expired(entry):
                self._update_access_order(key)
                return entry["value"]
            else:
                del self.cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        try:
            # Evict if needed
            if len(self.cache) >= self.max_items:
                self._evict_lru()

            self.cache[key] = {
                "value": value,
                "expires_at": datetime.now() + timedelta(seconds=ttl),
            }
            self._update_access_order(key)
            return True
        except Exception as e:
            logger.error(f"In-memory cache set error: {e}")
            return False

    async def invalidate(self, pattern: str) -> bool:
        try:
            keys_to_remove = [
                key for key in self.cache.keys() if self._matches_pattern(key, pattern)
            ]

            for key in keys_to_remove:
                del self.cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)

            return True
        except Exception as e:
            logger.error(f"In-memory cache invalidate error: {e}")
            return False

    async def clear(self) -> bool:
        self.cache.clear()
        self._access_order.clear()
        return True

    def _evict_lru(self):
        """Evict least recently used item"""
        if self._access_order:
            lru_key = self._access_order.pop(0)
            if lru_key in self.cache:
                del self.cache[lru_key]

    def _update_access_order(self, key: str):
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        return datetime.now() > entry["expires_at"]

    def _matches_pattern(self, key: str, pattern: str) -> bool:
        if pattern.endswith("*"):
            return key.startswith(pattern[:-1])
        elif pattern.startswith("*"):
            return key.endswith(pattern[1:])
        elif "*" in pattern:
            parts = pattern.split("*")
            return key.startswith(parts[0]) and key.endswith(parts[-1])
        else:
            return key == pattern
