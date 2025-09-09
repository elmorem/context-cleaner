# Historical Data Migration Specification

**Version**: 1.0  
**Status**: DRAFT  
**Priority**: CRITICAL  
**Created**: 2025-09-09  

## Executive Summary

This specification defines the strategy and procedures for migrating 2.768 billion tokens from Enhanced Token Analysis (JSONL file-based) into the ClickHouse database. This one-time migration resolves the critical data loss issue and establishes the foundation for ongoing data synchronization.

## Migration Overview

### Scope and Scale

**Data Volume**: 2,768,012,012 tokens across 88 JSONL files  
**Source System**: Enhanced Token Analysis (direct JSONL file processing)  
**Target System**: ClickHouse telemetry database  
**Migration Type**: One-time historical backfill with ongoing incremental sync  
**Criticality**: CRITICAL - Dashboard cannot show accurate data without this migration

### Current State Assessment

**Source Data Status**:
- ✅ **Enhanced Token Analysis**: Working perfectly, returns accurate 2.768B token count
- ✅ **JSONL Files**: 88 files in `~/.claude/projects` directory, all accessible  
- ✅ **Analysis Engine**: Successfully processes all files with consistent results

**Target Infrastructure Status**:
- ⚠️ **ClickHouse Database**: Accessible but missing token summary schema
- ⚠️ **Data Bridge**: Service not yet implemented
- ⚠️ **Schema**: Token summary tables not created

## Migration Architecture

### High-Level Migration Flow

```
Phase 1: Pre-Migration Setup
├── Database schema creation
├── Bridge service implementation  
├── Data validation framework setup
└── Rollback procedure preparation

Phase 2: Historical Data Processing
├── JSONL file discovery and cataloging
├── Enhanced token analysis execution
├── Data transformation and validation
└── Batch insertion into ClickHouse

Phase 3: Post-Migration Validation
├── Data integrity verification
├── Performance benchmarking
├── Dashboard integration testing
└── Rollback capability testing

Phase 4: Ongoing Synchronization Setup
├── Incremental sync mechanism
├── Real-time trigger implementation
├── Monitoring and alerting setup
└── Maintenance procedure documentation
```

### Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Historical Data Migration                  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────────────────────────┐│
│  │   Discovery     │  │    Analysis Processing              ││
│  │   - JSONL scan  │  │    - Enhanced token analysis       ││
│  │   - File catalog│  │    - Session identification        ││
│  │   - Change det. │  │    - Data transformation           ││
│  └─────────────────┘  └─────────────────────────────────────┘│
│  ┌─────────────────┐  ┌─────────────────────────────────────┐│
│  │   Validation    │  │    Database Operations              ││
│  │   - Data integ. │  │    - Batch insertion                ││
│  │   - Consistency │  │    - Transaction management         ││
│  │   - Error check │  │    - Performance optimization       ││
│  └─────────────────┘  └─────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Migration Service Implementation

### Core Migration Service

```python
class HistoricalDataMigrator:
    """
    Service for migrating historical Enhanced Token Analysis data to ClickHouse.
    
    Handles discovery, processing, validation, and insertion of 2.768B tokens
    from 88 JSONL files into database storage.
    """
    
    def __init__(
        self,
        clickhouse_client: ClickHouseClient,
        token_counter: EnhancedTokenCounter,
        bridge_service: EnhancedTokenDatabaseBridge,
        batch_size: int = 100,
        parallel_workers: int = 3,
        validation_enabled: bool = True
    ):
        """Initialize migration service with required dependencies."""
```

### Primary Migration Operations

#### Full Historical Migration

```python
async def migrate_all_historical_data(
    self,
    source_directory: str = "~/.claude/projects",
    dry_run: bool = False,
    progress_callback: Optional[Callable] = None,
    checkpoint_interval: int = 10
) -> HistoricalMigrationResult:
    """
    Migrate all historical JSONL data to ClickHouse database.
    
    Args:
        source_directory: Directory containing JSONL files
        dry_run: Validate migration without actual data insertion
        progress_callback: Optional callback for progress updates
        checkpoint_interval: Files processed between checkpoints
        
    Returns:
        HistoricalMigrationResult with comprehensive migration metrics
        
    Raises:
        MigrationError: When migration process fails
        ValidationError: When data validation fails
        DatabaseError: When database operations fail
    """
```

#### Incremental Migration

```python
async def migrate_incremental_changes(
    self,
    since: datetime,
    modified_files_only: bool = True,
    force_reanalysis: bool = False
) -> IncrementalMigrationResult:
    """
    Migrate only changed or new JSONL data since last migration.
    
    Args:
        since: Only process files modified after this timestamp
        modified_files_only: Skip unchanged files
        force_reanalysis: Reprocess all files regardless of modification time
        
    Returns:
        IncrementalMigrationResult with delta migration metrics
    """
```

#### Migration Validation

```python
async def validate_migration_integrity(
    self,
    sample_size: int = 100,
    full_validation: bool = False,
    tolerance: float = 0.001
) -> ValidationResult:
    """
    Validate migrated data integrity against source analysis.
    
    Cross-validates database records against live enhanced analysis
    to ensure migration accuracy and detect data corruption.
    
    Args:
        sample_size: Number of sessions to validate (if not full)
        full_validation: Validate all migrated data
        tolerance: Acceptable variance in token counts
        
    Returns:
        ValidationResult with detailed validation metrics
    """
```

### Migration Data Models

#### Migration Result Tracking

```python
@dataclass
class HistoricalMigrationResult:
    """Comprehensive result of historical data migration."""
    migration_id: str
    start_time: datetime
    end_time: datetime
    success: bool
    
    # File processing metrics
    total_files_found: int
    files_processed: int
    files_skipped: int
    files_failed: int
    
    # Token migration metrics  
    total_tokens_migrated: int
    total_sessions_created: int
    total_records_inserted: int
    
    # Performance metrics
    processing_duration: float
    average_processing_speed_tokens_per_second: float
    peak_memory_usage_mb: float
    database_insertion_time: float
    
    # Error tracking
    errors: List[MigrationError]
    warnings: List[str]
    skipped_files: List[str]
    
    # Data quality metrics
    data_integrity_score: float
    validation_passed: bool
    consistency_check_results: Dict[str, Any]
```

#### Migration Progress Tracking

```python
@dataclass  
class MigrationProgress:
    """Real-time migration progress tracking."""
    migration_id: str
    current_phase: str
    files_completed: int
    files_remaining: int
    tokens_processed: int
    estimated_completion_time: datetime
    current_processing_rate: float
    errors_encountered: int
    warnings_count: int
```

## Migration Phases

### Phase 1: Pre-Migration Setup

#### Database Schema Preparation

```python
async def setup_migration_infrastructure(self) -> SetupResult:
    """
    Prepare database and services for historical migration.
    
    Steps:
    1. Create token summary database schema
    2. Initialize enhanced token bridge service
    3. Set up data validation framework
    4. Create migration tracking tables
    5. Prepare rollback procedures
    """
```

**Schema Creation Order**:
1. Create `enhanced_token_summaries` table
2. Create `enhanced_token_details` table  
3. Create `enhanced_analysis_metadata` table
4. Create migration tracking tables
5. Set up indexes and partitions
6. Configure TTL policies

#### Migration Tracking Tables

```sql
CREATE TABLE migration_execution_log (
    migration_id String,
    execution_timestamp DateTime64(3),
    phase String,
    operation String,
    status Enum8('started' = 1, 'completed' = 2, 'failed' = 3),
    details String,
    processing_time_ms UInt32
) ENGINE = MergeTree()
ORDER BY (migration_id, execution_timestamp);

CREATE TABLE migration_file_tracking (
    migration_id String,
    file_path String,
    file_hash String,
    processing_status Enum8('pending' = 1, 'processing' = 2, 'completed' = 3, 'failed' = 4),
    tokens_found UInt64,
    records_inserted UInt32,
    error_message String,
    processed_at DateTime64(3)
) ENGINE = MergeTree()
ORDER BY (migration_id, file_path);
```

### Phase 2: Historical Data Processing

#### File Discovery and Cataloging

```python
async def discover_jsonl_files(
    self,
    source_directory: str,
    file_pattern: str = "*.jsonl"
) -> FileDiscoveryResult:
    """
    Discover and catalog all JSONL files for migration.
    
    Returns:
        FileDiscoveryResult containing file paths, sizes, modification times,
        and preliminary metadata for processing prioritization.
    """
```

**Discovery Logic**:
```python
# File discovery algorithm
for file_path in glob.glob(f"{source_directory}/**/{file_pattern}", recursive=True):
    file_stats = os.stat(file_path)
    file_info = JSONLFileInfo(
        path=file_path,
        size_bytes=file_stats.st_size,
        modified_at=datetime.fromtimestamp(file_stats.st_mtime),
        estimated_sessions=estimate_sessions_from_file_size(file_stats.st_size)
    )
    discovered_files.append(file_info)
```

#### Batch Processing Strategy

```python
async def process_file_batch(
    self,
    file_batch: List[str],
    batch_id: str
) -> BatchProcessingResult:
    """
    Process a batch of JSONL files for token analysis and database insertion.
    
    Processing Steps:
    1. Load JSONL files into memory (with memory management)
    2. Execute enhanced token analysis on batch
    3. Transform analysis results into database records
    4. Validate data integrity and consistency
    5. Insert records into ClickHouse using bulk operations
    6. Update migration tracking and checkpoint progress
    """
```

**Memory Management Strategy**:
```python
# Memory-efficient batch processing
MAX_BATCH_MEMORY = 200 * 1024 * 1024  # 200MB limit
current_memory = 0

for file_path in batch_files:
    file_size = os.path.getsize(file_path)
    if current_memory + file_size > MAX_BATCH_MEMORY:
        # Process current batch and clear memory
        await process_and_insert_batch(current_batch)
        current_batch.clear()
        current_memory = 0
    
    current_batch.append(file_path)
    current_memory += file_size
```

### Phase 3: Post-Migration Validation

#### Data Integrity Verification

```python
async def verify_migration_completeness(self) -> CompletenessResult:
    """
    Verify all expected data was migrated successfully.
    
    Validation Checks:
    1. Token count reconciliation (source vs database)
    2. Session count verification
    3. File processing confirmation
    4. Data consistency across tables
    5. Referential integrity validation
    """
```

**Token Count Reconciliation**:
```python
# Compare source analysis with database totals
source_analysis = await self.token_counter.get_enhanced_analysis()
database_totals = await self.bridge_service.get_migration_totals()

token_variance = abs(source_analysis.calculated_total_tokens - database_totals.total_tokens)
variance_percentage = (token_variance / source_analysis.calculated_total_tokens) * 100

if variance_percentage > self.tolerance_percentage:
    raise MigrationValidationError(f"Token count variance {variance_percentage}% exceeds tolerance")
```

#### Performance Benchmarking

```python
async def benchmark_migration_performance(self) -> PerformanceBenchmark:
    """
    Benchmark migration performance for future optimization.
    
    Metrics:
    - Tokens processed per second
    - Files processed per minute
    - Database insertion throughput
    - Memory usage patterns
    - Error rates and recovery times
    """
```

### Phase 4: Ongoing Synchronization Setup

#### Incremental Sync Configuration

```python
async def setup_incremental_sync(
    self,
    sync_interval_minutes: int = 60,
    enable_real_time: bool = False
) -> SyncSetupResult:
    """
    Configure ongoing synchronization for new JSONL data.
    
    Options:
    - Scheduled periodic sync (hourly/daily)
    - Real-time file system monitoring
    - Manual trigger via API/dashboard
    - Event-driven sync on content processing
    """
```

## Migration Performance Strategy

### Optimization Techniques

#### Parallel Processing

```python
# Parallel file processing with worker pools
async def process_files_parallel(
    self,
    file_list: List[str],
    max_workers: int = 3
) -> List[ProcessingResult]:
    """Process multiple files concurrently with resource limits."""
    
    semaphore = asyncio.Semaphore(max_workers)
    
    async def process_with_limit(file_path):
        async with semaphore:
            return await self.process_single_file(file_path)
    
    tasks = [process_with_limit(file_path) for file_path in file_list]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

#### Batch Database Operations

```python
# Bulk insertion for optimal database performance
async def bulk_insert_token_summaries(
    self,
    summaries: List[TokenSummaryRecord],
    batch_size: int = 1000
) -> BulkInsertResult:
    """Insert token summaries using ClickHouse batch operations."""
    
    for batch in chunk_list(summaries, batch_size):
        insert_query = """
            INSERT INTO enhanced_token_summaries 
            (analysis_id, session_id, timestamp, calculated_total_tokens, ...)
            VALUES
        """
        values = [(s.analysis_id, s.session_id, s.timestamp, s.total_tokens, ...) 
                 for s in batch]
        
        await self.clickhouse_client.execute_batch(insert_query, values)
```

### Resource Management

#### Memory Usage Control

```python
class MigrationMemoryManager:
    """Memory management for large-scale migration operations."""
    
    def __init__(self, max_memory_mb: int = 200):
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.current_usage = 0
        
    async def check_memory_availability(self, required_bytes: int) -> bool:
        """Check if enough memory available for operation."""
        return self.current_usage + required_bytes <= self.max_memory_bytes
        
    async def cleanup_if_needed(self):
        """Force garbage collection if memory usage high."""
        if self.current_usage > self.max_memory_bytes * 0.8:
            gc.collect()
            self.current_usage = psutil.Process().memory_info().rss
```

#### Database Connection Management

```python
class MigrationConnectionPool:
    """Dedicated connection pool for migration operations."""
    
    def __init__(self, pool_size: int = 5, migration_timeout: int = 300):
        self.pool_size = pool_size
        self.timeout = migration_timeout
        self.connections = asyncio.Queue(maxsize=pool_size)
        
    async def get_connection(self) -> ClickHouseConnection:
        """Get connection optimized for bulk operations."""
        return await asyncio.wait_for(
            self.connections.get(),
            timeout=self.timeout
        )
```

## Error Handling and Recovery

### Error Classification

```python
class MigrationError(Exception):
    """Base class for migration errors."""
    
class FileAccessError(MigrationError):
    """JSONL file cannot be read or accessed."""
    
class AnalysisError(MigrationError):
    """Enhanced token analysis failed."""
    
class DatabaseError(MigrationError):
    """Database operation failed."""
    
class ValidationError(MigrationError):
    """Data validation failed."""
    
class ResourceError(MigrationError):
    """Insufficient system resources."""
```

### Recovery Strategies

#### Checkpoint and Resume

```python
async def create_migration_checkpoint(
    self,
    migration_id: str,
    completed_files: List[str],
    current_state: Dict[str, Any]
) -> CheckpointResult:
    """Create checkpoint for resumable migration."""
    
    checkpoint_data = {
        'migration_id': migration_id,
        'timestamp': datetime.now().isoformat(),
        'completed_files': completed_files,
        'current_state': current_state,
        'total_tokens_processed': current_state.get('tokens_processed', 0)
    }
    
    await self.save_checkpoint(checkpoint_data)
```

#### Rollback Procedures

```python
async def rollback_migration(
    self,
    migration_id: str,
    rollback_to_checkpoint: Optional[str] = None
) -> RollbackResult:
    """
    Rollback migration to previous state.
    
    Rollback Options:
    1. Complete rollback - remove all migrated data
    2. Partial rollback - rollback to specific checkpoint
    3. Data-only rollback - keep schema, remove data
    4. Schema rollback - remove tables and data
    """
```

## Monitoring and Observability

### Migration Metrics

```python
class MigrationMetrics:
    """Comprehensive metrics for migration monitoring."""
    
    # Progress metrics
    files_processed_counter: Counter
    tokens_migrated_counter: Counter
    migration_duration_histogram: Histogram
    
    # Performance metrics
    processing_rate_gauge: Gauge  # tokens/second
    memory_usage_gauge: Gauge     # MB
    database_latency_histogram: Histogram
    
    # Error metrics
    error_rate_counter: Counter
    retry_attempts_counter: Counter
    failed_files_counter: Counter
```

### Real-time Progress Dashboard

```python
async def get_migration_status(
    self,
    migration_id: str
) -> MigrationStatus:
    """
    Get real-time migration status for dashboard display.
    
    Returns:
        Current progress, performance metrics, error counts,
        estimated completion time, and resource usage.
    """
```

### Alerting Configuration

```python
# Migration alert thresholds
MIGRATION_ALERTS = {
    'high_error_rate': {'threshold': 0.05, 'window': '5m'},
    'slow_processing': {'threshold': 1000, 'metric': 'tokens_per_second'},
    'high_memory_usage': {'threshold': 0.9, 'metric': 'memory_usage_ratio'},
    'migration_stalled': {'threshold': 300, 'metric': 'seconds_without_progress'}
}
```

## Testing Strategy

### Pre-Migration Testing

#### Dry Run Validation

```python
async def dry_run_migration(
    self,
    sample_size: int = 10,
    validate_all_operations: bool = True
) -> DryRunResult:
    """
    Execute complete migration workflow without database changes.
    
    Validates:
    - File discovery and access
    - Enhanced token analysis execution
    - Data transformation accuracy
    - Database schema compatibility
    - Performance projections
    """
```

#### Schema Compatibility Testing

```python
async def test_schema_compatibility(self) -> CompatibilityResult:
    """
    Test database schema compatibility with migration data.
    
    Tests:
    - Data type mapping
    - Constraint validation
    - Index performance
    - Foreign key relationships
    """
```

### Migration Testing

#### Integration Testing

```python
async def test_end_to_end_migration(
    self,
    test_data_size: int = 100_000  # 100K tokens
) -> IntegrationTestResult:
    """
    Test complete migration pipeline with controlled test data.
    
    Creates test JSONL files, executes migration, validates results.
    """
```

#### Performance Testing

```python
async def performance_test_migration(
    self,
    test_scale: str = 'medium'  # small, medium, large
) -> PerformanceTestResult:
    """
    Test migration performance at various scales.
    
    Measures processing rates, memory usage, database throughput.
    """
```

### Post-Migration Testing

#### Data Integrity Validation

```python
async def comprehensive_data_validation(self) -> ValidationSuite:
    """
    Complete validation of migrated data integrity.
    
    Validates:
    - Token count accuracy
    - Session data completeness
    - Cross-table referential integrity
    - Data consistency rules
    """
```

## Deployment Strategy

### Pre-Deployment Checklist

- [ ] **Database Preparation**
  - [ ] ClickHouse cluster health verified
  - [ ] Sufficient storage space available (estimate 500MB)
  - [ ] Database backup completed
  - [ ] Migration user permissions configured

- [ ] **Service Readiness**  
  - [ ] Enhanced Token Bridge service implemented
  - [ ] Migration service code deployed
  - [ ] Configuration files prepared
  - [ ] Monitoring and alerting configured

- [ ] **Data Validation**
  - [ ] Enhanced Token Analysis verified working
  - [ ] JSONL files accessible (all 88 files)
  - [ ] Test migration completed successfully
  - [ ] Rollback procedures tested

### Migration Execution Plan

#### Phase 1: Infrastructure Setup (30 minutes)
```bash
# 1. Create database schema
./scripts/create_token_schema.sql

# 2. Deploy bridge service
./scripts/deploy_bridge_service.sh

# 3. Initialize monitoring
./scripts/setup_migration_monitoring.sh
```

#### Phase 2: Migration Execution (2-3 hours)
```bash
# 1. Start migration with checkpoints
python -m context_cleaner.migration.historical_migrator \
  --source-dir ~/.claude/projects \
  --checkpoint-interval 10 \
  --batch-size 100 \
  --parallel-workers 3

# 2. Monitor progress
./scripts/monitor_migration_progress.sh
```

#### Phase 3: Validation and Integration (1 hour)  
```bash
# 1. Validate migration completeness
python -m context_cleaner.migration.validator \
  --full-validation \
  --tolerance 0.001

# 2. Update dashboard configuration
./scripts/configure_dashboard_database_mode.sh

# 3. Test end-to-end functionality
./scripts/test_dashboard_integration.sh
```

### Rollback Plan

#### Immediate Rollback (< 5 minutes)
```bash
# Disable database mode, revert to direct analysis
./scripts/emergency_rollback_to_direct_analysis.sh
```

#### Complete Migration Rollback (15-30 minutes)
```bash
# Remove migrated data and schema changes
./scripts/full_migration_rollback.sh
```

## Success Criteria

### Migration Success Metrics

- [ ] **Data Completeness**: 2.768 billion tokens successfully migrated (100% target)
- [ ] **Processing Performance**: Migration completes within 4 hours
- [ ] **Data Accuracy**: Token count variance < 0.1% from source analysis
- [ ] **System Stability**: Migration process maintains < 200MB memory usage
- [ ] **Error Tolerance**: < 1% file processing error rate

### Post-Migration Success Criteria

- [ ] **Dashboard Integration**: Dashboard displays accurate 2.768B token count from database
- [ ] **Query Performance**: Token summary queries complete within 500ms
- [ ] **Data Freshness**: Incremental sync maintains < 1 hour data lag
- [ ] **System Reliability**: Bridge service maintains 99.9% uptime
- [ ] **Rollback Capability**: Complete rollback possible within 30 minutes

### Operational Readiness

- [ ] **Monitoring**: Full observability into migration and ongoing sync health
- [ ] **Alerting**: Automated alerts for migration failures and data inconsistencies  
- [ ] **Documentation**: Complete operational procedures for maintenance and troubleshooting
- [ ] **Training**: Team familiar with migration procedures and rollback processes

---

**Next Steps**:
1. Update project roadmap with PR22 and completed items
2. Begin Step 1: Comprehensive Code Analysis
3. Implement database schema creation scripts
4. Develop Enhanced Token Bridge Service
5. Create and test historical migration procedures