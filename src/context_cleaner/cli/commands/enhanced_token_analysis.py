"""
CLI Command for Enhanced Token Analysis

This command allows testing and validation of the new enhanced token counting system
that addresses the 90% undercount issue.
"""

import asyncio
import click
import json
from datetime import datetime
from pathlib import Path

from ...analysis.enhanced_token_counter import EnhancedTokenCounterService
from ...analysis.dashboard_integration import DashboardTokenAnalyzer


@click.group(name="token-analysis")
def token_analysis():
    """Enhanced token analysis commands using Anthropic's count-tokens API."""
    pass


@token_analysis.command()
@click.option("--api-key", help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
@click.option("--max-files", type=int, help="Maximum files to process (default: all)")
@click.option("--max-lines", type=int, help="Maximum lines per file (default: all)")
@click.option(
    "--no-api",
    is_flag=True,
    help="Skip count-tokens API calls (faster but less accurate)",
)
@click.option("--output", type=click.Path(), help="Save results to JSON file")
@click.option("--compare", is_flag=True, help="Compare with current dashboard method")
def comprehensive(api_key, max_files, max_lines, no_api, output, compare):
    """Run comprehensive token analysis addressing the 90% undercount issue."""

    click.echo("🔍 Enhanced Token Analysis - Addressing 90% Undercount Issue")
    click.echo("=" * 60)

    async def run_analysis():
        # Initialize service
        service = EnhancedTokenCounterService(api_key)

        # Show current limitations being addressed
        click.echo("\n📊 Current Implementation Limitations:")
        click.echo(f"   • Files processed: 10 most recent only")
        click.echo(f"   • Lines per file: First 1,000 only")
        click.echo(f"   • Content types: Assistant messages only")
        click.echo(f"   • Validation: None")

        click.echo(f"\n🚀 Enhanced Analysis Parameters:")
        click.echo(
            f"   • Files to process: {'All files' if not max_files else f'{max_files} files'}"
        )
        click.echo(
            f"   • Lines per file: {'Complete files' if not max_lines else f'{max_lines} lines'}"
        )
        click.echo(f"   • Content types: All message types")
        click.echo(
            f"   • API validation: {'Disabled' if no_api else 'Enabled' if api_key else 'Auto-detect'}"
        )

        # Run analysis
        click.echo(f"\n⏳ Running enhanced analysis...")
        start_time = datetime.now()

        try:
            analysis = await service.analyze_comprehensive_token_usage(
                max_files=max_files,
                max_lines_per_file=max_lines,
                use_count_tokens_api=not no_api,
            )

            duration = (datetime.now() - start_time).total_seconds()

            # Display results
            click.echo(f"\n✅ Analysis Complete ({duration:.2f}s)")
            click.echo("=" * 60)

            click.echo(f"\n📈 Coverage Improvements:")
            click.echo(f"   Sessions analyzed: {analysis.total_sessions_analyzed}")
            click.echo(f"   Files processed: {analysis.total_files_processed}")
            click.echo(f"   Lines processed: {analysis.total_lines_processed:,}")

            click.echo(f"\n🎯 Token Count Results:")
            click.echo(f"   Reported tokens: {analysis.total_reported_tokens:,}")
            click.echo(f"   Calculated tokens: {analysis.total_calculated_tokens:,}")
            click.echo(f"   Accuracy ratio: {analysis.global_accuracy_ratio:.2f}x")

            if analysis.global_undercount_percentage > 0:
                click.echo(f"\n⚠️  Undercount Detection:")
                missed = (
                    analysis.total_calculated_tokens - analysis.total_reported_tokens
                )
                click.echo(
                    f"   Undercount percentage: {analysis.global_undercount_percentage:.1f}%"
                )
                click.echo(f"   Missed tokens: {missed:,}")
                click.echo(
                    f"   Actual usage is {analysis.global_accuracy_ratio:.1f}x higher than reported"
                )

            if analysis.api_calls_made > 0:
                click.echo(f"\n🔗 API Validation:")
                click.echo(f"   Count-tokens API calls: {analysis.api_calls_made}")
                click.echo(f"   Validation enabled: ✅")
            else:
                click.echo(f"\n💡 API Validation:")
                click.echo(f"   Count-tokens API calls: 0")
                click.echo(f"   Tip: Set --api-key for precise validation")

            # Category breakdown
            if analysis.category_reported:
                click.echo(f"\n📂 Category Breakdown:")
                for category, tokens in sorted(
                    analysis.category_reported.items(), key=lambda x: x[1], reverse=True
                )[:5]:
                    click.echo(
                        f"   {category.replace('_', ' ').title()}: {tokens:,} tokens"
                    )

            # Session insights
            if analysis.sessions:
                top_sessions = sorted(
                    analysis.sessions.values(),
                    key=lambda s: s.total_reported_tokens,
                    reverse=True,
                )[:3]
                click.echo(f"\n👥 Top Sessions by Token Usage:")
                for i, session in enumerate(top_sessions, 1):
                    undercount = session.undercount_percentage
                    click.echo(f"   {i}. Session {session.session_id[:12]}...")
                    click.echo(
                        f"      Reported: {session.total_reported_tokens:,} tokens"
                    )
                    click.echo(
                        f"      Calculated: {session.calculated_total_tokens:,} tokens"
                    )
                    if undercount > 10:
                        click.echo(f"      ⚠️  Undercount: {undercount:.1f}%")

            # Error summary
            if analysis.errors_encountered:
                click.echo(f"\n⚠️  Processing Errors:")
                for error in analysis.errors_encountered[:3]:
                    click.echo(f"   • {error}")
                if len(analysis.errors_encountered) > 3:
                    click.echo(
                        f"   ... and {len(analysis.errors_encountered) - 3} more"
                    )

            # Improvement summary
            improvement = analysis.improvement_summary
            click.echo(f"\n🎉 Summary:")
            click.echo(
                f"   Previous method processed: ~10,000 lines from 10 recent files"
            )
            click.echo(
                f"   Enhanced method processed: {analysis.total_lines_processed:,} lines from {analysis.total_files_processed} files"
            )
            if analysis.global_undercount_percentage > 50:
                click.echo(
                    f"   💥 Major undercount detected: Your actual usage is {analysis.global_accuracy_ratio:.1f}x higher!"
                )
            elif analysis.global_undercount_percentage > 10:
                click.echo(
                    f"   📊 Moderate undercount detected: {analysis.global_undercount_percentage:.1f}% more usage found"
                )
            else:
                click.echo(f"   ✅ Token counting appears accurate")

        except Exception as e:
            click.echo(f"\n❌ Analysis failed: {str(e)}")
            raise click.ClickException(f"Enhanced token analysis failed: {str(e)}")

        # Save results if requested
        if output:
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "analysis": {
                    "sessions_analyzed": analysis.total_sessions_analyzed,
                    "files_processed": analysis.total_files_processed,
                    "lines_processed": analysis.total_lines_processed,
                    "total_reported_tokens": analysis.total_reported_tokens,
                    "total_calculated_tokens": analysis.total_calculated_tokens,
                    "accuracy_ratio": analysis.global_accuracy_ratio,
                    "undercount_percentage": analysis.global_undercount_percentage,
                    "category_breakdown": analysis.category_reported,
                    "api_calls_made": analysis.api_calls_made,
                    "processing_time_seconds": analysis.processing_time_seconds,
                    "errors": analysis.errors_encountered,
                },
            }

            with open(output, "w") as f:
                json.dump(output_data, f, indent=2, default=str)
            click.echo(f"\n💾 Results saved to {output}")

        return analysis

    # Run the async analysis
    try:
        analysis = asyncio.run(run_analysis())

        # Compare with current method if requested
        if compare:
            click.echo(f"\n🔄 Comparing with Current Dashboard Method...")
            # This would require importing the current dashboard method
            # For now, just show the comparison conceptually
            click.echo(f"   Current method limitations:")
            click.echo(
                f"   • Would only process 10 files vs {analysis.total_files_processed}"
            )
            click.echo(
                f"   • Would only process ~10,000 lines vs {analysis.total_lines_processed:,}"
            )
            click.echo(
                f"   • Would miss {analysis.global_undercount_percentage:.1f}% of tokens"
            )

    except KeyboardInterrupt:
        click.echo(f"\n❌ Analysis cancelled by user")
    except Exception as e:
        raise click.ClickException(f"Analysis failed: {str(e)}")


@token_analysis.command()
def dashboard():
    """Test the dashboard integration for enhanced token analysis."""

    click.echo("🎛️  Testing Dashboard Integration")
    click.echo("=" * 40)

    async def test_dashboard():
        analyzer = DashboardTokenAnalyzer()

        click.echo("⏳ Running dashboard-compatible analysis...")

        try:
            dashboard_data = await analyzer.get_enhanced_token_analysis()

            click.echo("✅ Dashboard integration successful!")
            click.echo(f"\nResults:")

            total_tokens = dashboard_data.get("total_tokens", {})
            click.echo(f"   Total tokens: {total_tokens.get('total', 0):,}")

            categories = dashboard_data.get("categories", [])
            click.echo(f"   Categories found: {len(categories)}")

            metadata = dashboard_data.get("analysis_metadata", {})
            if metadata.get("enhanced_analysis"):
                click.echo(f"   Enhanced analysis: ✅")
                click.echo(f"   Sessions: {metadata.get('sessions_analyzed', 0)}")
                click.echo(f"   Files: {metadata.get('files_processed', 0)}")

                accuracy = metadata.get("accuracy_improvement", {})
                if accuracy:
                    click.echo(
                        f"   Improvement: {accuracy.get('improvement_factor', 'N/A')}"
                    )
                    click.echo(
                        f"   Undercount: {accuracy.get('undercount_percentage', 'N/A')}"
                    )
            else:
                click.echo(f"   Enhanced analysis: ❌ (fallback used)")

            recommendations = dashboard_data.get("recommendations", [])
            if recommendations:
                click.echo(f"\n💡 Recommendations:")
                for i, rec in enumerate(recommendations[:3], 1):
                    click.echo(f"   {i}. {rec}")

        except Exception as e:
            click.echo(f"❌ Dashboard integration failed: {str(e)}")
            raise click.ClickException(f"Dashboard test failed: {str(e)}")

    try:
        asyncio.run(test_dashboard())
    except Exception as e:
        raise click.ClickException(f"Dashboard test failed: {str(e)}")


@token_analysis.command()
@click.option("--session-id", help="Specific session ID to analyze")
def session(session_id):
    """Analyze token usage for a specific session."""

    if not session_id:
        raise click.ClickException("--session-id is required")

    click.echo(f"🎯 Session Token Analysis: {session_id}")
    click.echo("=" * 50)

    async def analyze_session():
        service = EnhancedTokenCounterService()

        try:
            analysis = await service.analyze_comprehensive_token_usage()

            # Find the specific session
            session_data = analysis.sessions.get(session_id)
            if not session_data:
                # Try partial match
                matching_sessions = [
                    sid for sid in analysis.sessions.keys() if session_id in sid
                ]

                if not matching_sessions:
                    click.echo(f"❌ Session '{session_id}' not found")
                    click.echo(f"Available sessions: {len(analysis.sessions)}")
                    return

                if len(matching_sessions) > 1:
                    click.echo(f"Multiple sessions match '{session_id}':")
                    for sid in matching_sessions[:5]:
                        click.echo(f"   • {sid}")
                    return

                session_data = analysis.sessions[matching_sessions[0]]
                session_id = matching_sessions[0]

            # Display session details
            click.echo(f"\n📊 Session: {session_id}")
            click.echo(f"   Reported tokens: {session_data.total_reported_tokens:,}")
            click.echo(
                f"   Calculated tokens: {session_data.calculated_total_tokens:,}"
            )
            click.echo(f"   Accuracy ratio: {session_data.accuracy_ratio:.2f}x")

            if session_data.undercount_percentage > 0:
                click.echo(
                    f"   ⚠️  Undercount: {session_data.undercount_percentage:.1f}%"
                )

            click.echo(f"\n💬 Content:")
            click.echo(f"   User messages: {len(session_data.user_messages)}")
            click.echo(f"   Assistant messages: {len(session_data.assistant_messages)}")
            click.echo(f"   System prompts: {len(session_data.system_prompts)}")
            click.echo(f"   Tool calls: {len(session_data.tool_calls)}")

            click.echo(f"\n📂 Categories:")
            for category, count in session_data.content_categories.items():
                if count > 0:
                    click.echo(f"   {category.replace('_', ' ').title()}: {count}")

        except Exception as e:
            raise click.ClickException(f"Session analysis failed: {str(e)}")

    asyncio.run(analyze_session())
