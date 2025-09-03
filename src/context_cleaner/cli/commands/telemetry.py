"""CLI commands for telemetry features."""

import asyncio
import click
import sys
from typing import Optional
import logging

from ...telemetry import ClickHouseClient, ErrorRecoveryManager, CostOptimizationEngine
from ...telemetry.cost_optimization.models import BudgetConfig

logger = logging.getLogger(__name__)


def get_current_session_id() -> str:
    """Get the current Claude Code session ID."""
    # This would need to integrate with the actual Claude Code system
    # For now, return a placeholder
    return "current-session-placeholder"


async def get_telemetry_client() -> ClickHouseClient:
    """Get configured telemetry client."""
    client = ClickHouseClient()
    
    # Check if telemetry system is available
    if not await client.health_check():
        raise click.ClickException(
            "Telemetry system is not available. Please ensure the telemetry infrastructure is running:\n"
            "  docker compose ps\n"
            "  ./install-telemetry.sh"
        )
    
    return client


@click.group()
def telemetry():
    """Telemetry and cost optimization commands."""
    pass


@telemetry.command()
@click.option('--session-id', help='Session ID (defaults to current session)')
@click.option('--hours', default=24, help='Hours of error history to analyze')
def error_analyze(session_id: Optional[str], hours: int):
    """Analyze recent errors and get recovery recommendations."""
    async def _analyze():
        try:
            client = await get_telemetry_client()
            recovery_manager = ErrorRecoveryManager(client)
            
            # Get error statistics
            stats = await recovery_manager.get_recovery_statistics()
            
            click.echo(f"\n📊 Error Analysis (Last {hours} hours)")
            click.echo("=" * 50)
            
            if stats.get("total_errors", 0) == 0:
                click.echo("✅ No errors detected in the specified time period")
                return
            
            click.echo(f"Total Errors: {stats['total_errors']}")
            click.echo(f"Error Rate: {stats.get('error_rate', 0):.2f} errors/hour")
            
            if stats.get("most_common_error"):
                click.echo(f"Most Common: {stats['most_common_error']}")
            
            click.echo(f"\n📋 Error Types:")
            for error_type, details in stats.get("error_types", {}).items():
                click.echo(f"  • {error_type}:")
                click.echo(f"    Count: {details['count']}")
                click.echo(f"    Avg Duration: {details['avg_duration_ms']:.0f}ms")
                click.echo(f"    Models Affected: {', '.join(details['models_affected'])}")
            
            # Get optimization suggestions
            if session_id:
                suggestions = await recovery_manager.suggest_optimizations(session_id)
                if suggestions:
                    click.echo(f"\n💡 Optimization Suggestions:")
                    for suggestion in suggestions:
                        priority_icon = {"high": "🔥", "medium": "⚠️", "low": "💡"}.get(suggestion["priority"], "•")
                        click.echo(f"  {priority_icon} {suggestion['message']}")
                        if suggestion.get("expected_savings"):
                            click.echo(f"    Expected Savings: {suggestion['expected_savings']}")
            
        except Exception as e:
            click.echo(f"❌ Error analysis failed: {e}", err=True)
            sys.exit(1)
    
    asyncio.run(_analyze())


@telemetry.command()
@click.option('--session-id', help='Session ID (defaults to current session)')
@click.option('--auto-optimize/--no-auto-optimize', default=True, 
              help='Enable automatic cost optimizations')
@click.option('--session-budget', type=float, default=2.0, 
              help='Session budget limit in USD')
@click.option('--daily-budget', type=float, default=5.0,
              help='Daily budget limit in USD')
def cost_optimize(session_id: Optional[str], auto_optimize: bool, 
                 session_budget: float, daily_budget: float):
    """Analyze costs and get optimization recommendations."""
    async def _optimize():
        try:
            if not session_id:
                session_id = get_current_session_id()
                
            client = await get_telemetry_client()
            
            budget_config = BudgetConfig(
                session_limit=session_budget,
                daily_limit=daily_budget,
                auto_switch_haiku=auto_optimize
            )
            
            optimizer = CostOptimizationEngine(client, budget_config)
            
            # Get session analysis
            analysis = await optimizer.get_session_analysis(session_id)
            
            click.echo(f"\n💰 Cost Analysis - Session {session_id}")
            click.echo("=" * 60)
            
            # Current costs
            click.echo(f"Session Cost:     ${analysis.session_cost:.3f}")
            click.echo(f"Daily Cost:       ${analysis.daily_cost:.3f}")
            click.echo(f"Weekly Cost:      ${analysis.weekly_cost:.3f}")
            
            # Budget status
            session_pct = (analysis.session_cost / session_budget) * 100
            daily_pct = (analysis.daily_cost / daily_budget) * 100
            
            session_status = "🟢" if session_pct < 50 else "🟡" if session_pct < 80 else "🔴"
            daily_status = "🟢" if daily_pct < 50 else "🟡" if daily_pct < 80 else "🔴"
            
            click.echo(f"\n📊 Budget Status:")
            click.echo(f"Session Budget:   {session_status} {session_pct:.1f}% of ${session_budget:.2f}")
            click.echo(f"Daily Budget:     {daily_status} {daily_pct:.1f}% of ${daily_budget:.2f}")
            
            if analysis.budget_remaining:
                click.echo(f"Remaining:        ${analysis.budget_remaining:.3f}")
            
            # Model breakdown
            click.echo(f"\n🤖 Model Usage:")
            click.echo(f"Sonnet Cost:      ${analysis.sonnet_cost:.3f}")
            click.echo(f"Haiku Cost:       ${analysis.haiku_cost:.3f}")
            
            # Efficiency metrics
            click.echo(f"\n📈 Efficiency:")
            click.echo(f"Cost per Token:   ${analysis.cost_per_token:.6f}")
            click.echo(f"Cost per Minute:  ${analysis.cost_per_minute:.3f}")
            
            # Projections
            if analysis.projected_daily_cost:
                click.echo(f"\n🔮 Projections:")
                click.echo(f"Projected Daily:  ${analysis.projected_daily_cost:.2f}")
            
            # Get optimization suggestions
            suggestions = await optimizer.get_optimization_suggestions(session_id)
            
            if suggestions:
                click.echo(f"\n💡 Optimization Suggestions:")
                for suggestion in suggestions:
                    priority_icon = {"critical": "🚨", "high": "🔥", "medium": "⚠️", "low": "💡"}.get(suggestion.priority, "•")
                    click.echo(f"  {priority_icon} {suggestion.title}")
                    click.echo(f"    {suggestion.description}")
                    
                    if suggestion.expected_savings_percent:
                        click.echo(f"    Expected Savings: {suggestion.expected_savings_percent:.0f}%")
                    
                    if suggestion.auto_applicable and auto_optimize:
                        click.echo(f"    ✅ Auto-optimization enabled")
                    
                    click.echo()
            
            # Comparison to averages
            if analysis.vs_daily_avg != 0:
                trend = "above" if analysis.vs_daily_avg > 0 else "below"
                click.echo(f"📊 Daily cost is {abs(analysis.vs_daily_avg):.1f}% {trend} average")
            
            if analysis.vs_session_avg != 0:
                trend = "above" if analysis.vs_session_avg > 0 else "below"
                click.echo(f"📊 Session cost is {abs(analysis.vs_session_avg):.1f}% {trend} average")
            
        except Exception as e:
            click.echo(f"❌ Cost optimization failed: {e}", err=True)
            sys.exit(1)
    
    asyncio.run(_optimize())


@telemetry.command()
@click.argument('task_description')
@click.option('--session-id', help='Session ID (defaults to current session)')
@click.option('--budget-aware/--ignore-budget', default=True,
              help='Consider current budget in recommendation')
def model_recommend(task_description: str, session_id: Optional[str], budget_aware: bool):
    """Get intelligent model recommendation for a task."""
    async def _recommend():
        try:
            if not session_id:
                session_id = get_current_session_id()
                
            client = await get_telemetry_client()
            optimizer = CostOptimizationEngine(client)
            
            recommendation = await optimizer.get_model_recommendation(task_description, session_id)
            
            click.echo(f"\n🤖 Model Recommendation")
            click.echo("=" * 40)
            click.echo(f"Task: {task_description}")
            click.echo()
            
            model_name = recommendation.model.value.replace("claude-", "").replace("-20250514", "").replace("-20241022", "")
            confidence_bar = "█" * int(recommendation.confidence * 10) + "░" * (10 - int(recommendation.confidence * 10))
            
            click.echo(f"Recommended Model: {model_name.upper()}")
            click.echo(f"Confidence:        {confidence_bar} {recommendation.confidence:.0%}")
            click.echo(f"Reasoning:         {recommendation.reasoning}")
            
            if recommendation.expected_cost:
                click.echo(f"Expected Cost:     ${recommendation.expected_cost:.4f}")
            
            if recommendation.expected_duration_ms:
                duration_sec = recommendation.expected_duration_ms / 1000
                click.echo(f"Expected Duration: {duration_sec:.1f}s")
            
            if recommendation.cost_savings:
                click.echo(f"💰 Cost Savings:    ${recommendation.cost_savings:.4f} vs Sonnet")
                savings_pct = (recommendation.cost_savings / (recommendation.expected_cost + recommendation.cost_savings)) * 100
                click.echo(f"   Savings:         {savings_pct:.0f}%")
            
        except Exception as e:
            click.echo(f"❌ Model recommendation failed: {e}", err=True)
            sys.exit(1)
    
    asyncio.run(_recommend())


@telemetry.command()
@click.option('--session-id', help='Session ID (defaults to current session)')
def session_insights(session_id: Optional[str]):
    """Get comprehensive session insights and analytics."""
    async def _insights():
        try:
            if not session_id:
                session_id = get_current_session_id()
                
            client = await get_telemetry_client()
            
            # Get session metrics
            session_metrics = await client.get_session_metrics(session_id)
            
            if not session_metrics:
                click.echo(f"❌ No data found for session: {session_id}")
                return
            
            click.echo(f"\n📊 Session Insights - {session_id}")
            click.echo("=" * 60)
            
            # Basic metrics
            duration = "Active"
            if session_metrics.end_time:
                duration_delta = session_metrics.end_time - session_metrics.start_time
                duration = f"{duration_delta.total_seconds() / 60:.1f} minutes"
            
            click.echo(f"Duration:         {duration}")
            click.echo(f"API Calls:        {session_metrics.api_calls}")
            click.echo(f"Total Cost:       ${session_metrics.total_cost:.3f}")
            click.echo(f"Input Tokens:     {session_metrics.total_input_tokens:,}")
            click.echo(f"Output Tokens:    {session_metrics.total_output_tokens:,}")
            click.echo(f"Errors:           {session_metrics.error_count}")
            
            # Efficiency metrics
            if session_metrics.api_calls > 0:
                cost_per_call = session_metrics.total_cost / session_metrics.api_calls
                tokens_per_call = session_metrics.total_input_tokens / session_metrics.api_calls
                click.echo(f"\n⚡ Efficiency:")
                click.echo(f"Cost per Call:    ${cost_per_call:.4f}")
                click.echo(f"Tokens per Call:  {tokens_per_call:.0f}")
            
            # Tools used
            if session_metrics.tools_used:
                click.echo(f"\n🛠️  Tools Used:")
                for tool in session_metrics.tools_used:
                    click.echo(f"  • {tool}")
            
            # Get cost optimization insights
            optimizer = CostOptimizationEngine(client)
            suggestions = await optimizer.get_optimization_suggestions(session_id)
            
            if suggestions:
                click.echo(f"\n💡 Insights & Suggestions:")
                for suggestion in suggestions[:3]:  # Show top 3
                    priority_icon = {"critical": "🚨", "high": "🔥", "medium": "⚠️", "low": "💡"}.get(suggestion.priority, "•")
                    click.echo(f"  {priority_icon} {suggestion.title}")
                    click.echo(f"    {suggestion.description}")
            
        except Exception as e:
            click.echo(f"❌ Session insights failed: {e}", err=True)
            sys.exit(1)
    
    asyncio.run(_insights())


@telemetry.command()
def health_check():
    """Check telemetry system health and connectivity."""
    async def _health_check():
        try:
            client = await get_telemetry_client()
            
            click.echo("🔍 Checking telemetry system health...")
            click.echo()
            
            # Test basic connectivity
            is_healthy = await client.health_check()
            
            if is_healthy:
                click.echo("✅ ClickHouse connection: OK")
            else:
                click.echo("❌ ClickHouse connection: FAILED")
                click.echo("   Please check: docker compose ps")
                sys.exit(1)
            
            # Test data availability
            recent_errors = await client.get_recent_errors(hours=24)
            click.echo(f"📊 Recent errors (24h): {len(recent_errors)}")
            
            # Test model stats
            model_stats = await client.get_model_usage_stats(days=7)
            total_requests = sum(stats["request_count"] for stats in model_stats.values())
            click.echo(f"📈 Total requests (7d): {total_requests}")
            
            if model_stats:
                click.echo("🤖 Active models:")
                for model, stats in model_stats.items():
                    model_name = model.replace("claude-", "").replace("-20250514", "").replace("-20241022", "")
                    click.echo(f"   • {model_name}: {stats['request_count']} requests, ${stats['total_cost']:.3f}")
            
            click.echo()
            click.echo("✅ Telemetry system is healthy and operational!")
            
        except Exception as e:
            click.echo(f"❌ Health check failed: {e}", err=True)
            click.echo()
            click.echo("🔧 Troubleshooting steps:")
            click.echo("  1. Check if telemetry infrastructure is running:")
            click.echo("     docker compose ps")
            click.echo("  2. Restart telemetry system if needed:")
            click.echo("     ./install-telemetry.sh")
            click.echo("  3. Check logs:")
            click.echo("     docker logs otel-collector")
            sys.exit(1)
    
    asyncio.run(_health_check())


# Add to main CLI
def add_telemetry_commands(main_cli):
    """Add telemetry commands to the main CLI."""
    main_cli.add_command(telemetry)