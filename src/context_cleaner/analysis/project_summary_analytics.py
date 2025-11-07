"""
Project Summary Analytics

Provides analytics and insights for Claude Code project summaries,
including completion tracking, categorization, and productivity metrics.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from collections import defaultdict, Counter

from .summary_parser import ProjectSummaryParser
from .models import ProjectSummary, SummaryType, FileType

logger = logging.getLogger(__name__)


class ProjectSummaryAnalytics:
    """Analytics service for project summary data."""

    def __init__(self):
        """Initialize analytics service."""
        self.summary_parser = ProjectSummaryParser()
        self._cached_summaries: List[ProjectSummary] = []
        self._last_analysis_time = None

    def analyze_project_summaries(self, search_paths: List[Path]) -> Dict[str, Any]:
        """
        Analyze project summaries from search paths.

        Args:
            search_paths: List of paths to search for summary files

        Returns:
            Dict containing comprehensive analytics
        """
        try:
            logger.info(f"Analyzing project summaries from {len(search_paths)} paths")

            # Discover and parse summary files
            summary_files = self._discover_summary_files(search_paths)
            summaries = self._parse_all_summaries(summary_files)
            summaries = self._deduplicate_summaries(summaries)

            # Cache results
            self._cached_summaries = summaries
            self._last_analysis_time = datetime.now()

            # Generate analytics
            analytics = {
                "overview": self._generate_overview(summaries),
                "categories": self._analyze_categories(summaries),
                "completion_status": self._analyze_completion(summaries),
                "timeline": self._analyze_timeline(summaries),
                "technology_trends": self._analyze_technology_trends(summaries),
                "productivity_insights": self._generate_productivity_insights(
                    summaries
                ),
                "metadata": {
                    "total_summaries": len(summaries),
                    "total_files": len(summary_files),
                    "analysis_time": self._last_analysis_time.isoformat(),
                    "parser_stats": self.summary_parser.get_stats(),
                },
            }

            logger.info(f"Analysis complete: {len(summaries)} summaries processed")
            return analytics

        except Exception as e:
            logger.error(f"Error analyzing project summaries: {e}")
            return {
                "error": str(e),
                "overview": {},
                "categories": {},
                "completion_status": {},
                "timeline": {},
                "technology_trends": {},
                "productivity_insights": {},
                "metadata": {"total_summaries": 0, "total_files": 0},
            }

    def _discover_summary_files(self, search_paths: List[Path]) -> List[Path]:
        """Discover summary files in search paths."""
        summary_files = []

        for search_path in search_paths:
            if not search_path.exists():
                continue

            logger.debug(f"Searching for summary files in: {search_path}")

            # Find .jsonl files
            for jsonl_file in search_path.rglob("*.jsonl"):
                try:
                    # Check if it's a summary file
                    file_metadata = self.summary_parser.detect_file_type(jsonl_file)
                    if file_metadata.file_type == FileType.SUMMARY:
                        summary_files.append(jsonl_file)
                        logger.debug(f"Found summary file: {jsonl_file}")
                except Exception as e:
                    logger.warning(f"Error checking file {jsonl_file}: {e}")

        logger.info(f"Discovered {len(summary_files)} summary files")
        return summary_files

    def _parse_all_summaries(self, summary_files: List[Path]) -> List[ProjectSummary]:
        """Parse all summary files."""
        all_summaries = []

        for file_path in summary_files:
            try:
                summaries = self.summary_parser.parse_summary_file(file_path)
                all_summaries.extend(summaries)
            except Exception as e:
                logger.warning(f"Error parsing summary file {file_path}: {e}")

        return all_summaries

    def _deduplicate_summaries(
        self, summaries: List[ProjectSummary]
    ) -> List[ProjectSummary]:
        """Remove duplicate summaries, preferring the most recent entry."""

        if not summaries:
            return []

        deduped: List[ProjectSummary] = []
        seen_leaf_ids = set()
        seen_fallback_keys = set()
        seen_descriptions = set()

        for summary in sorted(summaries, key=lambda s: s.timestamp, reverse=True):
            leaf_uuid = (summary.leaf_uuid or "").strip()

            normalized_description = (summary.description or "").strip().lower()

            if leaf_uuid:
                if leaf_uuid in seen_leaf_ids:
                    continue
                if (
                    normalized_description
                    and normalized_description in seen_descriptions
                ):
                    continue
                seen_leaf_ids.add(leaf_uuid)
            else:
                title_key = (summary.title or "").strip().lower()
                fallback_key = (title_key, normalized_description[:200])

                if fallback_key in seen_fallback_keys or (
                    normalized_description
                    and normalized_description in seen_descriptions
                ):
                    continue
                seen_fallback_keys.add(fallback_key)

            deduped.append(summary)
            if normalized_description:
                seen_descriptions.add(normalized_description)

        if len(deduped) != len(summaries):
            logger.info(
                "Deduplicated project summaries: %s -> %s unique entries",
                len(summaries),
                len(deduped),
            )

        # Maintain deterministic ordering (newest first)
        deduped.sort(key=lambda s: s.timestamp, reverse=True)
        return deduped

    def _generate_overview(self, summaries: List[ProjectSummary]) -> Dict[str, Any]:
        """Generate overview statistics."""
        if not summaries:
            return {"total_projects": 0}

        completed_count = sum(1 for s in summaries if s.is_completed)

        return {
            "total_projects": len(summaries),
            "completed_projects": completed_count,
            "in_progress_projects": len(summaries) - completed_count,
            "completion_rate": completed_count / len(summaries) * 100,
            "average_title_length": sum(len(s.title) for s in summaries)
            / len(summaries),
            "unique_categories": len(set(s.project_category for s in summaries)),
        }

    def _analyze_categories(self, summaries: List[ProjectSummary]) -> Dict[str, Any]:
        """Analyze project categories."""
        category_counts = Counter(s.project_category for s in summaries)
        category_completion = defaultdict(lambda: {"total": 0, "completed": 0})

        for summary in summaries:
            category = summary.project_category
            category_completion[category]["total"] += 1
            if summary.is_completed:
                category_completion[category]["completed"] += 1

        # Calculate completion rates per category
        category_stats = {}
        for category, counts in category_completion.items():
            completion_rate = (
                counts["completed"] / counts["total"] * 100
                if counts["total"] > 0
                else 0
            )
            category_stats[category] = {
                "total": counts["total"],
                "completed": counts["completed"],
                "completion_rate": completion_rate,
            }

        return {
            "distribution": dict(category_counts),
            "completion_by_category": category_stats,
            "most_common": category_counts.most_common(5),
        }

    def _analyze_completion(self, summaries: List[ProjectSummary]) -> Dict[str, Any]:
        """Analyze completion patterns."""
        completion_by_status = Counter(s.completion_status for s in summaries)

        # Analyze completion indicators in descriptions
        completion_keywords = defaultdict(int)
        for summary in summaries:
            if summary.is_completed:
                desc_lower = summary.description.lower()
                keywords = [
                    "completed",
                    "finished",
                    "done",
                    "fixed",
                    "implemented",
                    "deployed",
                ]
                for keyword in keywords:
                    if keyword in desc_lower:
                        completion_keywords[keyword] += 1

        return {
            "status_distribution": dict(completion_by_status),
            "completion_indicators": dict(completion_keywords),
            "completion_percentage": (
                len([s for s in summaries if s.is_completed]) / len(summaries) * 100
                if summaries
                else 0
            ),
        }

    def _analyze_timeline(self, summaries: List[ProjectSummary]) -> Dict[str, Any]:
        """Analyze timeline and temporal patterns."""
        if not summaries:
            return {"projects_by_month": {}, "recent_activity": {}}

        # Group by month
        projects_by_month = defaultdict(int)
        for summary in summaries:
            month_key = summary.timestamp.strftime("%Y-%m")
            projects_by_month[month_key] += 1

        # Recent activity (last 30 days)
        now = datetime.now()
        thirty_days_ago = now - timedelta(days=30)
        recent_summaries = [s for s in summaries if s.timestamp >= thirty_days_ago]

        return {
            "projects_by_month": dict(projects_by_month),
            "recent_activity": {
                "last_30_days": len(recent_summaries),
                "average_per_week": (
                    len(recent_summaries) / 4.3 if recent_summaries else 0
                ),
            },
            "oldest_project": min(s.timestamp for s in summaries).isoformat(),
            "newest_project": max(s.timestamp for s in summaries).isoformat(),
        }

    def _analyze_technology_trends(
        self, summaries: List[ProjectSummary]
    ) -> Dict[str, Any]:
        """Analyze technology usage trends."""
        # Aggregate all tags
        all_tags = []
        for summary in summaries:
            all_tags.extend(summary.tags)

        tag_counts = Counter(all_tags)

        # Technology categories
        tech_categories = {
            "languages": ["python", "javascript", "typescript", "go", "rust"],
            "frameworks": ["react", "django", "flask", "fastapi", "nodejs"],
            "databases": ["postgresql", "mysql", "redis", "mongodb"],
            "infrastructure": ["docker", "kubernetes", "aws", "azure", "gcp"],
        }

        category_usage = {}
        for category, techs in tech_categories.items():
            category_usage[category] = {tech: tag_counts.get(tech, 0) for tech in techs}

        return {
            "popular_technologies": dict(tag_counts.most_common(10)),
            "technology_categories": category_usage,
            "total_unique_tags": len(tag_counts),
        }

    def _generate_productivity_insights(
        self, summaries: List[ProjectSummary]
    ) -> Dict[str, Any]:
        """Generate productivity insights."""
        if not summaries:
            return {"insights": [], "recommendations": []}

        insights = []
        recommendations = []

        # Completion rate insight
        completion_rate = (
            sum(1 for s in summaries if s.is_completed) / len(summaries) * 100
        )
        if completion_rate > 80:
            insights.append(
                f"High completion rate: {completion_rate:.1f}% of projects are completed"
            )
        elif completion_rate < 50:
            insights.append(
                f"Low completion rate: {completion_rate:.1f}% of projects are completed"
            )
            recommendations.append(
                "Consider breaking down large projects into smaller, manageable tasks"
            )

        # Category analysis
        categories = Counter(s.project_category for s in summaries)
        if categories:
            most_common_category = categories.most_common(1)[0]
            insights.append(
                f"Most common project type: {most_common_category[0]} ({most_common_category[1]} projects)"
            )

        # Technology diversity
        all_tags = []
        for summary in summaries:
            all_tags.extend(summary.tags)
        unique_technologies = len(set(all_tags))

        if unique_technologies > 10:
            insights.append(
                f"High technology diversity: {unique_technologies} different technologies used"
            )
        elif unique_technologies < 3:
            recommendations.append(
                "Consider expanding technology stack for diverse skill development"
            )

        return {
            "insights": insights,
            "recommendations": recommendations,
            "completion_rate": completion_rate,
            "technology_diversity_score": unique_technologies,
        }

    def get_project_categories_summary(self) -> Dict[str, Any]:
        """Get summary of project categories for dashboard widget."""
        if not self._cached_summaries:
            return {"categories": [], "total": 0}

        categories = Counter(s.project_category for s in self._cached_summaries)

        return {
            "categories": [
                {
                    "name": name,
                    "count": count,
                    "percentage": count / len(self._cached_summaries) * 100,
                }
                for name, count in categories.most_common()
            ],
            "total": len(self._cached_summaries),
            "last_updated": (
                self._last_analysis_time.isoformat()
                if self._last_analysis_time
                else None
            ),
        }

    def get_completion_metrics(self) -> Dict[str, Any]:
        """Get completion metrics for dashboard widget."""
        if not self._cached_summaries:
            return {"completed": 0, "in_progress": 0, "completion_rate": 0}

        completed = sum(1 for s in self._cached_summaries if s.is_completed)
        total = len(self._cached_summaries)

        return {
            "completed": completed,
            "in_progress": total - completed,
            "total": total,
            "completion_rate": completed / total * 100 if total > 0 else 0,
            "last_updated": (
                self._last_analysis_time.isoformat()
                if self._last_analysis_time
                else None
            ),
        }

    def get_recent_projects(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most recent projects."""
        if not self._cached_summaries:
            return []

        # Sort by timestamp descending
        recent = sorted(
            self._cached_summaries, key=lambda x: x.timestamp, reverse=True
        )[:limit]

        return [
            {
                "title": s.title,
                "description": (
                    s.description[:100] + "..."
                    if len(s.description) > 100
                    else s.description
                ),
                "category": s.project_category,
                "completed": s.is_completed,
                "timestamp": s.timestamp.isoformat(),
                "tags": s.tags,
            }
            for s in recent
        ]
