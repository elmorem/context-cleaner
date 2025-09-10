# CCUSAGE Token Count Accuracy Implementation Plan

## Executive Summary

**CRITICAL FINDING**: The context-cleaner codebase has **severe architectural issues** with token calculation accuracy. Despite implementing enhanced token counting infrastructure to match ccusage standards, **22 files still use legacy estimation methods** and **the "enhanced" token counter itself contains legacy fallback code**, completely undermining accuracy improvements.

**Immediate Impact**: The "Context Window Usage by Directory" widget and multiple other dashboard components are showing dramatically incorrect token counts due to mixed implementation of old and new calculation methods.

## Root Cause Analysis

### The Core Problem
```
Enhanced Infrastructure ✅ EXISTS but Legacy Methods ❌ STILL ACTIVE
Result: Inconsistent, inaccurate token calculations throughout the system
```

### Architectural Issues Identified
1. **Self-defeating Enhanced Token Counter**: Contains `* 1.3` legacy fallback
2. **Multiple Token Calculation Pathways**: Enhanced and legacy systems coexist
3. **Inconsistent Routing**: Components bypass enhanced analysis for crude estimates
4. **Mixed Implementation**: Dashboard receives data from both accurate and inaccurate sources

## Implementation Plan

### Phase 1: CRITICAL FIXES (Priority 1 - Immediate)

#### Fix 1.1: Enhanced Token Counter Self-Defeating Fallback
- **File**: `/Users/markelmore/_code/context-cleaner/src/context_cleaner/analysis/enhanced_token_counter.py:450`
- **Status**: ✅ **COMPLETED** - Fixed in Phase 3 comprehensive cleanup
- **Previous Problem**: 
  ```python
  estimated_tokens = len(content.split()) * 1.3  # Rough token-to-word ratio (LEGACY)
  ```
- **Solution**: Replace with proper JSONL token extraction or return 0
- **Implementation**:
  ```python
  # BEFORE (legacy fallback defeating the purpose):
  if content:
      estimated_tokens = len(content.split()) * 1.3
      session_metrics.calculated_total_tokens += int(estimated_tokens)
  
  # AFTER (use actual JSONL token data or fail gracefully):
  if usage_data and any(key in usage_data for key in ['input_tokens', 'output_tokens']):
      # Use actual token data from JSONL
      token_metrics = self._parse_token_metrics(usage_data)
      session_metrics.calculated_total_tokens += token_metrics.total_tokens
  else:
      # No estimation fallback - return 0 to maintain accuracy
      logger.warning(f"No token data available for message, skipping estimation")
  ```

#### Fix 1.2: Context Window Analyzer
- **File**: `/Users/markelmore/_code/context-cleaner/src/context_cleaner/analysis/context_window_analyzer.py:82`
- **Current Problem**: `estimated_tokens = file_size // 4`
- **Solution**: Use SessionCacheParser to extract actual token data from JSONL files
- **Implementation**:
  ```python
  def _analyze_session_context(self, session_file: str) -> Dict[str, any]:
      """Enhanced analysis using actual JSONL token data."""
      try:
          # Use SessionCacheParser for accurate token extraction
          from .session_parser import SessionCacheParser
          parser = SessionCacheParser()
          analysis = parser.parse_session_file(Path(session_file))
          
          if analysis:
              return {
                  'file_size_bytes': os.path.getsize(session_file),
                  'file_size_mb': round(os.path.getsize(session_file) / (1024 * 1024), 2),
                  'estimated_tokens': analysis.total_tokens,  # ACTUAL tokens from JSONL
                  'last_activity': analysis.end_time,
                  'entry_count': analysis.total_messages,
                  'tool_calls': len([tool for msg in analysis.file_operations for tool in msg.tool_usage]),
                  'file_reads': len([tool for msg in analysis.file_operations 
                                   for tool in msg.tool_usage if tool.tool_name == 'Read']),
                  'session_file': os.path.basename(session_file)
              }
      except Exception as e:
          logger.error(f"Enhanced analysis failed for {session_file}: {e}")
          # Fallback to basic file info without token estimation
          return self._fallback_basic_analysis(session_file)
  ```

#### Fix 1.3: Dashboard Total Token Calculation
- **File**: `/Users/markelmore/_code/context-cleaner/src/context_cleaner/dashboard/comprehensive_health_dashboard.py:3915`
- **Current Problem**: `return len(content_str) // 4`
- **Solution**: Route through enhanced token analysis service
- **Implementation**:
  ```python
  async def _calculate_total_tokens(self, context_data: Dict[str, Any]) -> int:
      """Calculate total tokens using enhanced analysis (no fallback estimation)."""
      try:
          # Route through enhanced token analysis
          from ..analysis.dashboard_integration import get_enhanced_token_analysis_sync
          enhanced_data = get_enhanced_token_analysis_sync(force_refresh=False)
          
          if enhanced_data and 'total_tokens' in enhanced_data:
              return enhanced_data['total_tokens']
          
          # If enhanced analysis fails, return 0 rather than crude estimate
          logger.warning("Enhanced token analysis unavailable, returning 0")
          return 0
          
      except Exception as e:
          logger.error(f"Token calculation failed: {e}")
          return 0
  ```

### Phase 2: HIGH PRIORITY FIXES (Priority 2)

#### Fix 2.1: Context Health Scorer
- **File**: `/Users/markelmore/_code/context-cleaner/src/context_cleaner/analytics/context_health_scorer.py:243`
- **Problem**: `estimated_tokens = size_bytes // 4`
- **Solution**: Integrate with enhanced token analysis or use ContextWindowAnalyzer

#### Fix 2.2: Bridge Services
- **File**: `/Users/markelmore/_code/context-cleaner/src/context_cleaner/bridges/incremental_sync.py:285`
- **Problem**: `estimated_tokens += len(content.split()) * 1.3`
- **Solution**: Use enhanced token extraction methods

#### Fix 2.3: Migration Services
- **File**: `/Users/markelmore/_code/context-cleaner/src/context_cleaner/migration/data_extraction.py:390`
- **Problem**: `estimated_tokens = len(content.split()) * 1.3`
- **Solution**: Route through SessionCacheParser for accurate token data

### Phase 3: COMPREHENSIVE CLEANUP (Priority 3)

#### All Remaining Legacy Patterns
**Division by 4 Pattern (`// 4`)** - 17+ files:
- `/Users/markelmore/_code/context-cleaner/src/context_cleaner/optimization/basic_analyzer.py:198`
- `/Users/markelmore/_code/context-cleaner/src/context_cleaner/core/redundancy_detector.py:330`
- Multiple other files identified by codebase-architect

**Multiplication by 1.3 Pattern (`* 1.3`)** - 6 files:
- All remaining files in migration, telemetry, and analytics directories

### Phase 4: ARCHITECTURAL CONSOLIDATION

#### 4.1: Create Unified Token Calculation Interface
```python
# NEW FILE: src/context_cleaner/core/token_calculator.py
from typing import Union, Optional
from pathlib import Path

class UnifiedTokenCalculator:
    """Single interface for all token calculations in the system."""
    
    async def calculate_tokens(self, source: Union[str, Path, Dict]) -> int:
        """
        Calculate tokens using best available method:
        1. JSONL token data (highest accuracy)
        2. Anthropic count-tokens API (high accuracy)
        3. Return 0 (no crude estimation)
        """
        if isinstance(source, Path) and source.suffix == '.jsonl':
            return await self._calculate_from_jsonl(source)
        elif isinstance(source, str):
            return await self._calculate_from_content(source)
        elif isinstance(source, dict) and 'usage' in source:
            return await self._calculate_from_usage_data(source)
        
        logger.warning(f"No reliable token calculation method for: {type(source)}")
        return 0
```

#### 4.2: Migration Strategy
1. **Update Components Incrementally**: Start with dashboard, then analytics, then utilities
2. **Add Deprecation Warnings**: Mark all `// 4` and `* 1.3` patterns as deprecated
3. **Create Migration Timeline**: 4-week plan to eliminate all legacy methods
4. **Add Monitoring**: Track which components use accurate vs. legacy calculations

## Detailed File-by-File Implementation

### CRITICAL PRIORITY FILES (Fix Immediately)

#### 1. enhanced_token_counter.py:450
```python
# Current (BROKEN):
if content:
    estimated_tokens = len(content.split()) * 1.3  # Defeats enhanced purpose!
    session_metrics.calculated_total_tokens += int(estimated_tokens)

# Fixed:
if message_data and 'usage' in message_data:
    usage = message_data['usage']
    if any(key in usage for key in ['input_tokens', 'output_tokens']):
        token_metrics = TokenMetrics(
            input_tokens=usage.get('input_tokens', 0),
            output_tokens=usage.get('output_tokens', 0),
            cache_creation_input_tokens=usage.get('cache_creation_input_tokens', 0),
            cache_read_input_tokens=usage.get('cache_read_input_tokens', 0)
        )
        session_metrics.calculated_total_tokens += token_metrics.total_tokens
        logger.debug(f"Used actual JSONL token data: {token_metrics.total_tokens}")
    else:
        logger.warning("No token usage data in message, skipping")
else:
    logger.warning("No message usage data available")
```

#### 2. context_window_analyzer.py:82
```python
# Current (BROKEN):
estimated_tokens = file_size // 4

# Fixed:
from .session_parser import SessionCacheParser

def _get_actual_tokens_from_jsonl(self, session_file: str) -> int:
    """Extract actual token counts from JSONL file."""
    try:
        parser = SessionCacheParser()
        analysis = parser.parse_session_file(Path(session_file))
        return analysis.total_tokens if analysis else 0
    except Exception as e:
        logger.error(f"Failed to parse JSONL tokens from {session_file}: {e}")
        return 0

# In _analyze_session_context:
actual_tokens = self._get_actual_tokens_from_jsonl(session_file)
return {
    'file_size_bytes': file_size,
    'file_size_mb': round(file_size_mb, 2),
    'estimated_tokens': actual_tokens,  # ACTUAL tokens, not estimated
    # ... rest of return data
}
```

#### 3. comprehensive_health_dashboard.py:3915
```python
# Current (BROKEN):
return len(content_str) // 4

# Fixed:
async def _calculate_total_tokens(self, context_data: Dict[str, Any]) -> int:
    """Use enhanced token analysis instead of character estimation."""
    try:
        from ..analysis.dashboard_integration import get_enhanced_token_analysis_sync
        enhanced_result = get_enhanced_token_analysis_sync()
        
        if enhanced_result.get('total_tokens'):
            return enhanced_result['total_tokens']
        
        logger.warning("Enhanced token analysis returned no data")
        return 0
        
    except Exception as e:
        logger.error(f"Enhanced token analysis failed: {e}")
        return 0
```

### Testing Strategy

#### Unit Tests
```python
# NEW FILE: tests/test_token_calculation_accuracy.py
class TestTokenCalculationAccuracy:
    def test_no_legacy_fallbacks(self):
        """Ensure no legacy * 1.3 or // 4 patterns remain."""
        
    def test_enhanced_counter_no_estimation(self):
        """Verify enhanced counter uses only JSONL data."""
        
    def test_dashboard_consistency(self):
        """Verify all dashboard widgets show same token counts."""
        
    def test_ccusage_compatibility(self):
        """Verify token calculations match ccusage methodology."""
```

#### Integration Tests
```python
def test_end_to_end_token_accuracy():
    """Test complete pipeline from JSONL to dashboard display."""
    # Load known JSONL file with specific token counts
    # Verify same counts appear in all dashboard widgets
    # Compare with ccusage calculations on same data
```

## Success Metrics

### Quantitative Goals
- **100% Legacy Method Elimination**: Zero `// 4` or `* 1.3` patterns remain
- **100% Accuracy Match**: Token counts match ccusage calculations exactly
- **100% Consistency**: All dashboard widgets show identical token counts for same data
- **Zero Estimation Fallbacks**: No crude estimation methods used anywhere

### Validation Process
1. **Before/After Comparison**: Document token count differences on same test data
2. **ccusage Cross-Validation**: Verify calculations match ccusage on identical JSONL files
3. **Dashboard Consistency Check**: All widgets must show same totals
4. **Performance Impact Assessment**: Ensure enhanced methods don't degrade performance

## Risk Assessment

### High Risk Issues
1. **Performance Impact**: Enhanced token parsing might be slower
   - **Mitigation**: Implement caching, optimize JSONL parsing
2. **Breaking Changes**: Components expecting estimated tokens get 0
   - **Mitigation**: Gradual rollout, extensive testing
3. **API Dependency**: Enhanced methods depend on Anthropic count-tokens API
   - **Mitigation**: Graceful degradation, JSONL-first approach

### Medium Risk Issues
1. **Data Migration**: Existing cached results become invalid
   - **Mitigation**: Clear caches, regenerate with accurate methods
2. **Testing Coverage**: Need comprehensive test coverage
   - **Mitigation**: Create extensive test suite before implementation

## Implementation Timeline

### Week 1: Critical Fixes
- **Day 1-2**: Fix enhanced_token_counter.py legacy fallback
- **Day 3-4**: Fix context_window_analyzer.py file size estimation  
- **Day 5**: Fix dashboard total token calculation
- **Weekend**: Testing and validation

### Week 2: High Priority Components
- **Day 1-2**: Fix context health scorer
- **Day 3-4**: Fix bridge and migration services
- **Day 5**: Integration testing

### Week 3: Comprehensive Cleanup
- **Day 1-3**: Fix all remaining `// 4` patterns
- **Day 4-5**: Fix all remaining `* 1.3` patterns

### Week 4: Architectural Consolidation
- **Day 1-2**: Implement unified token calculator
- **Day 3-4**: Migration and deprecation warnings
- **Day 5**: Final validation and documentation

## Monitoring and Validation

### Real-time Monitoring
```python
# Add to enhanced token counter
class TokenCalculationMonitor:
    def log_calculation_method(self, method: str, tokens: int, source: str):
        """Track which calculation methods are being used."""
        metrics = {
            'timestamp': datetime.now(),
            'method': method,  # 'jsonl_data', 'count_tokens_api', 'legacy_fallback', 'zero_return'
            'tokens': tokens,
            'source': source
        }
        # Log to monitoring system
```

### Validation Dashboard
- **Token Calculation Health**: Show % using enhanced vs. legacy methods
- **Accuracy Metrics**: Compare with ccusage baselines
- **Performance Impact**: Track calculation times
- **Error Rates**: Monitor failures and fallbacks

## Conclusion

This implementation plan addresses the **critical architectural flaw** where enhanced token counting infrastructure exists but is undermined by widespread legacy estimation methods. The most shocking discovery is that the "enhanced" token counter itself contains legacy fallback code.

**The key insight**: Fix the enhanced system first by removing all crude estimation fallbacks, then systematically migrate all components to use only the enhanced pathway. This ensures the accuracy improvements actually reach all parts of the application.

**Expected Outcome**: 
- ✅ 100% accurate token counting matching ccusage standards
- ✅ Consistent token displays across all dashboard widgets  
- ✅ No more "Context Window Usage by Directory" inaccuracy issues
- ✅ Complete elimination of crude `// 4` and `* 1.3` estimation methods

This plan transforms the context-cleaner from a mixed-accuracy system to a consistently accurate token analysis platform.