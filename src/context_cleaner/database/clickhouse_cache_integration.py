"""
ClickHouse Cache Integration

Provides intelligent caching integration between ClickHouse queries and the multi-level cache system.
Optimized for 2.768B token dataset performance with intelligent cache key generation and TTL management.
"""

import logging
import hashlib
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta

from ..api.cache import MultiLevelCache, CacheService
from ..telemetry.clients.clickhouse_client import ClickHouseClient

logger = logging.getLogger(__name__)


class ClickHouseCacheIntegration:
    """
    High-performance cache integration for ClickHouse operations.

    Provides intelligent caching strategies for different query patterns
    with optimized TTL management and cache invalidation.
    """

    def __init__(self, clickhouse_client: ClickHouseClient, cache_service: CacheService):
        """Initialize cache integration with ClickHouse client and cache service."""
        self.clickhouse_client = clickhouse_client
        self.cache_service = cache_service

        # Inject cache service into ClickHouse client
        self.clickhouse_client.set_cache_service(cache_service)

        # Cache TTL strategies for different query types
        self.cache_strategies = {
            # Dashboard queries - frequent access, short TTL for real-time feel
            'dashboard_overview': 60,       # 1 minute
            'widget_data': 30,              # 30 seconds
            'health_metrics': 15,           # 15 seconds

            # Analytics queries - moderate frequency, longer TTL
            'cost_trends': 300,             # 5 minutes
            'usage_stats': 180,             # 3 minutes
            'model_statistics': 240,        # 4 minutes
            'token_analysis': 600,          # 10 minutes

            # Heavy aggregation queries - low frequency, long TTL
            'aggregated_metrics': 900,      # 15 minutes
            'historical_analysis': 1800,    # 30 minutes
            'bulk_statistics': 3600,        # 1 hour

            # System queries - very long TTL
            'schema_info': 7200,            # 2 hours
            'table_metadata': 3600,         # 1 hour
        }

        # Performance monitoring
        self.performance_stats = {
            'queries_cached': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'cache_invalidations': 0,
            'total_cache_time_saved_ms': 0
        }

        logger.info("ClickHouse cache integration initialized successfully")

    def generate_cache_key(self, query: str, params: Optional[Dict[str, Any]] = None,
                         query_type: str = 'general') -> str:
        """
        Generate intelligent cache key based on query, parameters, and type.

        Args:
            query: SQL query string
            params: Query parameters
            query_type: Type of query for TTL strategy selection

        Returns:
            Cache key string
        """
        # Normalize query for consistent caching
        normalized_query = ' '.join(query.strip().split())

        # Create hash components
        query_hash = hashlib.sha256(normalized_query.encode()).hexdigest()[:16]

        params_hash = ''
        if params:
            params_str = json.dumps(params, sort_keys=True, separators=(',', ':'))
            params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:8]

        # Generate cache key with namespace
        cache_key = f"clickhouse:{query_type}:{query_hash}"
        if params_hash:
            cache_key += f":{params_hash}"

        return cache_key

    async def execute_cached_query(self, query: str, params: Optional[Dict[str, Any]] = None,
                                 query_type: str = 'general',
                                 force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Execute query with intelligent caching.

        Args:
            query: SQL query to execute
            params: Query parameters
            query_type: Query type for cache strategy selection
            force_refresh: Force cache refresh

        Returns:
            Query results
        """
        # Generate cache key
        cache_key = self.generate_cache_key(query, params, query_type)

        # Get TTL for this query type
        cache_ttl = self.cache_strategies.get(query_type, 300)  # Default 5 minutes

        start_time = datetime.now()

        # Try cache first unless forcing refresh
        if not force_refresh:
            try:
                cached_result = await self.cache_service.get(cache_key)
                if cached_result is not None:
                    self.performance_stats['cache_hits'] += 1
                    cache_time_saved = (datetime.now() - start_time).total_seconds() * 1000
                    self.performance_stats['total_cache_time_saved_ms'] += cache_time_saved

                    logger.debug(f"Cache hit for {query_type}: {cache_key}")
                    return cached_result
                else:
                    self.performance_stats['cache_misses'] += 1
            except Exception as e:
                logger.warning(f"Cache retrieval error for {cache_key}: {e}")
                self.performance_stats['cache_misses'] += 1

        # Execute query with ClickHouse client
        try:
            results = await self.clickhouse_client.execute_dashboard_query(
                query, query_type, params
            )

            # Cache the results
            if results:  # Only cache non-empty results
                try:
                    await self.cache_service.set(cache_key, results, cache_ttl)
                    self.performance_stats['queries_cached'] += 1
                    logger.debug(f"Cached {query_type} query result: {cache_key}")
                except Exception as e:
                    logger.warning(f"Cache storage error for {cache_key}: {e}")

            return results

        except Exception as e:
            logger.error(f"Query execution failed for {query_type}: {e}")
            # Return empty list on error to maintain consistency
            return []

    async def invalidate_cache_pattern(self, pattern: str) -> bool:
        """
        Invalidate cache entries matching pattern.

        Args:
            pattern: Cache key pattern to invalidate

        Returns:
            True if successful
        """
        try:
            success = await self.cache_service.invalidate(f"clickhouse:{pattern}")
            if success:
                self.performance_stats['cache_invalidations'] += 1
                logger.info(f"Invalidated cache pattern: {pattern}")
            return success
        except Exception as e:
            logger.error(f"Cache invalidation failed for pattern {pattern}: {e}")
            return False

    async def invalidate_query_type(self, query_type: str) -> bool:
        """
        Invalidate all cached queries of a specific type.

        Args:
            query_type: Query type to invalidate

        Returns:
            True if successful
        """
        return await self.invalidate_cache_pattern(f"{query_type}:*")

    async def warm_dashboard_cache(self, dashboard_queries: Dict[str, str]) -> Dict[str, bool]:
        """
        Pre-warm cache with common dashboard queries.

        Args:
            dashboard_queries: Dictionary of query_type -> query mappings

        Returns:
            Dictionary of query_type -> success status
        """
        results = {}

        for query_type, query in dashboard_queries.items():
            try:
                await self.execute_cached_query(query, query_type=query_type, force_refresh=True)
                results[query_type] = True
                logger.debug(f"Cache warmed for {query_type}")
            except Exception as e:
                logger.error(f"Cache warming failed for {query_type}: {e}")
                results[query_type] = False

        logger.info(f"Cache warming completed: {sum(results.values())}/{len(results)} successful")
        return results

    async def get_cache_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache performance statistics."""
        try:
            # Get base cache stats
            cache_stats = await self.cache_service.get_stats()

            # Get ClickHouse client performance stats
            clickhouse_stats = await self.clickhouse_client.get_performance_stats()

            # Calculate cache efficiency metrics
            total_queries = self.performance_stats['cache_hits'] + self.performance_stats['cache_misses']
            cache_hit_rate = 0.0
            if total_queries > 0:
                cache_hit_rate = (self.performance_stats['cache_hits'] / total_queries) * 100

            return {
                'cache_integration': {
                    'queries_cached': self.performance_stats['queries_cached'],
                    'cache_hits': self.performance_stats['cache_hits'],
                    'cache_misses': self.performance_stats['cache_misses'],
                    'cache_hit_rate_percent': round(cache_hit_rate, 2),
                    'cache_invalidations': self.performance_stats['cache_invalidations'],
                    'total_cache_time_saved_ms': self.performance_stats['total_cache_time_saved_ms'],
                    'average_time_saved_per_hit_ms': round(
                        self.performance_stats['total_cache_time_saved_ms'] /
                        max(self.performance_stats['cache_hits'], 1), 2
                    )
                },
                'cache_service_stats': cache_stats,
                'clickhouse_stats': clickhouse_stats,
                'cache_strategies': self.cache_strategies
            }

        except Exception as e:
            logger.error(f"Error getting cache performance stats: {e}")
            return {'error': str(e)}

    def optimize_for_workload(self, workload_type: str = 'dashboard'):
        """
        Optimize cache strategies for specific workload patterns.

        Args:
            workload_type: Type of workload ('dashboard', 'analytics', 'bulk')
        """
        if workload_type == 'dashboard':
            # Optimize for real-time dashboard responsiveness
            self.cache_strategies.update({
                'dashboard_overview': 30,   # Even shorter for real-time feel
                'widget_data': 15,          # Very short for responsive widgets
                'health_metrics': 10,       # Almost real-time health data
            })

        elif workload_type == 'analytics':
            # Optimize for analytical workloads with longer TTLs
            self.cache_strategies.update({
                'token_analysis': 1200,     # 20 minutes
                'cost_trends': 600,         # 10 minutes
                'usage_stats': 900,         # 15 minutes
            })

        elif workload_type == 'bulk':
            # Optimize for bulk processing with very long TTLs
            self.cache_strategies.update({
                'bulk_statistics': 7200,    # 2 hours
                'historical_analysis': 3600, # 1 hour
                'aggregated_metrics': 1800, # 30 minutes
            })

        # Apply optimizations to ClickHouse client
        self.clickhouse_client.optimize_for_dashboard_queries()

        logger.info(f"Cache integration optimized for {workload_type} workload")

    async def clear_all_cache(self) -> bool:
        """Clear all ClickHouse-related cache entries."""
        try:
            success = await self.cache_service.invalidate("clickhouse:*")
            if success:
                # Reset performance stats
                self.performance_stats = {
                    'queries_cached': 0,
                    'cache_hits': 0,
                    'cache_misses': 0,
                    'cache_invalidations': 0,
                    'total_cache_time_saved_ms': 0
                }
                logger.info("All ClickHouse cache cleared")
            return success
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on cache integration."""
        try:
            # Test cache operations
            test_key = "clickhouse:health_check:test"
            test_data = {"timestamp": datetime.now().isoformat(), "status": "healthy"}

            # Test cache set
            set_success = await self.cache_service.set(test_key, test_data, 60)

            # Test cache get
            retrieved_data = await self.cache_service.get(test_key) if set_success else None
            get_success = retrieved_data is not None

            # Test cache invalidation
            invalidate_success = await self.cache_service.invalidate(test_key) if get_success else False

            # Test ClickHouse connectivity
            clickhouse_health = await self.clickhouse_client.comprehensive_health_check()

            return {
                'cache_integration_healthy': set_success and get_success and invalidate_success,
                'cache_operations': {
                    'set_success': set_success,
                    'get_success': get_success,
                    'invalidate_success': invalidate_success
                },
                'clickhouse_health': clickhouse_health,
                'performance_stats': self.performance_stats,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'cache_integration_healthy': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Factory function for easy integration setup
async def create_clickhouse_cache_integration(
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 9000,
    clickhouse_database: str = "otel",
    redis_url: str = "redis://localhost:6379",
    max_connections: int = 10,
    enable_query_caching: bool = True
) -> ClickHouseCacheIntegration:
    """
    Factory function to create a fully configured ClickHouse cache integration.

    Args:
        clickhouse_host: ClickHouse host
        clickhouse_port: ClickHouse port
        clickhouse_database: ClickHouse database name
        redis_url: Redis URL for caching
        max_connections: Maximum ClickHouse connections
        enable_query_caching: Enable query caching

    Returns:
        Configured ClickHouseCacheIntegration instance
    """
    try:
        # Create cache service
        cache_service = MultiLevelCache(redis_url=redis_url, max_memory_items=2000)

        # Create ClickHouse client with caching enabled
        clickhouse_client = ClickHouseClient(
            host=clickhouse_host,
            port=clickhouse_port,
            database=clickhouse_database,
            max_connections=max_connections,
            enable_query_caching=enable_query_caching
        )

        # Initialize ClickHouse client
        await clickhouse_client.initialize()

        # Create integration
        integration = ClickHouseCacheIntegration(clickhouse_client, cache_service)

        # Optimize for dashboard workload by default
        integration.optimize_for_workload('dashboard')

        logger.info("ClickHouse cache integration created successfully")
        return integration

    except Exception as e:
        logger.error(f"Failed to create ClickHouse cache integration: {e}")
        raise