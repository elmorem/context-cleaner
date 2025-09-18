"""
High-Performance Streaming Processor for Large Token Datasets

Optimized for processing 2.768B tokens with minimal memory footprint
using advanced streaming, chunking, and garbage collection strategies.
"""

import gc
import asyncio
import logging
import weakref
import threading
from typing import (
    AsyncIterator, Iterator, List, Dict, Any, Optional, Callable, Union,
    TypeVar, Generic, Protocol, runtime_checkable
)
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing as mp
import time
import psutil

from .memory_profiler import memory_profiler, memory_profile
from .efficient_structures import CompactTokenStorage, object_manager

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


@dataclass
class StreamingConfig:
    """Configuration for streaming processor"""
    chunk_size: int = 10000
    max_memory_mb: int = 512
    gc_threshold: int = 100  # Chunks before GC
    max_workers: int = 4
    enable_memory_monitoring: bool = True
    compression_enabled: bool = True
    prefetch_chunks: int = 2


@dataclass
class ProcessingStats:
    """Statistics for streaming processing"""
    total_items: int = 0
    chunks_processed: int = 0
    processing_time_seconds: float = 0.0
    memory_peak_mb: float = 0.0
    memory_average_mb: float = 0.0
    gc_collections: int = 0
    items_per_second: float = 0.0
    memory_efficiency_ratio: float = 0.0
    errors: List[str] = field(default_factory=list)


@runtime_checkable
class StreamProcessor(Protocol):
    """Protocol for stream processors"""
    async def process_chunk(self, chunk: List[T]) -> R:
        """Process a chunk of data"""
        ...


class TokenStreamProcessor:
    """High-performance token stream processor"""

    def __init__(self, config: StreamingConfig = None):
        self.config = config or StreamingConfig()
        self.stats = ProcessingStats()
        self.token_storage = CompactTokenStorage(self.config.chunk_size * 10)

        # Memory management
        self._memory_snapshots = deque(maxlen=100)
        self._gc_counter = 0
        self._process = psutil.Process()

        # Threading
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        self._processing_lock = asyncio.Lock()

        logger.info(f"TokenStreamProcessor initialized with chunk_size={self.config.chunk_size}")

    async def stream_tokens(self,
                           token_iterator: AsyncIterator[str],
                           processor: StreamProcessor,
                           progress_callback: Optional[Callable] = None) -> AsyncIterator[Any]:
        """Stream process tokens with memory optimization"""

        start_time = time.time()
        chunk_buffer = []

        if self.config.enable_memory_monitoring:
            memory_profiler.start_monitoring()

        try:
            async for token in token_iterator:
                chunk_buffer.append(token)

                if len(chunk_buffer) >= self.config.chunk_size:
                    # Process chunk
                    async with self._processing_lock:
                        result = await self._process_chunk_with_monitoring(
                            chunk_buffer, processor
                        )

                        if result is not None:
                            yield result

                        # Update progress
                        if progress_callback:
                            progress_callback(self.stats)

                        # Clear buffer for memory efficiency
                        chunk_buffer.clear()

                        # Periodic garbage collection
                        await self._maybe_collect_garbage()

            # Process remaining tokens
            if chunk_buffer:
                async with self._processing_lock:
                    result = await self._process_chunk_with_monitoring(
                        chunk_buffer, processor
                    )
                    if result is not None:
                        yield result

        finally:
            self.stats.processing_time_seconds = time.time() - start_time
            self.stats.items_per_second = (
                self.stats.total_items / max(self.stats.processing_time_seconds, 0.001)
            )

            if self.config.enable_memory_monitoring:
                memory_profiler.stop_monitoring()

            logger.info(f"Stream processing complete: {self.stats.total_items} tokens "
                       f"in {self.stats.processing_time_seconds:.2f}s "
                       f"({self.stats.items_per_second:.0f} tokens/sec)")

    async def _process_chunk_with_monitoring(self,
                                           chunk: List[str],
                                           processor: StreamProcessor) -> Any:
        """Process chunk with memory and performance monitoring"""

        start_memory = self._process.memory_info().rss / 1024 / 1024
        start_time = time.time()

        try:
            # Store tokens efficiently
            self.token_storage.add_tokens(chunk)

            # Process chunk
            result = await processor.process_chunk(chunk)

            # Update statistics
            self.stats.total_items += len(chunk)
            self.stats.chunks_processed += 1

            # Memory tracking
            current_memory = self._process.memory_info().rss / 1024 / 1024
            self.stats.memory_peak_mb = max(self.stats.memory_peak_mb, current_memory)

            self._memory_snapshots.append({
                'timestamp': datetime.now(),
                'memory_mb': current_memory,
                'items_processed': self.stats.total_items
            })

            # Calculate memory efficiency
            if self.stats.chunks_processed > 0:
                avg_memory = sum(s['memory_mb'] for s in self._memory_snapshots) / len(self._memory_snapshots)
                self.stats.memory_average_mb = avg_memory
                self.stats.memory_efficiency_ratio = self.stats.total_items / max(avg_memory, 1)

            processing_time = time.time() - start_time

            # Log significant memory changes
            memory_delta = current_memory - start_memory
            if abs(memory_delta) > 10:  # More than 10MB change
                logger.debug(f"Chunk processing memory change: {memory_delta:+.1f} MB "
                           f"(current: {current_memory:.1f} MB)")

            return result

        except Exception as e:
            self.stats.errors.append(f"Chunk processing error: {str(e)}")
            logger.error(f"Error processing chunk: {e}")
            return None

    async def _maybe_collect_garbage(self) -> None:
        """Perform garbage collection if needed"""
        self._gc_counter += 1

        if self._gc_counter >= self.config.gc_threshold:
            # Check memory pressure
            current_memory = self._process.memory_info().rss / 1024 / 1024

            if current_memory > self.config.max_memory_mb * 0.8:  # 80% threshold
                logger.debug(f"Memory pressure detected ({current_memory:.1f} MB), "
                           "forcing garbage collection")

                before_memory = current_memory

                # Force garbage collection
                collected = gc.collect()

                after_memory = self._process.memory_info().rss / 1024 / 1024
                memory_freed = before_memory - after_memory

                self.stats.gc_collections += 1

                logger.debug(f"GC freed {memory_freed:.1f} MB, collected {collected} objects")

                # Also clean up object pools
                object_manager.force_cleanup()

            self._gc_counter = 0

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        return {
            'processing_stats': {
                'total_items': self.stats.total_items,
                'chunks_processed': self.stats.chunks_processed,
                'processing_time_seconds': self.stats.processing_time_seconds,
                'items_per_second': self.stats.items_per_second,
                'errors': len(self.stats.errors)
            },
            'memory_stats': {
                'peak_memory_mb': self.stats.memory_peak_mb,
                'average_memory_mb': self.stats.memory_average_mb,
                'memory_efficiency_ratio': self.stats.memory_efficiency_ratio,
                'gc_collections': self.stats.gc_collections
            },
            'token_storage_stats': self.token_storage.get_memory_usage(),
            'config': {
                'chunk_size': self.config.chunk_size,
                'max_memory_mb': self.config.max_memory_mb,
                'max_workers': self.config.max_workers
            }
        }


class ContextAnalysisProcessor:
    """Specialized processor for context analysis with memory optimization"""

    def __init__(self, analysis_config: Dict[str, Any] = None):
        self.analysis_config = analysis_config or {}
        self.context_cache = {}
        self.analysis_stats = {
            'contexts_analyzed': 0,
            'tokens_processed': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }

    @memory_profile("context_analysis")
    async def process_chunk(self, chunk: List[str]) -> Dict[str, Any]:
        """Process chunk for context analysis"""

        # Efficient context analysis using token patterns
        context_data = {
            'token_count': len(chunk),
            'unique_tokens': len(set(chunk)),
            'repetition_ratio': self._calculate_repetition_ratio(chunk),
            'context_patterns': self._analyze_patterns(chunk),
            'complexity_score': self._calculate_complexity(chunk)
        }

        self.analysis_stats['contexts_analyzed'] += 1
        self.analysis_stats['tokens_processed'] += len(chunk)

        return context_data

    def _calculate_repetition_ratio(self, tokens: List[str]) -> float:
        """Calculate token repetition ratio efficiently"""
        if not tokens:
            return 0.0

        unique_count = len(set(tokens))
        return 1.0 - (unique_count / len(tokens))

    def _analyze_patterns(self, tokens: List[str]) -> Dict[str, int]:
        """Analyze token patterns with memory efficiency"""
        patterns = {}

        # Use a sliding window approach to avoid creating all n-grams at once
        window_size = min(3, len(tokens))

        for i in range(len(tokens) - window_size + 1):
            pattern = ' '.join(tokens[i:i + window_size])
            patterns[pattern] = patterns.get(pattern, 0) + 1

            # Limit pattern storage to prevent memory explosion
            if len(patterns) > 1000:
                # Keep only the most frequent patterns
                patterns = dict(sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:500])

        return patterns

    def _calculate_complexity(self, tokens: List[str]) -> float:
        """Calculate context complexity score"""
        if not tokens:
            return 0.0

        # Simple complexity metric based on vocabulary diversity
        unique_tokens = len(set(tokens))
        total_tokens = len(tokens)

        vocabulary_diversity = unique_tokens / total_tokens
        average_token_length = sum(len(token) for token in tokens) / total_tokens

        # Normalize complexity score
        complexity = (vocabulary_diversity + average_token_length / 20) / 2
        return min(complexity, 1.0)

    def get_analysis_stats(self) -> Dict[str, Any]:
        """Get analysis statistics"""
        total_requests = self.analysis_stats['cache_hits'] + self.analysis_stats['cache_misses']
        cache_hit_rate = 0.0

        if total_requests > 0:
            cache_hit_rate = (self.analysis_stats['cache_hits'] / total_requests) * 100

        return {
            **self.analysis_stats,
            'cache_hit_rate_percent': cache_hit_rate,
            'average_tokens_per_context': (
                self.analysis_stats['tokens_processed'] /
                max(self.analysis_stats['contexts_analyzed'], 1)
            )
        }


class ParallelStreamProcessor:
    """Parallel stream processor for maximum throughput"""

    def __init__(self, num_workers: int = None):
        self.num_workers = num_workers or min(mp.cpu_count(), 8)
        self.executor = ProcessPoolExecutor(max_workers=self.num_workers)
        self.processing_queue = asyncio.Queue(maxsize=self.num_workers * 2)

        logger.info(f"ParallelStreamProcessor initialized with {self.num_workers} workers")

    async def process_stream_parallel(self,
                                    data_stream: AsyncIterator[List[T]],
                                    processor_func: Callable,
                                    chunk_size: int = 1000) -> AsyncIterator[Any]:
        """Process stream using parallel workers"""

        async def producer():
            """Produce chunks for processing queue"""
            async for chunk in data_stream:
                await self.processing_queue.put(chunk)

            # Signal completion
            for _ in range(self.num_workers):
                await self.processing_queue.put(None)

        async def consumer():
            """Consume and process chunks"""
            loop = asyncio.get_event_loop()

            while True:
                chunk = await self.processing_queue.get()
                if chunk is None:
                    break

                try:
                    # Process chunk in thread pool
                    result = await loop.run_in_executor(
                        self.executor, processor_func, chunk
                    )
                    yield result

                except Exception as e:
                    logger.error(f"Parallel processing error: {e}")

                finally:
                    self.processing_queue.task_done()

        # Start producer task
        producer_task = asyncio.create_task(producer())

        try:
            # Yield results from consumer
            async for result in consumer():
                yield result
        finally:
            # Cleanup
            await producer_task
            self.executor.shutdown(wait=True)


class GarbageCollectionOptimizer:
    """Optimize garbage collection patterns for large dataset processing"""

    def __init__(self):
        self.original_thresholds = gc.get_threshold()
        self.collection_stats = {
            'manual_collections': 0,
            'automatic_collections': 0,
            'objects_collected': 0,
            'memory_freed_mb': 0.0
        }

        # Optimize GC thresholds for large dataset processing
        self._optimize_gc_thresholds()

    def _optimize_gc_thresholds(self) -> None:
        """Optimize garbage collection thresholds"""
        # Increase thresholds to reduce GC frequency during heavy processing
        new_thresholds = (
            self.original_thresholds[0] * 2,  # Generation 0: 700 -> 1400
            self.original_thresholds[1] * 2,  # Generation 1: 10 -> 20
            self.original_thresholds[2] * 2   # Generation 2: 10 -> 20
        )

        gc.set_threshold(*new_thresholds)
        logger.info(f"GC thresholds optimized: {self.original_thresholds} -> {new_thresholds}")

    def force_efficient_collection(self) -> Dict[str, Any]:
        """Perform efficient garbage collection"""
        import psutil

        process = psutil.Process()
        before_memory = process.memory_info().rss / 1024 / 1024

        # Collect in reverse order (generation 2 -> 0) for efficiency
        collected_objects = []
        for generation in reversed(range(3)):
            collected = gc.collect(generation)
            collected_objects.append(collected)

        after_memory = process.memory_info().rss / 1024 / 1024
        memory_freed = before_memory - after_memory

        self.collection_stats['manual_collections'] += 1
        self.collection_stats['objects_collected'] += sum(collected_objects)
        self.collection_stats['memory_freed_mb'] += memory_freed

        return {
            'objects_collected': collected_objects,
            'memory_freed_mb': memory_freed,
            'gc_time_ms': 0,  # Would need timing for exact measurement
            'efficiency_ratio': sum(collected_objects) / max(memory_freed, 0.1)
        }

    def restore_original_thresholds(self) -> None:
        """Restore original GC thresholds"""
        gc.set_threshold(*self.original_thresholds)
        logger.info(f"GC thresholds restored to: {self.original_thresholds}")

    def get_gc_stats(self) -> Dict[str, Any]:
        """Get comprehensive GC statistics"""
        return {
            'collection_stats': self.collection_stats,
            'current_thresholds': gc.get_threshold(),
            'original_thresholds': self.original_thresholds,
            'gc_counts': gc.get_count(),
            'gc_stats': gc.get_stats() if hasattr(gc, 'get_stats') else None
        }


# Global GC optimizer
gc_optimizer = GarbageCollectionOptimizer()


async def create_token_stream_processor(config: StreamingConfig = None) -> TokenStreamProcessor:
    """Factory function for creating token stream processor"""
    return TokenStreamProcessor(config)


async def create_context_analyzer() -> ContextAnalysisProcessor:
    """Factory function for creating context analyzer"""
    return ContextAnalysisProcessor()


async def streaming_health_check() -> Dict[str, Any]:
    """Health check for streaming processing system"""
    try:
        # Test streaming processor
        config = StreamingConfig(chunk_size=100, max_memory_mb=50)
        processor = TokenStreamProcessor(config)

        # Test context analyzer
        analyzer = ContextAnalysisProcessor()

        # Test with sample data
        test_tokens = ['test', 'token', 'stream', 'processing'] * 25  # 100 tokens

        async def token_generator():
            for token in test_tokens:
                yield token

        results = []
        async for result in processor.stream_tokens(token_generator(), analyzer):
            results.append(result)

        performance_summary = processor.get_performance_summary()
        analysis_stats = analyzer.get_analysis_stats()
        gc_stats = gc_optimizer.get_gc_stats()

        return {
            'streaming_system_healthy': len(results) > 0,
            'tokens_processed': performance_summary['processing_stats']['total_items'],
            'memory_efficiency': performance_summary['memory_stats']['memory_efficiency_ratio'],
            'processing_speed': performance_summary['processing_stats']['items_per_second'],
            'analysis_working': analysis_stats['contexts_analyzed'] > 0,
            'gc_optimization_active': gc_stats['current_thresholds'] != gc_stats['original_thresholds'],
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Streaming health check failed: {e}")
        return {
            'streaming_system_healthy': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }