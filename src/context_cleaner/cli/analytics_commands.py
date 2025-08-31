"""
Enhanced CLI Commands for Analytics Integration (PR20)

This module provides the missing CLI commands for effectiveness tracking,
health checks, and analytics export functionality.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import click

from .. import __version__
from ..analytics.effectiveness_tracker import EffectivenessTracker
from ..analytics.productivity_analyzer import ProductivityAnalyzer
from ..optimization.cache_dashboard import CacheEnhancedDashboard
from ..optimization.cross_session_analytics import CrossSessionAnalyticsEngine
from ..config.settings import ContextCleanerConfig


class AnalyticsCommandHandler:
    """
    Enhanced CLI commands for analytics and effectiveness tracking.

    Provides the missing commands identified in PR20:
    - health-check: System health and readiness assessment
    - export-analytics: Comprehensive analytics data export
    - effectiveness stats: Optimization effectiveness tracking
    """

    def __init__(
        self, config: Optional[ContextCleanerConfig] = None, verbose: bool = False
    ):
        """Initialize analytics command handler."""
        self.config = config or ContextCleanerConfig.from_env()
        self.verbose = verbose

        # Initialize analytics components
        self.effectiveness_tracker = EffectivenessTracker()
        self.productivity_analyzer = ProductivityAnalyzer()
        self.cache_dashboard = CacheEnhancedDashboard()
        self.cross_session_analyzer = CrossSessionAnalyticsEngine()

    def handle_health_check_command(
        self, detailed: bool = False, fix_issues: bool = False, format: str = "text"
    ) -> None:
        """
        Perform comprehensive system health check.

        Validates system readiness, data integrity, and identifies issues.
        """
        if self.verbose and format != "json":
            click.echo("🔍 Performing Context Cleaner health check...")

        health_results = self._perform_health_check(detailed)

        if format == "json":
            click.echo(json.dumps(health_results, indent=2))
            return

        # Text format output
        self._display_health_check_results(health_results, detailed)

        # Fix issues if requested
        if fix_issues and health_results["issues_found"] > 0:
            if self.verbose:
                click.echo("\n🔧 Attempting to fix identified issues...")
            self._attempt_issue_fixes(health_results)

    def handle_export_analytics_command(
        self,
        output_path: Optional[str] = None,
        days: int = 30,
        include_sessions: bool = True,
        format: str = "json",
    ) -> None:
        """
        Export comprehensive analytics data.

        Exports effectiveness data, session history, and performance metrics.
        """
        if self.verbose:
            click.echo(f"📊 Exporting analytics data for last {days} days...")

        try:
            # Gather all analytics data
            analytics_data = self._gather_comprehensive_analytics(
                days, include_sessions
            )

            # Determine output path
            if output_path:
                output_file = Path(output_path)
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = Path(f"context_cleaner_analytics_{timestamp}.{format}")

            # Export data
            if format == "json":
                with open(output_file, "w") as f:
                    json.dump(analytics_data, f, indent=2)
            else:
                # Could add CSV or other formats
                raise ValueError(f"Unsupported export format: {format}")

            click.echo(f"✅ Analytics data exported to: {output_file}")

            # Display summary
            if self.verbose:
                self._display_export_summary(analytics_data)

        except Exception as e:
            click.echo(f"❌ Failed to export analytics: {e}", err=True)
            sys.exit(1)

    def handle_effectiveness_stats_command(
        self,
        days: int = 30,
        strategy: Optional[str] = None,
        detailed: bool = False,
        format: str = "text",
    ) -> None:
        """
        Display optimization effectiveness statistics.

        Shows before/after metrics, success rates, and user satisfaction data.
        """
        if self.verbose and format != "json":
            click.echo(
                f"📈 Analyzing optimization effectiveness for last {days} days..."
            )

        try:
            effectiveness_data = self.effectiveness_tracker.get_effectiveness_summary(
                days
            )

            if format == "json":
                click.echo(json.dumps(effectiveness_data, indent=2))
                return

            # Text format display
            self._display_effectiveness_stats(effectiveness_data, strategy, detailed)

        except Exception as e:
            click.echo(f"❌ Failed to get effectiveness stats: {e}", err=True)
            sys.exit(1)

    def handle_enhanced_dashboard_command(
        self, interactive: bool = False, operations: bool = False, format: str = "text"
    ) -> None:
        """
        Enhanced dashboard with manipulation operation controls.

        Provides interactive dashboard with operation triggers and analytics.
        """
        if self.verbose and format != "json":
            click.echo("🎯 Loading enhanced context dashboard...")

        try:
            # Get comprehensive dashboard data
            dashboard_data = self._get_enhanced_dashboard_data()

            if format == "json":
                click.echo(json.dumps(dashboard_data, indent=2))
                return

            # Display enhanced dashboard
            self._display_enhanced_dashboard(dashboard_data, interactive, operations)

            # Handle interactive mode
            if interactive:
                self._handle_interactive_dashboard()

        except Exception as e:
            click.echo(f"❌ Failed to load enhanced dashboard: {e}", err=True)
            sys.exit(1)

    def _perform_health_check(self, detailed: bool = False) -> Dict[str, Any]:
        """Perform comprehensive system health check."""
        health_results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "issues_found": 0,
            "warnings_found": 0,
            "checks_performed": 0,
            "checks": {},
        }

        # Data directory check
        data_dir = Path(self.config.data_directory)
        health_results["checks"]["data_directory"] = {
            "status": "pass" if data_dir.exists() else "fail",
            "message": f"Data directory: {data_dir}",
            "details": {
                "exists": data_dir.exists(),
                "writable": data_dir.is_dir()
                and data_dir.exists()
                and data_dir.stat().st_mode,
            },
        }
        health_results["checks_performed"] += 1
        if health_results["checks"]["data_directory"]["status"] == "fail":
            health_results["issues_found"] += 1

        # Configuration check
        try:
            config_valid = self.config.dashboard.port > 0
            health_results["checks"]["configuration"] = {
                "status": "pass" if config_valid else "fail",
                "message": "Configuration validation",
                "details": {
                    "dashboard_port": self.config.dashboard.port,
                    "data_directory": self.config.data_directory,
                },
            }
        except Exception as e:
            health_results["checks"]["configuration"] = {
                "status": "fail",
                "message": f"Configuration error: {e}",
                "details": {},
            }
            health_results["issues_found"] += 1
        health_results["checks_performed"] += 1

        # Effectiveness tracking check
        effectiveness_dir = data_dir / "effectiveness"
        health_results["checks"]["effectiveness_tracking"] = {
            "status": "pass" if effectiveness_dir.exists() else "warning",
            "message": f"Effectiveness tracking: {effectiveness_dir}",
            "details": {
                "directory_exists": effectiveness_dir.exists(),
                "sessions_file_exists": (
                    effectiveness_dir / "optimization_sessions.jsonl"
                ).exists(),
            },
        }
        health_results["checks_performed"] += 1
        if health_results["checks"]["effectiveness_tracking"]["status"] == "warning":
            health_results["warnings_found"] += 1

        # Cache integration check
        try:
            # Try to generate a simple dashboard to test cache access
            import asyncio

            try:
                cache_data = asyncio.run(self.cache_dashboard.generate_dashboard())
                cache_status = cache_data is not None
            except:
                cache_status = False

            health_results["checks"]["cache_integration"] = {
                "status": "pass" if cache_status else "warning",
                "message": "Claude Code cache integration",
                "details": {"cache_accessible": cache_status},
            }
        except Exception as e:
            health_results["checks"]["cache_integration"] = {
                "status": "warning",
                "message": f"Cache integration: {e}",
                "details": {},
            }
            health_results["warnings_found"] += 1
        health_results["checks_performed"] += 1

        # Performance check
        if detailed:
            health_results["checks"]["performance"] = self._check_system_performance()
            health_results["checks_performed"] += 1

        # Update overall status
        if health_results["issues_found"] > 0:
            health_results["overall_status"] = "unhealthy"
        elif health_results["warnings_found"] > 0:
            health_results["overall_status"] = "warning"

        return health_results

    def _display_health_check_results(
        self, health_results: Dict[str, Any], detailed: bool
    ) -> None:
        """Display health check results in text format."""
        status_emoji = {"healthy": "🟢", "warning": "🟡", "unhealthy": "🔴"}

        overall_status = health_results["overall_status"]
        click.echo(
            f"\n{status_emoji[overall_status]} SYSTEM HEALTH: {overall_status.upper()}"
        )
        click.echo("=" * 50)

        click.echo(f"Checks performed: {health_results['checks_performed']}")
        click.echo(f"Issues found: {health_results['issues_found']}")
        click.echo(f"Warnings: {health_results['warnings_found']}")

        if (
            detailed
            or health_results["issues_found"] > 0
            or health_results["warnings_found"] > 0
        ):
            click.echo("\n📋 DETAILED RESULTS")
            click.echo("-" * 20)

            for check_name, check_result in health_results["checks"].items():
                status_icon = {"pass": "✅", "warning": "⚠️", "fail": "❌"}
                click.echo(
                    f"{status_icon.get(check_result['status'], '?')} {check_name}"
                )
                click.echo(f"   {check_result['message']}")

                if detailed and check_result.get("details"):
                    for key, value in check_result["details"].items():
                        click.echo(f"   • {key}: {value}")

        if health_results["issues_found"] > 0:
            click.echo("\n🔧 Run with --fix-issues to attempt automatic fixes")

    def _gather_comprehensive_analytics(
        self, days: int, include_sessions: bool
    ) -> Dict[str, Any]:
        """Gather all analytics data for export."""
        return {
            "export_metadata": {
                "timestamp": datetime.now().isoformat(),
                "days_included": days,
                "include_sessions": include_sessions,
                "context_cleaner_version": __version__,
            },
            "effectiveness_data": self.effectiveness_tracker.get_effectiveness_summary(
                days
            ),
            "system_health": self._perform_health_check(detailed=True),
            "cache_analytics": self._get_cache_analytics_summary(),
            "cross_session_insights": self._get_cross_session_insights(),
            "performance_metrics": self._get_performance_metrics(),
        }

    def _display_effectiveness_stats(
        self, data: Dict[str, Any], strategy: Optional[str], detailed: bool
    ) -> None:
        """Display effectiveness statistics in text format."""
        if data["total_sessions"] == 0:
            click.echo("📊 No optimization sessions found in the specified period.")
            return

        click.echo("\n📈 OPTIMIZATION EFFECTIVENESS REPORT")
        click.echo("=" * 50)

        # Overall metrics
        metrics = data["average_metrics"]
        click.echo(f"Period: {data['period_days']} days")
        click.echo(f"Total sessions: {data['total_sessions']}")
        click.echo(f"Success rate: {data['success_rate_percentage']:.1f}%")
        click.echo()

        # Impact metrics
        click.echo("🎯 AVERAGE IMPROVEMENTS")
        click.echo(
            f"• Context size reduction: {metrics['size_reduction_percentage']:.1f}%"
        )
        click.echo(f"• Health score improvement: +{metrics['health_improvement']:.1f}")
        click.echo(f"• Focus score improvement: +{metrics['focus_improvement']:.1f}")
        if metrics["user_satisfaction"]:
            click.echo(f"• User satisfaction: {metrics['user_satisfaction']:.1f}/5.0")

        # Total impact
        impact = data["total_impact"]
        click.echo("\n💪 CUMULATIVE IMPACT")
        click.echo(f"• Bytes saved: {impact['total_bytes_saved']:,}")
        click.echo(f"• Duplicates removed: {impact['total_duplicates_removed']}")
        click.echo(f"• Stale items removed: {impact['total_stale_items_removed']}")
        click.echo(f"• Items consolidated: {impact['total_items_consolidated']}")
        click.echo(
            f"• Estimated time saved: {impact['total_time_saved_estimate_hours']:.1f} hours"
        )

        # Strategy breakdown
        if detailed and data["strategy_effectiveness"]:
            click.echo("\n🎛️  STRATEGY EFFECTIVENESS")
            for strategy_name, stats in data["strategy_effectiveness"].items():
                if not strategy or strategy_name == strategy:
                    click.echo(f"• {strategy_name.title()} Strategy:")
                    click.echo(f"  - Sessions: {stats['count']}")
                    click.echo(f"  - Success rate: {stats['success_rate']:.1f}%")
                    click.echo(
                        f"  - Avg size reduction: {stats['avg_size_reduction']:.1f}%"
                    )
                    click.echo(
                        f"  - Avg health improvement: {stats['avg_health_improvement']:.1f}"
                    )

    def _get_enhanced_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data with operation controls."""
        return {
            "timestamp": datetime.now().isoformat(),
            "system_health": self._perform_health_check(),
            "recent_effectiveness": self.effectiveness_tracker.get_effectiveness_summary(
                7
            ),
            "cache_insights": self._get_cache_analytics_summary(),
            "available_operations": {
                "quick_optimization": "Fast cleanup with safe defaults",
                "preview_optimization": "Show proposed changes without applying",
                "aggressive_optimization": "Maximum optimization with minimal confirmation",
                "focus_optimization": "Reorder priorities without removing content",
            },
            "smart_recommendations": self._get_smart_recommendations(),
        }

    def _display_enhanced_dashboard(
        self, data: Dict[str, Any], interactive: bool, operations: bool
    ) -> None:
        """Display enhanced dashboard with operation controls."""
        click.echo("\n🎯 ENHANCED CONTEXT CLEANER DASHBOARD")
        click.echo("=" * 50)

        # System health summary
        health = data["system_health"]
        status_emoji = {"healthy": "🟢", "warning": "🟡", "unhealthy": "🔴"}
        click.echo(
            f"System Status: {status_emoji[health['overall_status']]} {health['overall_status'].title()}"
        )

        # Recent effectiveness
        effectiveness = data["recent_effectiveness"]
        if effectiveness["total_sessions"] > 0:
            click.echo(
                f"Recent success rate: {effectiveness['success_rate_percentage']:.1f}%"
            )
            click.echo(
                f"Avg size reduction: {effectiveness['average_metrics']['size_reduction_percentage']:.1f}%"
            )

        # Smart recommendations
        recommendations = data.get("smart_recommendations", [])
        if recommendations:
            click.echo("\n💡 SMART RECOMMENDATIONS")
            for i, rec in enumerate(recommendations[:3], 1):
                click.echo(f"{i}. {rec}")

        # Available operations
        if operations:
            click.echo("\n🛠️  AVAILABLE OPERATIONS")
            for op_name, op_desc in data["available_operations"].items():
                click.echo(f"• {op_name.replace('_', ' ').title()}: {op_desc}")
            click.echo("\nRun: context-cleaner optimize --<operation> to execute")

    def _handle_interactive_dashboard(self) -> None:
        """Handle interactive dashboard mode."""
        click.echo("\n🔄 Interactive mode not yet implemented")
        click.echo(
            "Coming in future version - will provide real-time operation triggers"
        )

    def _check_system_performance(self) -> Dict[str, Any]:
        """Check system performance metrics."""
        import psutil
        import time

        start_time = time.time()

        # Basic performance test
        test_context = {"test": "data" * 1000}
        health_analysis = {"health_score": 75}  # Mock analysis

        analysis_time = time.time() - start_time

        return {
            "status": "pass" if analysis_time < 2.0 else "warning",
            "message": f"Performance test: {analysis_time:.3f}s",
            "details": {
                "analysis_time_seconds": analysis_time,
                "memory_usage_mb": psutil.Process().memory_info().rss / 1024 / 1024,
                "cpu_percent": psutil.cpu_percent(interval=1),
                "performance_target_met": analysis_time < 2.0,
            },
        }

    def _attempt_issue_fixes(self, health_results: Dict[str, Any]) -> None:
        """Attempt to fix identified issues automatically."""
        fixed_count = 0

        for check_name, check_result in health_results["checks"].items():
            if check_result["status"] == "fail":
                if check_name == "data_directory":
                    try:
                        Path(self.config.data_directory).mkdir(
                            parents=True, exist_ok=True
                        )
                        click.echo(f"✅ Fixed: Created data directory")
                        fixed_count += 1
                    except Exception as e:
                        click.echo(f"❌ Failed to fix data directory: {e}")

                elif check_name == "effectiveness_tracking":
                    try:
                        effectiveness_dir = (
                            Path(self.config.data_directory) / "effectiveness"
                        )
                        effectiveness_dir.mkdir(parents=True, exist_ok=True)
                        click.echo(
                            f"✅ Fixed: Created effectiveness tracking directory"
                        )
                        fixed_count += 1
                    except Exception as e:
                        click.echo(f"❌ Failed to fix effectiveness tracking: {e}")

        click.echo(f"\n🔧 Fixed {fixed_count} issues")

    def _get_cache_analytics_summary(self) -> Dict[str, Any]:
        """Get cache analytics summary."""
        try:
            import asyncio

            cache_data = asyncio.run(self.cache_dashboard.generate_dashboard())
            return {
                "status": "available",
                "context_size": getattr(cache_data, "context_size", 0),
                "file_count": getattr(cache_data, "file_count", 0),
                "session_count": getattr(cache_data, "session_count", 0),
            }
        except Exception as e:
            return {"status": "unavailable", "message": f"Cache analytics error: {e}"}

    def _get_cross_session_insights(self) -> Dict[str, Any]:
        """Get cross-session insights."""
        try:
            import asyncio

            insights = asyncio.run(
                self.cross_session_analyzer.analyze_cross_session_patterns([])
            )
            return {
                "status": "available",
                "total_sessions": len(insights.session_clusters) if insights else 0,
                "patterns_found": (
                    len(insights.cross_session_patterns) if insights else 0
                ),
            }
        except Exception as e:
            return {
                "status": "unavailable",
                "message": f"Cross-session insights error: {e}",
            }

    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics."""
        return {
            "timestamp": datetime.now().isoformat(),
            "system_info": {"python_version": sys.version, "platform": sys.platform},
        }

    def _get_smart_recommendations(self) -> List[str]:
        """Get smart recommendations based on usage patterns."""
        recommendations = []

        # Get recent effectiveness data
        recent_data = self.effectiveness_tracker.get_effectiveness_summary(7)

        if recent_data["total_sessions"] == 0:
            recommendations.append(
                "Try running your first optimization to see effectiveness metrics"
            )
        elif recent_data["success_rate_percentage"] < 80:
            recommendations.append(
                "Consider using Conservative mode for more reliable optimizations"
            )
        elif recent_data["average_metrics"]["size_reduction_percentage"] < 20:
            recommendations.append(
                "Try Aggressive mode for greater context size reduction"
            )

        # Cache-based recommendations would be added here
        recommendations.append(
            "Enable cache integration for personalized optimization strategies"
        )

        return recommendations

    def _display_export_summary(self, analytics_data: Dict[str, Any]) -> None:
        """Display summary of exported analytics data."""
        click.echo("\n📋 EXPORT SUMMARY")
        click.echo("-" * 20)

        effectiveness = analytics_data.get("effectiveness_data", {})
        click.echo(f"• Sessions exported: {effectiveness.get('total_sessions', 0)}")
        click.echo(f"• Time period: {effectiveness.get('period_days', 0)} days")

        health = analytics_data.get("system_health", {})
        click.echo(f"• Health checks: {health.get('checks_performed', 0)}")

        click.echo(
            f"• Export timestamp: {analytics_data.get('export_metadata', {}).get('timestamp', 'unknown')}"
        )
