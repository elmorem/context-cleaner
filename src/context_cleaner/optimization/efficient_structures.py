"""
Memory-Efficient Data Structures and Memory Pooling

Provides optimized data structures and memory management for handling
large token datasets (2.768B tokens) with minimal memory footprint.
"""

import array
import mmap
import struct
import weakref
import logging
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    Iterator,
    Generic,
    TypeVar,
    Protocol,
    runtime_checkable,
)
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading
import gc
import sys
import os

logger = logging.getLogger(__name__)

T = TypeVar("T")


@runtime_checkable
class Poolable(Protocol):
    """Protocol for objects that can be pooled"""

    def reset(self) -> None:
        """Reset object state for reuse"""
        ...


@dataclass
class MemoryPool:
    """Generic memory pool for object reuse"""

    object_factory: callable
    max_size: int = 1000
    _pool: deque = field(default_factory=deque)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    created_count: int = 0
    reused_count: int = 0

    def acquire(self) -> Any:
        """Acquire an object from the pool"""
        with self._lock:
            if self._pool:
                obj = self._pool.popleft()
                self.reused_count += 1
                if hasattr(obj, "reset"):
                    obj.reset()
                return obj
            else:
                self.created_count += 1
                return self.object_factory()

    def release(self, obj: Any) -> None:
        """Return an object to the pool"""
        if obj is None:
            return

        with self._lock:
            if len(self._pool) < self.max_size:
                # Clear sensitive data before pooling
                if hasattr(obj, "reset"):
                    obj.reset()
                self._pool.append(obj)

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        with self._lock:
            return {
                "pool_size": len(self._pool),
                "max_size": self.max_size,
                "created_count": self.created_count,
                "reused_count": self.reused_count,
                "reuse_rate": (
                    self.reused_count / max(self.created_count + self.reused_count, 1)
                )
                * 100,
            }


class CompactTokenStorage:
    """Memory-efficient storage for large token datasets"""

    def __init__(self, initial_capacity: int = 1000000):
        """Initialize with efficient array-based storage"""
        # Use array for better memory density than lists
        self.token_ids = array.array("I")  # Unsigned int (4 bytes each)
        self.token_ids.extend([0] * initial_capacity)

        # Metadata storage with memory mapping for large datasets
        self.metadata_file = None
        self.metadata_mmap = None
        self.token_count = 0
        self.capacity = initial_capacity

        # String interning for repeated tokens
        self.string_pool: Dict[str, str] = {}
        self.token_to_id: Dict[str, int] = {}
        self.id_to_token: Dict[int, str] = {}
        self.next_id = 1

        logger.info(f"CompactTokenStorage initialized with capacity {initial_capacity}")

    def intern_token(self, token: str) -> int:
        """Intern a token string and return its ID"""
        if token in self.token_to_id:
            return self.token_to_id[token]

        # Use sys.intern for automatic string interning
        interned_token = sys.intern(token)
        self.string_pool[token] = interned_token

        token_id = self.next_id
        self.token_to_id[interned_token] = token_id
        self.id_to_token[token_id] = interned_token
        self.next_id += 1

        return token_id

    def add_tokens(self, tokens: List[str]) -> None:
        """Add tokens efficiently using batch processing"""
        if self.token_count + len(tokens) > self.capacity:
            self._expand_capacity(self.token_count + len(tokens))

        # Batch process tokens for better performance
        for i, token in enumerate(tokens):
            token_id = self.intern_token(token)
            self.token_ids[self.token_count + i] = token_id

        self.token_count += len(tokens)

    def _expand_capacity(self, new_capacity: int) -> None:
        """Expand storage capacity"""
        old_capacity = self.capacity
        self.capacity = max(new_capacity, old_capacity * 2)

        # Extend array
        self.token_ids.extend([0] * (self.capacity - old_capacity))

        logger.info(f"Expanded token storage from {old_capacity} to {self.capacity}")

    def get_tokens(self, start: int, count: int) -> List[str]:
        """Get token strings by range"""
        if start + count > self.token_count:
            count = self.token_count - start

        result = []
        for i in range(start, start + count):
            token_id = self.token_ids[i]
            result.append(self.id_to_token.get(token_id, "<UNK>"))

        return result

    def get_memory_usage(self) -> Dict[str, int]:
        """Get detailed memory usage statistics"""
        return {
            "token_array_bytes": self.token_ids.buffer_info()[1]
            * self.token_ids.itemsize,
            "string_pool_count": len(self.string_pool),
            "unique_tokens": len(self.token_to_id),
            "total_tokens": self.token_count,
            "capacity": self.capacity,
            "utilization_percent": (self.token_count / self.capacity) * 100,
        }

    def create_memory_mapped_storage(self, filepath: str) -> None:
        """Create memory-mapped file for very large datasets"""
        try:
            # Calculate file size needed
            file_size = self.capacity * 4  # 4 bytes per token ID

            # Create file
            with open(filepath, "wb") as f:
                f.write(b"\x00" * file_size)

            # Open for memory mapping
            self.metadata_file = open(filepath, "r+b")
            self.metadata_mmap = mmap.mmap(
                self.metadata_file.fileno(), 0, access=mmap.ACCESS_WRITE
            )

            logger.info(f"Created memory-mapped storage: {filepath}")

        except Exception as e:
            logger.error(f"Failed to create memory-mapped storage: {e}")

    def __del__(self):
        """Cleanup memory-mapped resources"""
        if self.metadata_mmap:
            self.metadata_mmap.close()
        if self.metadata_file:
            self.metadata_file.close()


class ChunkedDataProcessor:
    """Process large datasets in memory-efficient chunks"""

    def __init__(self, chunk_size: int = 10000, max_memory_mb: int = 512):
        self.chunk_size = chunk_size
        self.max_memory_mb = max_memory_mb
        self.processing_stats = {
            "chunks_processed": 0,
            "total_items": 0,
            "memory_peaks": [],
            "processing_times": [],
        }

    def process_chunks(
        self,
        data_iterator: Iterator[T],
        processor_func: callable,
        chunk_callback: Optional[callable] = None,
    ) -> Iterator[List[Any]]:
        """Process data in memory-efficient chunks"""
        import psutil
        import time

        process = psutil.Process()
        chunk = []

        for item in data_iterator:
            chunk.append(item)

            if len(chunk) >= self.chunk_size:
                # Process chunk
                start_time = time.time()
                start_memory = process.memory_info().rss / 1024 / 1024

                try:
                    result = processor_func(chunk)

                    # Record statistics
                    end_time = time.time()
                    end_memory = process.memory_info().rss / 1024 / 1024

                    self.processing_stats["chunks_processed"] += 1
                    self.processing_stats["total_items"] += len(chunk)
                    self.processing_stats["memory_peaks"].append(end_memory)
                    self.processing_stats["processing_times"].append(
                        end_time - start_time
                    )

                    # Memory pressure check
                    if end_memory > self.max_memory_mb:
                        logger.warning(
                            f"Memory usage ({end_memory:.1f} MB) exceeds limit ({self.max_memory_mb} MB)"
                        )
                        gc.collect()  # Force garbage collection

                    if chunk_callback:
                        chunk_callback(self.processing_stats)

                    yield result

                finally:
                    # Clear chunk for memory efficiency
                    chunk.clear()

                    # Periodic garbage collection
                    if self.processing_stats["chunks_processed"] % 10 == 0:
                        gc.collect()

        # Process remaining items
        if chunk:
            result = processor_func(chunk)
            self.processing_stats["chunks_processed"] += 1
            self.processing_stats["total_items"] += len(chunk)
            yield result

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics"""
        stats = self.processing_stats.copy()

        if stats["memory_peaks"]:
            stats["memory_stats"] = {
                "peak_mb": max(stats["memory_peaks"]),
                "average_mb": sum(stats["memory_peaks"]) / len(stats["memory_peaks"]),
                "min_mb": min(stats["memory_peaks"]),
            }

        if stats["processing_times"]:
            stats["timing_stats"] = {
                "total_time": sum(stats["processing_times"]),
                "average_chunk_time": sum(stats["processing_times"])
                / len(stats["processing_times"]),
                "items_per_second": stats["total_items"]
                / max(sum(stats["processing_times"]), 0.001),
            }

        return stats


class LRUCacheWithMemoryLimit:
    """LRU Cache with memory usage tracking and limits"""

    def __init__(self, max_memory_mb: int = 100, max_items: int = 1000):
        self.max_memory_mb = max_memory_mb
        self.max_items = max_items
        self.cache: Dict[Any, Any] = {}
        self.access_order: deque = deque()
        self.memory_usage_mb = 0.0
        self._lock = threading.Lock()

    def get(self, key: Any) -> Optional[Any]:
        """Get item from cache"""
        with self._lock:
            if key in self.cache:
                # Move to end (most recent)
                self.access_order.remove(key)
                self.access_order.append(key)
                return self.cache[key]
            return None

    def put(self, key: Any, value: Any) -> None:
        """Put item in cache with memory management"""
        with self._lock:
            # Estimate memory usage
            item_size_mb = self._estimate_size(value) / 1024 / 1024

            # Remove existing key if present
            if key in self.cache:
                old_size = self._estimate_size(self.cache[key]) / 1024 / 1024
                self.memory_usage_mb -= old_size
                self.access_order.remove(key)

            # Check memory limit
            while (
                self.memory_usage_mb + item_size_mb > self.max_memory_mb
                or len(self.cache) >= self.max_items
            ):
                self._evict_lru()

            # Add new item
            self.cache[key] = value
            self.access_order.append(key)
            self.memory_usage_mb += item_size_mb

    def _evict_lru(self) -> None:
        """Evict least recently used item"""
        if not self.access_order:
            return

        lru_key = self.access_order.popleft()
        if lru_key in self.cache:
            evicted_value = self.cache.pop(lru_key)
            evicted_size_mb = self._estimate_size(evicted_value) / 1024 / 1024
            self.memory_usage_mb -= evicted_size_mb

    def _estimate_size(self, obj: Any) -> int:
        """Estimate object size in bytes"""
        try:
            return sys.getsizeof(obj)
        except:
            return 1024  # Default estimate

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                "items": len(self.cache),
                "max_items": self.max_items,
                "memory_usage_mb": self.memory_usage_mb,
                "max_memory_mb": self.max_memory_mb,
                "utilization_percent": (len(self.cache) / self.max_items) * 100,
                "memory_utilization_percent": (
                    self.memory_usage_mb / self.max_memory_mb
                )
                * 100,
            }


class EfficientBitSet:
    """Memory-efficient bit set for large boolean arrays"""

    def __init__(self, size: int):
        self.size = size
        # Use bytearray for efficiency
        self.bits = bytearray((size + 7) // 8)  # Round up to nearest byte

    def set(self, index: int) -> None:
        """Set bit at index"""
        if 0 <= index < self.size:
            byte_index = index // 8
            bit_index = index % 8
            self.bits[byte_index] |= 1 << bit_index

    def clear(self, index: int) -> None:
        """Clear bit at index"""
        if 0 <= index < self.size:
            byte_index = index // 8
            bit_index = index % 8
            self.bits[byte_index] &= ~(1 << bit_index)

    def get(self, index: int) -> bool:
        """Get bit at index"""
        if 0 <= index < self.size:
            byte_index = index // 8
            bit_index = index % 8
            return bool(self.bits[byte_index] & (1 << bit_index))
        return False

    def count_set_bits(self) -> int:
        """Count number of set bits"""
        return sum(bin(byte).count("1") for byte in self.bits)

    def get_memory_usage(self) -> Dict[str, int]:
        """Get memory usage statistics"""
        return {
            "size_bits": self.size,
            "size_bytes": len(self.bits),
            "memory_efficiency_ratio": self.size / (len(self.bits) * 8),
            "set_bits": self.count_set_bits(),
        }


class MemoryEfficientObjectManager:
    """Manage object lifecycle for memory efficiency"""

    def __init__(self):
        self.pools: Dict[str, MemoryPool] = {}
        self.weak_refs: weakref.WeakSet = weakref.WeakSet()
        self.creation_stats: Dict[str, int] = defaultdict(int)

    def register_pool(self, name: str, factory: callable, max_size: int = 1000) -> None:
        """Register a new object pool"""
        self.pools[name] = MemoryPool(factory, max_size)
        logger.info(f"Registered memory pool: {name} (max_size: {max_size})")

    def acquire_object(self, pool_name: str) -> Any:
        """Acquire object from pool"""
        if pool_name not in self.pools:
            raise ValueError(f"Pool {pool_name} not registered")

        obj = self.pools[pool_name].acquire()
        self.weak_refs.add(obj)
        self.creation_stats[pool_name] += 1
        return obj

    def release_object(self, pool_name: str, obj: Any) -> None:
        """Release object back to pool"""
        if pool_name in self.pools:
            self.pools[pool_name].release(obj)

    def force_cleanup(self) -> Dict[str, Any]:
        """Force cleanup and garbage collection"""
        before_count = len(self.weak_refs)
        gc.collect()

        # Clear any dead weak references
        dead_refs = [ref for ref in self.weak_refs if ref() is None]
        for ref in dead_refs:
            self.weak_refs.discard(ref)

        after_count = len(self.weak_refs)

        return {
            "objects_before_cleanup": before_count,
            "objects_after_cleanup": after_count,
            "objects_cleaned": before_count - after_count,
            "pool_stats": {name: pool.get_stats() for name, pool in self.pools.items()},
        }

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory management statistics"""
        return {
            "pools": {name: pool.get_stats() for name, pool in self.pools.items()},
            "active_objects": len(self.weak_refs),
            "creation_stats": dict(self.creation_stats),
            "total_pools": len(self.pools),
        }


# Global instances
object_manager = MemoryEfficientObjectManager()

# Register common object pools
object_manager.register_pool("dict", dict, 500)
object_manager.register_pool("list", list, 500)
object_manager.register_pool("set", set, 200)


def create_efficient_token_storage(
    initial_capacity: int = 1000000,
) -> CompactTokenStorage:
    """Factory function for creating efficient token storage"""
    return CompactTokenStorage(initial_capacity)


def create_chunked_processor(
    chunk_size: int = 10000, max_memory_mb: int = 512
) -> ChunkedDataProcessor:
    """Factory function for creating chunked data processor"""
    return ChunkedDataProcessor(chunk_size, max_memory_mb)


def create_memory_limited_cache(
    max_memory_mb: int = 100, max_items: int = 1000
) -> LRUCacheWithMemoryLimit:
    """Factory function for creating memory-limited cache"""
    return LRUCacheWithMemoryLimit(max_memory_mb, max_items)


async def efficient_structures_health_check() -> Dict[str, Any]:
    """Health check for efficient structures system"""
    try:
        # Test basic functionality
        token_storage = create_efficient_token_storage(1000)
        token_storage.add_tokens(["test", "token", "storage"])

        processor = create_chunked_processor(100, 50)
        test_data = list(range(250))

        chunks_processed = 0
        for chunk_result in processor.process_chunks(
            iter(test_data), lambda chunk: len(chunk)
        ):
            chunks_processed += 1

        cache = create_memory_limited_cache(10, 100)
        cache.put("test_key", "test_value")

        return {
            "efficient_structures_healthy": True,
            "token_storage_working": token_storage.token_count == 3,
            "chunked_processor_working": chunks_processed > 0,
            "memory_cache_working": cache.get("test_key") == "test_value",
            "object_manager_stats": object_manager.get_comprehensive_stats(),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Efficient structures health check failed: {e}")
        return {
            "efficient_structures_healthy": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
