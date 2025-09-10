#!/usr/bin/env python3
"""
Test script for the System Diagnostics and Recovery service.
This will demonstrate comprehensive system analysis and automated recovery.
"""

import asyncio
import sys
import json
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.context_cleaner.services.system_diagnostics_and_recovery import (
    SystemDiagnosticsAndRecovery,
    DiagnosticLevel,
    RecoveryAction
)


def print_diagnostic_results(results):
    """Pretty print diagnostic results"""
    
    # Group by level
    by_level = {}
    for result in results:
        level = result.level.value
        if level not in by_level:
            by_level[level] = []
        by_level[level].append(result)
    
    # Print by level with appropriate icons
    level_icons = {
        "critical": "🚨",
        "error": "❌", 
        "warning": "⚠️",
        "info": "ℹ️"
    }
    
    for level in ["critical", "error", "warning", "info"]:
        if level in by_level:
            print(f"\n{level_icons[level]} {level.upper()} ({len(by_level[level])} issues)")
            print("=" * 50)
            
            for result in by_level[level]:
                print(f"Component: {result.component}")
                print(f"Message: {result.message}")
                
                if result.details:
                    print("Details:")
                    for key, value in result.details.items():
                        if isinstance(value, (dict, list)):
                            print(f"  {key}: {json.dumps(value, indent=2)[:200]}...")
                        else:
                            print(f"  {key}: {value}")
                
                if result.recovery_actions:
                    actions = [action.value for action in result.recovery_actions]
                    print(f"Recovery Actions: {', '.join(actions)}")
                
                print()


def print_recovery_attempts(attempts):
    """Pretty print recovery attempts"""
    
    if not attempts:
        print("No recovery attempts made.")
        return
    
    print(f"\n🔧 RECOVERY ATTEMPTS ({len(attempts)} total)")
    print("=" * 50)
    
    for attempt in attempts:
        status_icon = "✅" if attempt.success else "❌"
        print(f"{status_icon} {attempt.action.value} -> {attempt.component}")
        print(f"   Duration: {attempt.duration:.2f}s")
        print(f"   Timestamp: {attempt.timestamp}")
        
        if not attempt.success and attempt.error_message:
            print(f"   Error: {attempt.error_message}")
        
        print()


async def run_comprehensive_test():
    """Run comprehensive system diagnostic and recovery test"""
    
    print("🔍 SYSTEM DIAGNOSTICS AND RECOVERY TEST")
    print("=" * 60)
    
    # Initialize the diagnostic system
    diagnostic_system = SystemDiagnosticsAndRecovery()
    
    print("🧪 Running full system diagnostic...")
    
    # Run comprehensive diagnostics
    results = await diagnostic_system.run_full_system_diagnostic()
    
    print(f"✅ Diagnostic completed! Found {len(results)} results.")
    
    # Display results
    print_diagnostic_results(results)
    
    # Check if recovery is needed
    issues_needing_recovery = [r for r in results if r.recovery_actions and r.level in [DiagnosticLevel.CRITICAL, DiagnosticLevel.ERROR]]
    
    if issues_needing_recovery:
        print(f"\n🚑 ATTEMPTING AUTOMATED RECOVERY")
        print(f"Found {len(issues_needing_recovery)} issues requiring recovery")
        print("=" * 60)
        
        # Attempt recovery
        recovery_attempts = await diagnostic_system.attempt_recovery(results)
        
        # Display recovery results
        print_recovery_attempts(recovery_attempts)
        
        # Check if recovery was successful by running diagnostics again
        print("\n🔄 Re-running diagnostics to check recovery success...")
        post_recovery_results = await diagnostic_system.run_full_system_diagnostic()
        
        # Compare before/after
        pre_critical = len([r for r in results if r.level == DiagnosticLevel.CRITICAL])
        post_critical = len([r for r in post_recovery_results if r.level == DiagnosticLevel.CRITICAL])
        
        pre_error = len([r for r in results if r.level == DiagnosticLevel.ERROR])
        post_error = len([r for r in post_recovery_results if r.level == DiagnosticLevel.ERROR])
        
        print(f"\n📊 RECOVERY EFFECTIVENESS")
        print("=" * 30)
        print(f"Critical Issues: {pre_critical} → {post_critical} ({'✅ IMPROVED' if post_critical < pre_critical else '❌ NO CHANGE'})")
        print(f"Error Issues: {pre_error} → {post_error} ({'✅ IMPROVED' if post_error < pre_error else '❌ NO CHANGE'})")
        
    else:
        print("\n✅ No issues requiring automated recovery found.")
    
    # Get system health summary
    print(f"\n📋 SYSTEM HEALTH SUMMARY")
    print("=" * 30)
    
    health_summary = diagnostic_system.get_system_health_summary()
    print(json.dumps(health_summary, indent=2))
    
    return results, diagnostic_system


async def run_targeted_diagnostic_test():
    """Run targeted tests for known issues"""
    
    print("\n🎯 TARGETED DIAGNOSTIC TEST")
    print("=" * 40)
    
    diagnostic_system = SystemDiagnosticsAndRecovery()
    
    # Test specific components we know have issues
    print("Testing specific components with known issues...")
    
    # Test schema issues
    schema_results = await diagnostic_system._diagnose_schema_integrity()
    print(f"\n🗄️ Schema Integrity: {len(schema_results)} results")
    for result in schema_results:
        status_icon = "❌" if result.level in [DiagnosticLevel.CRITICAL, DiagnosticLevel.ERROR] else "✅"
        print(f"  {status_icon} {result.message}")
    
    # Test API health
    api_results = await diagnostic_system._diagnose_api_health()
    print(f"\n🌐 API Health: {len(api_results)} results")
    for result in api_results:
        if "working" in result.message.lower():
            print(f"  ✅ {result.message}")
        elif result.level == DiagnosticLevel.ERROR:
            print(f"  ❌ {result.message}")
        elif result.level == DiagnosticLevel.WARNING:
            print(f"  ⚠️ {result.message}")
        else:
            print(f"  ℹ️ {result.message}")
    
    # Test process health
    process_results = await diagnostic_system._diagnose_process_health()
    print(f"\n⚙️ Process Health: {len(process_results)} results")
    for result in process_results:
        if result.level == DiagnosticLevel.WARNING and "too many" in result.message.lower():
            print(f"  ⚠️ {result.message}")
            if result.details and 'processes' in result.details:
                print(f"     Found {len(result.details['processes'])} processes")
        else:
            status_icon = "✅" if result.level == DiagnosticLevel.INFO else "❌"
            print(f"  {status_icon} {result.message}")
    
    return schema_results + api_results + process_results


if __name__ == "__main__":
    print("🚀 Starting System Diagnostics and Recovery Test Suite")
    print("This will comprehensively analyze the system and attempt automated recovery")
    print()
    
    try:
        # Run comprehensive test
        results, diagnostic_system = asyncio.run(run_comprehensive_test())
        
        # Run targeted test
        targeted_results = asyncio.run(run_targeted_diagnostic_test())
        
        print(f"\n🎉 TEST SUITE COMPLETED")
        print("=" * 30)
        print(f"Total Diagnostics: {len(results)}")
        print(f"Targeted Tests: {len(targeted_results)}")
        print(f"Critical Issues: {len([r for r in results if r.level == DiagnosticLevel.CRITICAL])}")
        print(f"Error Issues: {len([r for r in results if r.level == DiagnosticLevel.ERROR])}")
        print(f"Warning Issues: {len([r for r in results if r.level == DiagnosticLevel.WARNING])}")
        
        # Summary of what we found
        print(f"\n🔍 KEY FINDINGS")
        print("=" * 20)
        
        critical_issues = [r for r in results if r.level == DiagnosticLevel.CRITICAL]
        if critical_issues:
            print("Critical Issues Found:")
            for issue in critical_issues:
                print(f"  - {issue.component}: {issue.message}")
        
        error_issues = [r for r in results if r.level == DiagnosticLevel.ERROR]
        if error_issues:
            print("Error Issues Found:")
            for issue in error_issues[:5]:  # Show first 5
                print(f"  - {issue.component}: {issue.message}")
                
        print("\n✅ System diagnostic and recovery test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)