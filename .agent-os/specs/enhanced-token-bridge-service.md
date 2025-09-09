# Enhanced Token Bridge Service Specification

**Version**: 1.0  
**Status**: DRAFT  
**Priority**: CRITICAL  
**Created**: 2025-09-09  

## Executive Summary

The Enhanced Token Bridge Service (`EnhancedTokenDatabaseBridge`) is a critical system component that bridges the gap between the Enhanced Token Analysis system (JSONL file-based) and the ClickHouse telemetry database. This service resolves the data loss issue where 2.768 billion tokens detected by enhanced analysis are not reaching the database for dashboard consumption.

## Problem Statement

### Current State
- **Enhanced Token Analysis**: Successfully processes 88 JSONL files, accurately counting 2,768,012,012 tokens
- **ClickHouse Database**: Contains telemetry data but lacks historical token summaries from JSONL analysis
- **Data Gap**: No mechanism exists to transfer enhanced analysis results into persistent storage
- **Dashboard Impact**: Dashboard shows incomplete data, cannot display accurate 2.7B token counts

### Architecture Gap
```
JSONL Files (2.7B tokens)
    ↓ [Enhanced Token Analysis - WORKING]
Enhanced Analysis Results
    ↓ [MISSING DATA BRIDGE - BROKEN]
ClickHouse Database
    ↓ [Database Queries - WORKING]  
Dashboard Display
```

## Service Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                Enhanced Token Bridge Service            │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────────────────────┐│
│  │   Data Ingestion │  │    Data Transformation          ││
│  │   - JSONL Analysis│  │    - Schema Mapping             ││
│  │   - Result Capture│  │    - Data Validation            ││
│  │   - Batch Processing│  │    - Deduplication Logic       ││
│  └─────────────────┘  └─────────────────────────────────┘│
│  ┌─────────────────┐  ┌─────────────────────────────────┐│
│  │   Storage Layer │  │    Integration Layer            ││
│  │   - ClickHouse   │  │    - Dashboard API              ││
│  │   - Bulk Insert  │  │    - Health Monitoring          ││
│  │   - Transaction  │  │    - Error Recovery             ││
│  └─────────────────┘  └─────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### Service Location
- **File Path**: `src/context_cleaner/telemetry/enhanced_token_bridge.py`
- **Package**: `context_cleaner.telemetry.enhanced_token_bridge`
- **Dependencies**: 
  - `context_cleaner.analysis.enhanced_token_counter`
  - `context_cleaner.telemetry.clients.clickhouse_client`
  - `context_cleaner.telemetry.jsonl_enhancement`

## API Specification

### Core Service Class

```python
class EnhancedTokenDatabaseBridge:
    """
    Service for bridging Enhanced Token Analysis results to ClickHouse database.
    
    Handles data transformation, validation, storage, and synchronization between
    the JSONL-based enhanced token analysis and the telemetry database.
    """
    
    def __init__(
        self, 
        clickhouse_client: ClickHouseClient,
        token_counter: EnhancedTokenCounter,
        batch_size: int = 1000,
        enable_validation: bool = True
    ):
        """Initialize bridge service with required dependencies."""
```

### Primary Methods

#### Data Storage Operations

```python
async def store_enhanced_analysis(
    self, 
    analysis: EnhancedTokenAnalysis,
    session_id: Optional[str] = None,
    force_update: bool = False
) -> BridgeResult:
    """
    Store enhanced token analysis results in ClickHouse database.
    
    Args:
        analysis: Enhanced token analysis results to store
        session_id: Optional session identifier for tracking
        force_update: Force update even if data exists
        
    Returns:
        BridgeResult containing success status, record count, and any errors
        
    Raises:
        BridgeStorageError: When database storage fails
        BridgeValidationError: When data validation fails
    """
```

```python
async def backfill_historical_data(
    self,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    batch_size: int = 100,
    progress_callback: Optional[Callable] = None
) -> BackfillResult:
    """
    Backfill historical enhanced token analysis data from JSONL files.
    
    Processes all historical JSONL files and stores enhanced analysis
    results in database. Critical for populating 2.768B tokens.
    
    Args:
        start_date: Optional start date filter
        end_date: Optional end date filter  
        batch_size: Number of files to process per batch
        progress_callback: Optional callback for progress updates
        
    Returns:
        BackfillResult with total tokens processed, files analyzed, duration
        
    Raises:
        BackfillError: When historical data processing fails
    """
```

#### Synchronization Operations

```python
async def sync_session_tokens(
    self, 
    session_id: str,
    incremental: bool = True
) -> SyncResult:
    """
    Synchronize enhanced token analysis for specific session.
    
    Args:
        session_id: Session to synchronize
        incremental: Only process new/modified data
        
    Returns:
        SyncResult with synchronization status and metrics
    """
```

```python
async def sync_all_sessions(
    self,
    since: Optional[datetime] = None,
    parallel_limit: int = 5
) -> List[SyncResult]:
    """
    Synchronize enhanced token analysis for all sessions.
    
    Args:
        since: Only sync data modified after this timestamp
        parallel_limit: Maximum concurrent sync operations
        
    Returns:
        List of SyncResult for each session processed
    """
```

#### Data Retrieval Operations

```python
async def get_stored_token_summaries(
    self,
    session_ids: Optional[List[str]] = None,
    days: int = 7,
    include_metadata: bool = False
) -> List[TokenSummaryRecord]:
    """
    Retrieve stored token summaries from database.
    
    Args:
        session_ids: Optional list of specific sessions
        days: Number of days to retrieve (default 7)
        include_metadata: Include analysis metadata
        
    Returns:
        List of stored token summary records
    """
```

### Data Models

#### Enhanced Token Analysis Result

```python
@dataclass
class EnhancedTokenAnalysis:
    """Enhanced token analysis results from JSONL processing."""
    analysis_id: str
    session_id: str
    timestamp: datetime
    
    # Token counts
    reported_input_tokens: int
    reported_output_tokens: int
    reported_cache_creation_tokens: int
    reported_cache_read_tokens: int
    calculated_total_tokens: int
    
    # Analysis metadata
    accuracy_ratio: float
    undercount_percentage: float
    files_processed: int
    content_categories: Dict[str, int]
    
    # Processing metadata
    processing_duration: float
    memory_usage_mb: float
    analysis_version: str
```

#### Bridge Operation Results

```python
@dataclass
class BridgeResult:
    """Result of bridge storage operation."""
    success: bool
    records_stored: int
    total_tokens: int
    processing_time: float
    errors: List[str]
    session_id: Optional[str] = None
```

```python
@dataclass
class BackfillResult:
    """Result of historical data backfill operation."""
    success: bool
    total_files_processed: int
    total_tokens_stored: int
    total_sessions: int
    processing_duration: float
    errors: List[str]
    skipped_files: List[str]
```

## Error Handling Strategy

### Exception Hierarchy

```python
class BridgeError(Exception):
    """Base exception for bridge operations."""
    
class BridgeConnectionError(BridgeError):
    """Database connection failures."""
    
class BridgeStorageError(BridgeError):
    """Data storage operation failures."""
    
class BridgeValidationError(BridgeError):
    """Data validation failures."""
    
class BackfillError(BridgeError):
    """Historical data backfill failures."""
```

### Error Recovery Patterns

#### Database Connection Recovery

```python
async def _execute_with_retry(
    self,
    operation: Callable,
    max_retries: int = 3,
    backoff_factor: float = 2.0
) -> Any:
    """
    Execute database operation with exponential backoff retry logic.
    
    Handles temporary connection failures and database unavailability.
    """
```

#### Graceful Degradation

```python
async def get_analysis_with_fallback(
    self, 
    session_id: str
) -> EnhancedTokenAnalysis:
    """
    Get enhanced analysis with fallback to direct JSONL processing.
    
    Priority:
    1. Try database-stored analysis
    2. Fall back to live enhanced token analysis
    3. Return cached results if available
    """
```

## Performance Requirements

### Service Level Agreements (SLA)

| Operation | Target Response Time | Memory Limit | Concurrent Operations |
|-----------|---------------------|--------------|----------------------|
| Single Analysis Storage | < 200ms | < 10MB | Up to 10 |
| Batch Storage (100 records) | < 2 seconds | < 50MB | Up to 5 |
| Historical Backfill | < 30 minutes | < 200MB | 1 |
| Session Sync | < 5 seconds | < 25MB | Up to 10 |

### Performance Optimization Strategies

#### Batch Processing
```python
async def _batch_store_analyses(
    self,
    analyses: List[EnhancedTokenAnalysis],
    batch_size: int = 1000
) -> List[BridgeResult]:
    """Store multiple analyses using ClickHouse batch insert capabilities."""
```

#### Connection Pooling
```python
class BridgeConnectionPool:
    """Managed connection pool for ClickHouse operations."""
    
    async def acquire_connection(self) -> ClickHouseConnection:
        """Acquire connection from pool with health checking."""
        
    async def release_connection(self, conn: ClickHouseConnection):
        """Return connection to pool after use."""
```

#### Caching Strategy
```python
class BridgeCache:
    """In-memory cache for frequently accessed token summaries."""
    
    def __init__(self, ttl_seconds: int = 600, max_entries: int = 1000):
        """Initialize cache with TTL and size limits."""
```

## Data Validation

### Input Validation Rules

```python
class AnalysisValidator:
    """Validator for enhanced token analysis data."""
    
    def validate_analysis(self, analysis: EnhancedTokenAnalysis) -> ValidationResult:
        """
        Validate analysis data before storage.
        
        Checks:
        - Token count consistency (total = sum of components)
        - Reasonable accuracy ratio (0.0 <= ratio <= 2.0)
        - Valid timestamp ranges
        - Required fields present
        - Data type correctness
        """
```

### Data Integrity Checks

```python
async def verify_data_integrity(
    self,
    session_id: str,
    tolerance: float = 0.01
) -> IntegrityResult:
    """
    Verify stored data matches enhanced analysis results.
    
    Cross-validates database records against live analysis to ensure
    data bridge integrity and detect corruption.
    """
```

## Integration Patterns

### Dashboard Integration

```python
class DashboardBridgeAdapter:
    """Adapter for dashboard integration with bridge service."""
    
    async def get_dashboard_token_metrics(
        self,
        time_range: TimeRange
    ) -> DashboardTokenMetrics:
        """
        Get token metrics optimized for dashboard display.
        
        Returns aggregated token counts, session breakdowns,
        and trend analysis data.
        """
```

### JSONL Processor Integration

```python
class JSONLProcessorBridge:
    """Integration bridge with JSONL content processor."""
    
    async def on_content_batch_processed(
        self,
        batch_result: BatchProcessingResult
    ):
        """
        Triggered after JSONL content batch processing.
        Automatically runs enhanced analysis and stores results.
        """
```

## Monitoring and Observability

### Health Checks

```python
async def health_check(self) -> HealthStatus:
    """
    Comprehensive health check for bridge service.
    
    Validates:
    - Database connectivity
    - Enhanced analysis system availability  
    - Recent data freshness
    - Error rate thresholds
    """
```

### Metrics Collection

```python
class BridgeMetrics:
    """Metrics collection for bridge operations."""
    
    # Performance metrics
    storage_operation_duration: Histogram
    backfill_progress_gauge: Gauge
    error_rate_counter: Counter
    
    # Data metrics  
    tokens_stored_total: Counter
    sessions_synchronized: Counter
    data_freshness_gauge: Gauge
```

### Logging Strategy

```python
# Structured logging with correlation IDs
logger.info(
    "Bridge storage completed",
    extra={
        "operation": "store_enhanced_analysis",
        "session_id": session_id,
        "tokens_stored": result.total_tokens,
        "processing_time": result.processing_time,
        "correlation_id": correlation_id
    }
)
```

## Security Considerations

### Data Privacy
- All JSONL content processed in memory only
- No persistent storage of conversation content
- Only aggregate token metrics stored in database

### Access Control
- Bridge service requires database write permissions
- Read-only access for dashboard queries
- Administrative access for backfill operations

### Audit Trail
```python
async def log_bridge_operation(
    self,
    operation: str,
    session_id: str,
    result: BridgeResult
):
    """Log all bridge operations for audit compliance."""
```

## Testing Strategy

### Unit Tests
- Data transformation validation
- Error handling verification
- Caching behavior testing
- Connection pooling testing

### Integration Tests
- End-to-end data flow validation
- Database schema compatibility
- Performance benchmarking
- Error recovery testing

### Load Testing
- Historical backfill performance (2.7B tokens)
- Concurrent operation handling
- Memory usage under load
- Database connection limits

## Deployment Considerations

### Configuration

```yaml
# bridge_config.yaml
enhanced_token_bridge:
  clickhouse:
    connection_pool_size: 10
    connection_timeout: 30s
    retry_attempts: 3
    
  processing:
    batch_size: 1000
    max_memory_mb: 200
    parallel_limit: 5
    
  caching:
    ttl_seconds: 600
    max_entries: 1000
    
  monitoring:
    health_check_interval: 60s
    metrics_export_interval: 30s
```

### Rollback Strategy

```python
async def rollback_bridge_integration(
    self,
    checkpoint: str
) -> RollbackResult:
    """
    Rollback bridge integration to previous stable state.
    
    Used if bridge implementation causes issues with existing system.
    Falls back to direct enhanced analysis without database storage.
    """
```

## Migration Path

### Phase 1: Service Implementation
1. Implement core `EnhancedTokenDatabaseBridge` class
2. Add database schema for token summaries
3. Create basic storage and retrieval operations

### Phase 2: Historical Backfill  
1. Implement `backfill_historical_data()` method
2. Process all 88 JSONL files to populate 2.7B tokens
3. Validate data integrity across systems

### Phase 3: Dashboard Integration
1. Update dashboard to use bridge service
2. Add real-time synchronization
3. Implement performance monitoring

## Success Criteria

### Functional Requirements
- [ ] Bridge service successfully stores enhanced analysis results
- [ ] Historical backfill completes without data loss
- [ ] Dashboard displays accurate 2.768B token count from database
- [ ] Real-time synchronization maintains data freshness

### Performance Requirements  
- [ ] Single analysis storage completes in < 200ms
- [ ] Historical backfill completes in < 30 minutes
- [ ] Service maintains < 50MB memory usage under normal load
- [ ] Error rate stays below 0.1% for storage operations

### Reliability Requirements
- [ ] Service handles database connectivity issues gracefully
- [ ] Data integrity maintained across all operations
- [ ] Rollback capability preserves system functionality
- [ ] Monitoring provides clear visibility into bridge health

---

**Next Steps**: 
1. Create `token-summary-database-schema.md` specification
2. Create `historical-data-migration.md` specification  
3. Begin implementation of `EnhancedTokenDatabaseBridge` service
4. Set up database schema for token summaries
5. Implement and test historical data backfill process