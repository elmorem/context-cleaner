# PR19 Test Suite Documentation
## Optimization Modes & Interactive Workflow Testing

This document describes the comprehensive test suite created for PR19: Optimization Modes & Interactive Workflow. The test suite validates all components of the interactive optimization system and ensures proper integration with existing components.

---

## 📋 Test Suite Overview

### Test Coverage Areas

1. **Interactive Workflow Management**
   - Session lifecycle and management
   - Strategy selection and execution
   - Plan generation and preview
   - User approval and change selection

2. **Change Approval System**
   - Selective approval workflows
   - Category-based batch operations
   - User preference learning
   - Change categorization and feedback

3. **CLI Integration**
   - All optimization command modes
   - Error handling and user feedback
   - Integration with workflow components
   - Output formatting (text/JSON)

4. **End-to-End Workflows**
   - Complete optimization pipelines
   - Component integration testing
   - Performance and scalability
   - Backward compatibility

---

## 🗃️ Test Structure

### Unit Tests

#### `tests/optimization/test_interactive_workflow.py`
- **TestInteractiveSession**: Session data class validation
- **TestInteractiveWorkflowManager**: Core workflow management functionality
- **TestConvenienceFunctions**: Helper function testing
- **TestWorkflowSteps**: Enum and state management
- **TestErrorHandling**: Exception handling and recovery
- **TestPerformance**: Concurrent sessions and large datasets

**Key Test Scenarios:**
- Session creation and lifecycle management
- Strategy recommendation based on context
- Plan generation for different strategies (Conservative, Balanced, Aggressive, Focus)
- Preview generation and user confirmation workflows
- Selective change application and full plan execution
- Error handling and session cleanup

#### `tests/optimization/test_change_approval.py`
- **TestChangeSelection**: Individual change selection
- **TestChangeApprovalSystem**: Complete approval workflow
- **TestConvenienceFunctions**: Quick approval helpers
- **TestPerformanceAndScalability**: Large operation sets

**Key Test Scenarios:**
- Operation categorization (Removal, Consolidation, Reordering, Summarization, Safety)
- Individual and batch approval decisions
- User preference learning and auto-approval
- Approval session management and data export
- Performance with large numbers of operations

#### `tests/cli/test_optimization_commands.py`
- **TestOptimizationCommandHandler**: Core handler functionality
- **TestDashboardCommand**: Context health dashboard integration
- **TestQuickOptimization**: Fast optimization with safe defaults
- **TestPreviewMode**: Change preview without execution
- **TestAggressiveOptimization**: Maximum optimization with confirmation
- **TestFocusMode**: Priority reordering without content removal
- **TestFullOptimization**: Complete interactive workflow

**Key Test Scenarios:**
- All CLI command modes (--quick, --preview, --aggressive, --focus, --dashboard)
- Verbose and quiet output modes
- JSON and text output formatting
- Error handling and user feedback
- Integration with workflow components

### Integration Tests

#### `tests/integration/test_pr19_optimization_workflow.py`
- **TestCompleteOptimizationWorkflow**: End-to-end workflow validation
- **TestCLIIntegration**: CLI command integration with real components
- **TestAdvancedIntegrationScenarios**: Complex scenarios and edge cases
- **TestPerformanceIntegration**: Performance with realistic data
- **TestBackwardCompatibility**: Integration with existing systems

**Key Test Scenarios:**
- Complete workflows for all strategy types
- CLI integration through click testing
- Concurrent session handling
- Large context data processing
- Error propagation and recovery
- Integration with PR17 (ManipulationEngine) and PR18 (Safety Framework)

---

## 🚀 Test Execution

### Test Runner

The custom test runner `tests/run_pr19_tests.py` provides:

```bash
# Run all tests
python tests/run_pr19_tests.py

# Run with coverage
python tests/run_pr19_tests.py --coverage

# Run only unit tests (fast)
python tests/run_pr19_tests.py --category unit

# Run with verbose output
python tests/run_pr19_tests.py --verbose

# Quick validation
python tests/run_pr19_tests.py --smoke-only
```

### Test Categories

- **Validation**: Component import and instantiation
- **Smoke Tests**: Basic functionality verification
- **Unit Tests**: Individual component testing
- **Integration Tests**: Complete workflow testing
- **Performance Tests**: Scalability and efficiency

---

## 📊 Test Results Summary

### Current Status
- ✅ **Installation Validation**: All components import successfully
- ✅ **Smoke Tests**: Basic functionality works
- ⚠️ **Unit Tests**: 53 passed, 19 failed, 9 errors (needs fixture fixes)
- ⏭️ **Integration Tests**: Requires unit test fixes first

### Known Issues
1. **Fixture Dependencies**: Some test fixtures need to be defined in test files
2. **Enum Import Issues**: WorkflowStep and UserAction enums need proper imports
3. **Mock Signature Issues**: Function call signatures need alignment with implementation

### Recommended Fixes
1. Add missing fixture definitions in test classes
2. Import required enums in test modules
3. Update mock function calls to match actual implementations
4. Fix attribute name mismatches (sessions → active_sessions)

---

## 🧪 Test Examples

### Basic Workflow Test
```python
def test_complete_optimization_workflow():
    manager = InteractiveWorkflowManager()
    
    # Start session
    session = manager.start_interactive_optimization(
        context_data, StrategyType.BALANCED
    )
    
    # Generate plan
    plan = manager.generate_optimization_plan(session.session_id)
    
    # Generate preview
    preview = manager.generate_preview(session.session_id)
    
    # Execute with approval
    result = manager.execute_full_plan(session.session_id)
    
    assert result.success is True
```

### CLI Integration Test
```python
def test_cli_preview_command():
    runner = CliRunner()
    result = runner.invoke(main, ['optimize', '--preview'])
    
    assert result.exit_code == 0
    assert "📋 Optimization Preview" in result.output
```

### Change Approval Test
```python
def test_selective_approval():
    approval_system = ChangeApprovalSystem()
    approval_id = approval_system.create_approval_session(plan)
    
    # Make selective choices
    approval_system.select_operation(
        approval_id, "op-001", ApprovalDecision.APPROVE
    )
    
    selected = approval_system.get_selected_operations(approval_id)
    assert "op-001" in selected
```

---

## 🔧 Maintenance

### Adding New Tests
1. Follow existing test structure and naming conventions
2. Use appropriate fixtures from `conftest.py`
3. Include both positive and negative test cases
4. Add performance tests for scalable components
5. Update test documentation

### Test Data Management
- Use realistic context data in tests
- Mock external dependencies consistently
- Provide both small and large datasets for performance testing
- Include edge cases and error scenarios

### Continuous Integration
- All tests should pass before merging
- Coverage reports help identify untested code paths
- Performance benchmarks ensure scalability
- Integration tests validate component interactions

---

## 📚 Related Documentation

- [PR19 Implementation README](../src/context_cleaner/optimization/README.md)
- [Development Roadmap](../DEVELOPMENT_ROADMAP.md)
- [CLI Usage Guide](../docs/CLI_USAGE.md)
- [Architecture Documentation](../docs/ARCHITECTURE.md)

---

## 🏆 Testing Best Practices

### What We Test
- ✅ All public API methods and functions
- ✅ Error handling and edge cases
- ✅ Integration between components
- ✅ Performance with realistic data sizes
- ✅ CLI user experience and error messages
- ✅ Backward compatibility with existing features

### What We Mock
- External dependencies (manipulation engine, safety validator)
- File system operations
- Network requests
- Time-dependent operations
- User input (for CLI tests)

### Test Quality Metrics
- **Code Coverage**: Aim for >90% on new components
- **Test Performance**: Unit tests <100ms, integration tests <2s
- **Test Reliability**: No flaky tests, consistent results
- **Test Maintainability**: Clear naming, good documentation, minimal duplication

---

*This test suite ensures the reliability, performance, and usability of PR19 Optimization Modes & Interactive Workflow components.*