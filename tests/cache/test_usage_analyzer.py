#!/usr/bin/env python3
"""
Tests for Usage Pattern Analyzer

Comprehensive tests for analyzing file access patterns, workflow recognition,
and user behavior patterns from Claude Code cache data.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from src.context_cleaner.analysis.usage_analyzer import (
    UsagePatternAnalyzer, WorkflowPattern, FileUsageMetrics, UsagePatternSummary
)
from src.context_cleaner.analysis.models import SessionAnalysis, ToolUsage, CacheConfig
from src.context_cleaner.analysis.discovery import CacheLocation


class TestUsagePatternAnalyzer:
    """Test suite for UsagePatternAnalyzer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = UsagePatternAnalyzer()
        self.config = CacheConfig()
        
        # Create sample session data
        now = datetime.now()
        
        self.sample_sessions = [
            SessionAnalysis(
                session_id="session-1",
                start_time=now - timedelta(hours=2),
                end_time=now - timedelta(hours=1),
                total_messages=10,
                total_tokens=1000,
                file_operations=[
                    ToolUsage("Read", "tool1", {"file_path": "/test/app.py"}, now - timedelta(hours=2)),
                    ToolUsage("Edit", "tool2", {"file_path": "/test/app.py"}, now - timedelta(hours=2)),
                    ToolUsage("Bash", "tool3", {"command": "python test.py"}, now - timedelta(hours=2))
                ],
                context_switches=2,
                average_response_time=1.0,
                cache_efficiency=0.8
            ),
            SessionAnalysis(
                session_id="session-2", 
                start_time=now - timedelta(hours=1),
                end_time=now,
                total_messages=15,
                total_tokens=1500,
                file_operations=[
                    ToolUsage("Read", "tool4", {"file_path": "/test/app.py"}, now - timedelta(hours=1)),
                    ToolUsage("Read", "tool5", {"file_path": "/test/utils.py"}, now - timedelta(hours=1)),
                    ToolUsage("Edit", "tool6", {"file_path": "/test/utils.py"}, now - timedelta(hours=1))
                ],
                context_switches=1,
                average_response_time=1.2,
                cache_efficiency=0.7
            )
        ]
        
        # Mock cache location
        self.mock_location = CacheLocation(
            path=Path("/test/cache"),
            project_name="test-project",
            session_files=[Path("/test/session1.jsonl"), Path("/test/session2.jsonl")],
            last_modified=now,
            total_size_bytes=1024
        )
    
    def test_analyze_usage_patterns_with_sessions(self):
        """Test usage pattern analysis with sample sessions."""
        with patch.object(self.analyzer.discovery, 'discover_cache_locations') as mock_discover:
            with patch.object(self.analyzer.parser, 'parse_session_file') as mock_parse:
                mock_discover.return_value = [self.mock_location]
                mock_parse.side_effect = self.sample_sessions
                
                summary = self.analyzer.analyze_usage_patterns()
                
                assert summary.total_sessions_analyzed == 2
                assert summary.total_files_accessed == 2  # app.py and utils.py
                assert len(summary.workflow_patterns) >= 0
                assert len(summary.file_usage_metrics) == 2
                
                # Check file metrics
                assert "/test/app.py" in summary.file_usage_metrics
                assert "/test/utils.py" in summary.file_usage_metrics
                
                app_metrics = summary.file_usage_metrics["/test/app.py"]
                assert app_metrics.total_accesses == 3  # Actual accesses found
                assert app_metrics.unique_sessions == 2
    
    def test_detect_workflow_patterns(self):
        """Test workflow pattern detection."""
        patterns = self.analyzer._detect_workflow_patterns(self.sample_sessions)
        
        # Should detect at least some patterns from the sample data
        assert isinstance(patterns, list)
        
        if patterns:
            pattern = patterns[0]
            assert isinstance(pattern, WorkflowPattern)
            assert pattern.frequency >= 1
            assert 0 <= pattern.confidence_score <= 1
    
    def test_analyze_file_usage(self):
        """Test file usage analysis."""
        metrics = self.analyzer._analyze_file_usage(self.sample_sessions)
        
        assert "/test/app.py" in metrics
        assert "/test/utils.py" in metrics
        
        app_metrics = metrics["/test/app.py"]
        assert app_metrics.total_accesses == 3  # Actual accesses found
        assert app_metrics.unique_sessions == 2
        assert "Read" in app_metrics.tool_types
        assert "Edit" in app_metrics.tool_types
        
        utils_metrics = metrics["/test/utils.py"]
        assert utils_metrics.total_accesses == 2  # Read and Edit in session 2
        assert utils_metrics.unique_sessions == 1
    
    def test_analyze_tool_sequences(self):
        """Test tool sequence analysis."""
        sequences = self.analyzer._analyze_tool_sequences(self.sample_sessions)
        
        assert isinstance(sequences, list)
        
        if sequences:
            sequence, count = sequences[0]
            assert isinstance(sequence, list)
            assert isinstance(count, int)
            assert count >= 1
    
    def test_create_pattern_signature(self):
        """Test pattern signature creation."""
        file_sequence = ["/test/app.py", "/test/utils.py"]
        tool_sequence = ["Read", "Edit", "Bash"]
        
        signature = self.analyzer._create_pattern_signature(file_sequence, tool_sequence)
        
        assert isinstance(signature, str)
        assert "tools:" in signature
        assert "types:" in signature
    
    def test_find_most_common_sequence(self):
        """Test finding most common sequence."""
        sequences = [
            ["Read", "Edit", "Bash"],
            ["Read", "Edit", "Test"],
            ["Read", "Edit", "Run"]
        ]
        
        common = self.analyzer._find_most_common_sequence(sequences)
        
        assert common == ["Read", "Edit", "Bash"]  # First in list when tied
    
    def test_calculate_pattern_confidence(self):
        """Test pattern confidence calculation."""
        file_sequences = [
            ["/test/a.py", "/test/b.py"],
            ["/test/a.py", "/test/c.py"],
            ["/test/a.py", "/test/b.py"]
        ]
        tool_sequences = [
            ["Read", "Edit"],
            ["Read", "Edit"],
            ["Read", "Edit"]
        ]
        
        confidence = self.analyzer._calculate_pattern_confidence(file_sequences, tool_sequences)
        
        assert 0 <= confidence <= 1
        assert confidence > 0  # Should have some confidence with consistent tools
    
    def test_sequence_similarity(self):
        """Test sequence similarity calculation."""
        seq1 = ["Read", "Edit", "Bash"]
        seq2 = ["Read", "Edit", "Test"]
        
        similarity = self.analyzer._sequence_similarity(seq1, seq2)
        
        assert 0 <= similarity <= 1
        assert similarity >= 0.5  # Should be similar with 2/3 overlap
    
    def test_generate_pattern_description(self):
        """Test pattern description generation."""
        tools = ["Read", "Edit", "Bash"]
        files = ["/test/app.py", "/test/test.py"]
        
        name, description = self.analyzer._generate_pattern_description(tools, files)
        
        assert isinstance(name, str)
        assert isinstance(description, str)
        assert len(name) > 0
        assert len(description) > 0
    
    def test_calculate_file_transitions(self):
        """Test file transition calculation."""
        file_sequences = [
            ["/test/a.py", "/test/b.py", "/test/c.py"],
            ["/test/a.py", "/test/b.py", "/test/d.py"],
            ["/test/a.py", "/test/b.py", "/test/c.py"]
        ]
        
        transitions = self.analyzer._calculate_file_transitions(file_sequences)
        
        assert isinstance(transitions, list)
        
        if transitions:
            from_file, to_file, probability = transitions[0]
            assert isinstance(from_file, str)
            assert isinstance(to_file, str)
            assert 0 <= probability <= 1
    
    def test_extract_context_words(self):
        """Test context word extraction."""
        session = self.sample_sessions[0]
        operation = session.file_operations[0]
        
        words = self.analyzer._extract_context_words(session, operation)
        
        assert isinstance(words, list)
        assert all(isinstance(word, str) for word in words)
        assert all(len(word) > 2 for word in words)  # Should filter short words
    
    def test_analyze_duration_patterns(self):
        """Test session duration pattern analysis."""
        patterns = self.analyzer._analyze_duration_patterns(self.sample_sessions)
        
        assert "average_duration" in patterns
        assert "short_session_ratio" in patterns
        assert "medium_session_ratio" in patterns
        assert "long_session_ratio" in patterns
        
        assert patterns["average_duration"] > 0
        assert 0 <= patterns["short_session_ratio"] <= 1
    
    def test_analyze_context_switches(self):
        """Test context switch analysis."""
        frequency = self.analyzer._analyze_context_switches(self.sample_sessions)
        
        assert isinstance(frequency, float)
        assert frequency >= 0
        
        # Should be average of context switches per session
        expected = (self.sample_sessions[0].context_switches + self.sample_sessions[1].context_switches) / 2
        assert frequency == expected
    
    def test_analyze_productive_hours(self):
        """Test productive hour analysis."""
        hours = self.analyzer._analyze_productive_hours(self.sample_sessions)
        
        assert isinstance(hours, list)
        assert all(isinstance(hour, int) for hour in hours)
        assert all(0 <= hour <= 23 for hour in hours)
    
    def test_get_pattern_recommendations(self):
        """Test pattern recommendation generation."""
        summary = UsagePatternSummary(
            total_sessions_analyzed=10,
            total_files_accessed=50,
            workflow_patterns=[],
            file_usage_metrics={f"/test/file{i}.py": FileUsageMetrics(
                file_path=f"/test/file{i}.py",
                total_accesses=5,
                unique_sessions=3,
                tool_types={"Read", "Edit"},
                first_access=datetime.now() - timedelta(days=1),
                last_access=datetime.now(),
                average_session_frequency=3.0,  # Heavy usage (>=2 for Moderate, >=5 for Heavy)
                peak_usage_hours=[9, 10, 14],
                common_contexts=["python", "code"]
            ) for i in range(15)},  # 15 heavily used files
            common_tool_sequences=[],
            session_duration_patterns={},
            context_switch_frequency=3.0,
            most_productive_hours=[]
        )
        
        recommendations = self.analyzer.get_pattern_recommendations(summary)
        
        assert isinstance(recommendations, list)
        assert all(isinstance(rec, str) for rec in recommendations)
        
        # Should recommend organizing files due to many heavily used files
        heavy_files_rec = any("organizing" in rec.lower() for rec in recommendations)
        assert heavy_files_rec
    
    def test_empty_sessions_handling(self):
        """Test handling of empty session list."""
        with patch.object(self.analyzer.discovery, 'discover_cache_locations') as mock_discover:
            mock_discover.return_value = []
            
            summary = self.analyzer.analyze_usage_patterns()
            
            assert summary.total_sessions_analyzed == 0
            assert summary.total_files_accessed == 0
            assert len(summary.workflow_patterns) == 0
            assert len(summary.file_usage_metrics) == 0


class TestWorkflowPattern:
    """Test suite for WorkflowPattern class."""
    
    def test_workflow_pattern_properties(self):
        """Test WorkflowPattern property calculations."""
        datetime.now()
        
        # Frequent pattern
        frequent_pattern = WorkflowPattern(
            pattern_id="pattern-1",
            name="Development Workflow",
            description="Read, edit, test cycle",
            file_sequence=["/test/app.py", "/test/test.py"],
            tool_sequence=["Read", "Edit", "Bash"],
            frequency=5,
            confidence_score=0.8,
            average_duration=30.0,
            common_transitions=[("app.py", "test.py", 0.7)],
            session_ids=["s1", "s2", "s3", "s4", "s5"]
        )
        
        assert frequent_pattern.is_frequent is True
        assert frequent_pattern.complexity_level == "Simple"  # 2 files
        
        # Complex pattern
        complex_pattern = WorkflowPattern(
            pattern_id="pattern-2",
            name="Complex Workflow",
            description="Multi-file development",
            file_sequence=[f"/test/file{i}.py" for i in range(8)],
            tool_sequence=["Read", "Edit", "Bash", "Test"],
            frequency=2,
            confidence_score=0.5,
            average_duration=60.0,
            common_transitions=[],
            session_ids=["s1", "s2"]
        )
        
        assert complex_pattern.is_frequent is False  # Low frequency
        assert complex_pattern.complexity_level == "Complex"  # 8 files


class TestFileUsageMetrics:
    """Test suite for FileUsageMetrics class."""
    
    def test_file_usage_metrics_properties(self):
        """Test FileUsageMetrics property calculations."""
        now = datetime.now()
        
        # Heavy usage file
        heavy_metrics = FileUsageMetrics(
            file_path="/test/main.py",
            total_accesses=20,
            unique_sessions=4,
            tool_types={"Read", "Edit", "Bash"},
            first_access=now - timedelta(days=7),
            last_access=now - timedelta(hours=1),
            average_session_frequency=5.0,  # Heavy usage
            peak_usage_hours=[9, 10, 14],
            common_contexts=["python", "main", "function"]
        )
        
        assert heavy_metrics.usage_intensity == "Heavy"
        assert heavy_metrics.staleness_days == 0  # Less than 1 day
        
        # Light usage file
        light_metrics = FileUsageMetrics(
            file_path="/test/config.py",
            total_accesses=3,
            unique_sessions=2,
            tool_types={"Read"},
            first_access=now - timedelta(days=30),
            last_access=now - timedelta(days=10),
            average_session_frequency=1.0,  # Light usage
            peak_usage_hours=[15],
            common_contexts=["config", "settings"]
        )
        
        assert light_metrics.usage_intensity == "Light"
        assert light_metrics.staleness_days == 10
        
        # Rare usage file
        rare_metrics = FileUsageMetrics(
            file_path="/test/old.py",
            total_accesses=1,
            unique_sessions=1,
            tool_types={"Read"},
            first_access=now - timedelta(days=60),
            last_access=now - timedelta(days=60),
            average_session_frequency=0.1,  # Rare usage
            peak_usage_hours=[],
            common_contexts=[]
        )
        
        assert rare_metrics.usage_intensity == "Rare"
        assert rare_metrics.staleness_days == 60


class TestUsagePatternSummary:
    """Test suite for UsagePatternSummary class."""
    
    def test_usage_pattern_summary_properties(self):
        """Test UsagePatternSummary property calculations."""
        now = datetime.now()
        
        # Create sample workflow patterns
        patterns = [
            WorkflowPattern(
                pattern_id="p1",
                name="Main Workflow",
                description="Primary development",
                file_sequence=["/test/main.py"],
                tool_sequence=["Read", "Edit"],
                frequency=10,
                confidence_score=0.9,
                average_duration=25.0,
                common_transitions=[],
                session_ids=[]
            ),
            WorkflowPattern(
                pattern_id="p2", 
                name="Testing Workflow",
                description="Testing and validation",
                file_sequence=["/test/test.py"],
                tool_sequence=["Bash", "Read"],
                frequency=5,
                confidence_score=0.7,
                average_duration=15.0,
                common_transitions=[],
                session_ids=[]
            )
        ]
        
        # Create sample file metrics
        file_metrics = {
            "/test/main.py": FileUsageMetrics(
                file_path="/test/main.py",
                total_accesses=15,
                unique_sessions=5,
                tool_types={"Read", "Edit"},
                first_access=now - timedelta(days=7),
                last_access=now,
                average_session_frequency=3.0,  # Heavy
                peak_usage_hours=[9, 10],
                common_contexts=["main", "function"]
            ),
            "/test/utils.py": FileUsageMetrics(
                file_path="/test/utils.py", 
                total_accesses=8,
                unique_sessions=3,
                tool_types={"Read", "Edit"},
                first_access=now - timedelta(days=5),
                last_access=now - timedelta(hours=2),
                average_session_frequency=2.5,  # Moderate
                peak_usage_hours=[14],
                common_contexts=["utils", "helper"]
            ),
            "/test/config.py": FileUsageMetrics(
                file_path="/test/config.py",
                total_accesses=2,
                unique_sessions=1, 
                tool_types={"Read"},
                first_access=now - timedelta(days=10),
                last_access=now - timedelta(days=5),
                average_session_frequency=0.5,  # Light
                peak_usage_hours=[],
                common_contexts=["config"]
            )
        }
        
        summary = UsagePatternSummary(
            total_sessions_analyzed=8,
            total_files_accessed=3,
            workflow_patterns=patterns,
            file_usage_metrics=file_metrics,
            common_tool_sequences=[],
            session_duration_patterns={},
            context_switch_frequency=2.0,
            most_productive_hours=[9, 10, 14]
        )
        
        # Test top workflow patterns (sorted by frequency and confidence)
        top_patterns = summary.top_workflow_patterns
        assert len(top_patterns) == 2
        assert top_patterns[0].name == "Main Workflow"  # Higher frequency
        
        # Test heavily used files
        heavily_used = summary.heavily_used_files
        assert len(heavily_used) == 2  # main.py (Heavy) and utils.py (Moderate)
        
        file_paths = [f.file_path for f in heavily_used]
        assert "/test/main.py" in file_paths
        assert "/test/utils.py" in file_paths
        assert "/test/config.py" not in file_paths  # Light usage


if __name__ == "__main__":
    pytest.main([__file__, "-v"])