"""
Comprehensive Tests for 90% Undercount Detection and Validation

These tests specifically validate that the Enhanced Token Counting System
accurately detects and quantifies the 90% token undercount issue.
"""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.context_cleaner.analysis.enhanced_token_counter import (
    EnhancedTokenCounterService,
    SessionTokenMetrics,
    EnhancedTokenAnalysis
)
from src.context_cleaner.analysis.dashboard_integration import DashboardTokenAnalyzer
from .fixtures import UndercountTestCases, JSONLFixtures, MockFileSystem


class TestUndercountDetection:
    """Test comprehensive undercount detection capabilities."""
    
    @pytest.fixture
    def service(self):
        """Create EnhancedTokenCounterService instance."""
        return EnhancedTokenCounterService(anthropic_api_key="test_key")
    
    @pytest.fixture
    def undercount_scenarios(self):
        """Provide all undercount test scenarios."""
        return UndercountTestCases.all_scenarios()
    
    @pytest.mark.asyncio
    async def test_severe_undercount_detection(self, service, tmp_path):
        """Test detection of severe (90%) undercount scenario."""
        # Create conversation that demonstrates severe undercount
        test_file = tmp_path / "severe_undercount.jsonl"
        
        # Simulate current system limitations:
        # - Only counts assistant messages with usage stats
        # - Misses user messages, system prompts, tool usage
        entries = [
            # Large user message - MISSED by current system
            {
                "type": "user",
                "timestamp": datetime.now().isoformat(),
                "session_id": "severe_session",
                "message": {
                    "role": "user",
                    "content": "I need comprehensive help with creating a complex system that processes large amounts of data. " * 50  # Very long content
                }
            },
            # Large system prompt - MISSED by current system
            {
                "type": "system",
                "timestamp": datetime.now().isoformat(),
                "session_id": "severe_session",
                "message": {
                    "role": "system", 
                    "content": "<system-reminder>You are Claude Code with extensive capabilities. " * 30  # Large system context
                }
            },
            # Multiple tool usage - MISSED by current system
            *[{
                "type": "tool_use",
                "timestamp": datetime.now().isoformat(),
                "session_id": "severe_session",
                "message": {
                    "role": "assistant",
                    "content": f"Using tool {i} to process large amounts of data and analyze complex patterns. " * 20
                }
            } for i in range(10)],
            # Small assistant message - ONLY thing counted by current system
            {
                "type": "assistant",
                "timestamp": datetime.now().isoformat(),
                "session_id": "severe_session",
                "message": {
                    "role": "assistant",
                    "content": "I'll help you.",  # Very short response
                    "usage": {
                        "input_tokens": 50,  # Minimal reported tokens
                        "output_tokens": 10,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0
                    }
                }
            }
        ]
        
        with open(test_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        with patch.object(service, 'cache_dir', tmp_path):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False  # Use heuristic estimation
            )
            
            session = analysis.sessions["severe_session"]
            
            # Verify severe undercount is detected
            assert session.total_reported_tokens == 60  # Only assistant message counted
            assert session.calculated_total_tokens > 600  # Much more content found
            assert session.undercount_percentage > 80.0  # Severe undercount
            assert analysis.global_undercount_percentage > 80.0
            
            # Verify content categorization captured missed content
            assert len(session.user_messages) == 1
            assert len(session.assistant_messages) > 10  # Tool usage captured
            assert session.content_categories["user_messages"] > 0
            assert session.content_categories["system_prompts"] > 0
    
    @pytest.mark.asyncio
    async def test_moderate_undercount_detection(self, service, tmp_path):
        """Test detection of moderate (50%) undercount."""
        test_file = tmp_path / "moderate_undercount.jsonl"
        
        entries = [
            # User message - MISSED
            {
                "type": "user",
                "timestamp": datetime.now().isoformat(),
                "session_id": "moderate_session",
                "message": {
                    "role": "user",
                    "content": "Medium length user request. " * 15
                }
            },
            # Assistant with usage - COUNTED
            {
                "type": "assistant",
                "timestamp": datetime.now().isoformat(),
                "session_id": "moderate_session",
                "message": {
                    "role": "assistant",
                    "content": "Medium length response. " * 15,
                    "usage": {
                        "input_tokens": 150,
                        "output_tokens": 75,
                        "cache_creation_input_tokens": 25,
                        "cache_read_input_tokens": 0
                    }
                }
            }
        ]
        
        with open(test_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        with patch.object(service, 'cache_dir', tmp_path):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False
            )
            
            session = analysis.sessions["moderate_session"]
            
            # Verify moderate undercount
            assert session.total_reported_tokens == 250
            assert session.calculated_total_tokens > 400
            assert 30.0 < session.undercount_percentage < 70.0  # Moderate range
    
    @pytest.mark.asyncio
    async def test_accurate_counting_scenario(self, service, tmp_path):
        """Test scenario where counting is relatively accurate (rare case)."""
        test_file = tmp_path / "accurate_session.jsonl"
        
        # Only assistant messages with complete usage stats
        entries = [
            {
                "type": "assistant",
                "timestamp": datetime.now().isoformat(),
                "session_id": "accurate_session",
                "message": {
                    "role": "assistant",
                    "content": "Response content. " * 20,
                    "usage": {
                        "input_tokens": 200,
                        "output_tokens": 80,
                        "cache_creation_input_tokens": 20,
                        "cache_read_input_tokens": 10
                    }
                }
            }
        ]
        
        with open(test_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        with patch.object(service, 'cache_dir', tmp_path):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False
            )
            
            session = analysis.sessions["accurate_session"]
            
            # Verify minimal or no undercount
            assert session.undercount_percentage < 20.0  # Relatively accurate
            assert session.accuracy_ratio < 2.0  # Not drastically different
    
    @pytest.mark.asyncio
    async def test_file_limit_impact_on_undercount(self, service, tmp_path):
        """Test how file processing limits affect undercount detection."""
        # Create 15 files with varying token usage patterns
        reported_tokens_total = 0
        actual_content_files = 0
        
        for i in range(15):
            file_path = tmp_path / f"session_{i:03d}.jsonl"
            
            if i < 10:
                # Files that would be processed by current system (10 most recent)
                entries = [
                    {
                        "type": "assistant",
                        "timestamp": datetime.now().isoformat(),
                        "session_id": f"session_{i:03d}",
                        "message": {
                            "role": "assistant",
                            "content": f"Response {i}",
                            "usage": {"input_tokens": 50, "output_tokens": 20, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
                        }
                    }
                ]
                reported_tokens_total += 70
            else:
                # Files missed by current system due to 10-file limit
                # These contain significant missed token usage
                entries = [
                    {
                        "type": "user",
                        "timestamp": datetime.now().isoformat(),
                        "session_id": f"session_{i:03d}",
                        "message": {
                            "role": "user",
                            "content": f"Large user request with lots of content. " * 30  # Significant content
                        }
                    },
                    {
                        "type": "assistant",
                        "timestamp": datetime.now().isoformat(),
                        "session_id": f"session_{i:03d}",
                        "message": {
                            "role": "assistant",
                            "content": "Small response",
                            "usage": {"input_tokens": 20, "output_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
                        }
                    }
                ]
                actual_content_files += 1
            
            with open(file_path, 'w') as f:
                for entry in entries:
                    f.write(json.dumps(entry) + "\n")
        
        with patch.object(service, 'cache_dir', tmp_path):
            # Test current system limitation (10 files)
            analysis_limited = await service.analyze_comprehensive_token_usage(
                max_files=10,
                use_count_tokens_api=False
            )
            
            # Test enhanced system (all files)
            analysis_enhanced = await service.analyze_comprehensive_token_usage(
                max_files=None,
                use_count_tokens_api=False
            )
            
            # Enhanced system should detect much more content
            assert analysis_enhanced.total_files_processed == 15
            assert analysis_limited.total_files_processed == 10
            
            # Enhanced system should find significantly more tokens
            assert analysis_enhanced.total_calculated_tokens > analysis_limited.total_calculated_tokens
            
            # Enhanced system should detect higher undercount due to more files
            assert analysis_enhanced.global_undercount_percentage > analysis_limited.global_undercount_percentage
    
    @pytest.mark.asyncio
    async def test_line_limit_impact_on_undercount(self, service, tmp_path):
        """Test how line processing limits affect undercount detection."""
        # Create file with 2500 lines (current system only processes first 1000)
        large_file = tmp_path / "large_conversation.jsonl"
        
        entries = []
        reported_tokens = 0
        
        for i in range(2500):
            if i < 1000:
                # Lines processed by current system
                if i % 10 == 0:  # Only some have usage stats
                    entry = {
                        "type": "assistant",
                        "timestamp": datetime.now().isoformat(),
                        "session_id": "large_session",
                        "message": {
                            "role": "assistant",
                            "content": f"Response {i}",
                            "usage": {"input_tokens": 30, "output_tokens": 15, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
                        }
                    }
                    reported_tokens += 45
                else:
                    entry = {
                        "type": "user",
                        "timestamp": datetime.now().isoformat(),
                        "session_id": "large_session",
                        "message": {
                            "role": "user",
                            "content": f"User message {i} with content"
                        }
                    }
            else:
                # Lines missed by current system due to 1000-line limit
                # These represent significant additional conversation content
                entry = {
                    "type": "user" if i % 2 == 0 else "assistant",
                    "timestamp": datetime.now().isoformat(),
                    "session_id": "large_session",
                    "message": {
                        "role": "user" if i % 2 == 0 else "assistant",
                        "content": f"Additional conversation content {i} that would be missed by current system. " * 10
                    }
                }
                if i % 2 == 1 and i % 20 == 1:  # Some assistant messages have usage
                    entry["message"]["usage"] = {"input_tokens": 80, "output_tokens": 40, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
            
            entries.append(entry)
        
        with open(large_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        with patch.object(service, 'cache_dir', tmp_path):
            # Test current system limitation (1000 lines)
            analysis_limited = await service.analyze_comprehensive_token_usage(
                max_lines_per_file=1000,
                use_count_tokens_api=False
            )
            
            # Test enhanced system (all lines)
            analysis_enhanced = await service.analyze_comprehensive_token_usage(
                max_lines_per_file=None,
                use_count_tokens_api=False
            )
            
            # Verify processing differences
            assert analysis_limited.total_lines_processed == 1000
            assert analysis_enhanced.total_lines_processed == 2500
            
            # Enhanced system should find significantly more content
            session_limited = analysis_limited.sessions["large_session"]
            session_enhanced = analysis_enhanced.sessions["large_session"]
            
            assert session_enhanced.calculated_total_tokens > session_limited.calculated_total_tokens
            assert len(session_enhanced.user_messages) > len(session_limited.user_messages)
            assert len(session_enhanced.assistant_messages) > len(session_limited.assistant_messages)
    
    @pytest.mark.asyncio
    async def test_content_type_coverage_impact(self, service, tmp_path):
        """Test how processing all content types affects undercount detection."""
        test_file = tmp_path / "content_types.jsonl" 
        
        entries = [
            # User messages - MISSED by current system
            *[{
                "type": "user",
                "timestamp": datetime.now().isoformat(),
                "session_id": "content_session",
                "message": {
                    "role": "user",
                    "content": f"User message {i} with substantial content explaining requirements. " * 20
                }
            } for i in range(5)],
            
            # System prompts - MISSED by current system
            *[{
                "type": "system",
                "timestamp": datetime.now().isoformat(),
                "session_id": "content_session",
                "message": {
                    "role": "system",
                    "content": f"<system-reminder>System context {i} with detailed instructions. " * 15 + "</system-reminder>"
                }
            } for i in range(3)],
            
            # Tool usage - MISSED by current system
            *[{
                "type": "tool_use",
                "timestamp": datetime.now().isoformat(),
                "session_id": "content_session",
                "message": {
                    "role": "assistant",
                    "content": f"Tool usage {i} with complex function calls and parameters. " * 25
                }
            } for i in range(7)],
            
            # Assistant messages with usage - COUNTED by current system
            *[{
                "type": "assistant",
                "timestamp": datetime.now().isoformat(),
                "session_id": "content_session",
                "message": {
                    "role": "assistant",
                    "content": f"Assistant response {i}",  # Much shorter than other content
                    "usage": {"input_tokens": 25, "output_tokens": 10, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
                }
            } for i in range(2)]
        ]
        
        with open(test_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        with patch.object(service, 'cache_dir', tmp_path):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False
            )
            
            session = analysis.sessions["content_session"]
            
            # Current system would only count 2 assistant messages = 70 tokens
            assert session.total_reported_tokens == 70
            
            # Enhanced system captures all content types
            assert len(session.user_messages) == 5
            assert len(session.assistant_messages) >= 7  # Tool usage + responses
            assert session.content_categories["user_messages"] > 0
            assert session.content_categories["system_prompts"] > 0
            
            # Should detect massive undercount due to missed content types
            assert session.undercount_percentage > 85.0
            assert session.calculated_total_tokens > 1000  # Much more than 70


class TestUndercountComparison:
    """Test direct comparison between current and enhanced approaches."""
    
    @pytest.mark.asyncio
    async def test_current_vs_enhanced_system_comparison(self, tmp_path):
        """Direct comparison of current system vs enhanced system results."""
        # Create realistic conversation data
        conversation_files = []
        
        for session_num in range(12):  # More than current 10-file limit
            file_path = tmp_path / f"conversation_{session_num:02d}.jsonl"
            conversation_files.append(file_path)
            
            # Create conversation with mixed content (realistic scenario)
            entries = []
            
            # User request (substantial content)
            entries.append({
                "type": "user",
                "timestamp": datetime.now().isoformat(),
                "session_id": f"session_{session_num:02d}",
                "message": {
                    "role": "user",
                    "content": f"Complex user request {session_num} with detailed requirements and context. " * 30
                }
            })
            
            # System prompt (substantial context)
            entries.append({
                "type": "system", 
                "timestamp": datetime.now().isoformat(),
                "session_id": f"session_{session_num:02d}",
                "message": {
                    "role": "system",
                    "content": "<system-reminder>Claude Code instructions with comprehensive guidelines. " * 20 + "</system-reminder>"
                }
            })
            
            # Multiple tool uses (significant content)
            for tool_num in range(5):
                entries.append({
                    "type": "tool_use",
                    "timestamp": datetime.now().isoformat(), 
                    "session_id": f"session_{session_num:02d}",
                    "message": {
                        "role": "assistant",
                        "content": f"Tool {tool_num} usage with detailed function call and extensive parameters. " * 20
                    }
                })
            
            # Assistant response (minimal - what current system counts)
            entries.append({
                "type": "assistant",
                "timestamp": datetime.now().isoformat(),
                "session_id": f"session_{session_num:02d}",
                "message": {
                    "role": "assistant", 
                    "content": "Brief response.",
                    "usage": {"input_tokens": 40, "output_tokens": 15, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 0}
                }
            })
            
            with open(file_path, 'w') as f:
                for entry in entries:
                    f.write(json.dumps(entry) + "\n")
        
        # Simulate current system behavior
        service_current = EnhancedTokenCounterService()
        with patch.object(service_current, 'cache_dir', tmp_path):
            current_analysis = await service_current.analyze_comprehensive_token_usage(
                max_files=10,  # Current limitation
                max_lines_per_file=1000,  # Current limitation
                use_count_tokens_api=False
            )
        
        # Enhanced system behavior
        service_enhanced = EnhancedTokenCounterService() 
        with patch.object(service_enhanced, 'cache_dir', tmp_path):
            enhanced_analysis = await service_enhanced.analyze_comprehensive_token_usage(
                max_files=None,  # No file limit
                max_lines_per_file=None,  # No line limit
                use_count_tokens_api=False
            )
        
        # Compare results
        assert enhanced_analysis.total_files_processed > current_analysis.total_files_processed
        assert enhanced_analysis.total_lines_processed > current_analysis.total_lines_processed
        assert enhanced_analysis.total_sessions_analyzed > current_analysis.total_sessions_analyzed
        
        # Enhanced system should find dramatically more tokens
        improvement_factor = enhanced_analysis.total_calculated_tokens / current_analysis.total_calculated_tokens
        assert improvement_factor > 2.0  # At least 2x more tokens found
        
        # Enhanced system should detect higher undercount percentage
        assert enhanced_analysis.global_undercount_percentage > current_analysis.global_undercount_percentage
        
        # Enhanced system should provide more comprehensive analytics
        assert len(enhanced_analysis.sessions) >= len(current_analysis.sessions)
        
        # Verify specific improvements
        improvement_summary = enhanced_analysis.improvement_summary
        assert improvement_summary["enhanced_coverage"]["files_processed"] > 10
        assert improvement_summary["enhanced_coverage"]["lines_processed"] > 10000
    
    @pytest.mark.asyncio
    async def test_dashboard_undercount_reporting(self):
        """Test dashboard reporting of undercount detection."""
        analyzer = DashboardTokenAnalyzer()
        
        # Mock severe undercount scenario
        mock_analysis = EnhancedTokenAnalysis(
            total_sessions_analyzed=5,
            total_files_processed=20,  # vs current 10
            total_lines_processed=50000,  # vs current ~10,000
            total_reported_tokens=500,  # What current system finds
            total_calculated_tokens=5000,  # What enhanced system finds
            global_accuracy_ratio=10.0,  # 10x undercount
            global_undercount_percentage=90.0,  # 90% missed
            api_calls_made=10,
            processing_time_seconds=3.45
        )
        
        with patch.object(analyzer.token_service, 'analyze_comprehensive_token_usage', 
                         return_value=mock_analysis):
            
            result = await analyzer.get_enhanced_token_analysis()
            
            # Verify dashboard reports the undercount prominently
            accuracy = result["analysis_metadata"]["accuracy_improvement"]
            assert accuracy["improvement_factor"] == "10.00x"
            assert accuracy["undercount_percentage"] == "90.0%"
            assert accuracy["missed_tokens"] == 4500  # 5000 - 500
            
            # Verify recommendations highlight the issue
            recommendations = result["recommendations"]
            undercount_warning = any("90.0%" in rec and "undercount" in rec.lower() for rec in recommendations)
            assert undercount_warning
            
            # Verify coverage improvements are reported
            limitations = result["analysis_metadata"]["limitations_removed"]
            assert "20 files" in limitations["files_processed"]
            assert "vs previous 10" in limitations["files_processed"]


class TestUndercountEdgeCases:
    """Test edge cases in undercount detection."""
    
    @pytest.mark.asyncio
    async def test_empty_files_handling(self, tmp_path):
        """Test handling of empty or corrupted JSONL files."""
        service = EnhancedTokenCounterService()
        
        # Create empty file
        empty_file = tmp_path / "empty.jsonl"
        empty_file.touch()
        
        # Create file with invalid JSON
        invalid_file = tmp_path / "invalid.jsonl"
        with open(invalid_file, 'w') as f:
            f.write("invalid json line\n")
            f.write('{"valid": "json"}\n')
            f.write("another invalid line\n")
        
        with patch.object(service, 'cache_dir', tmp_path):
            analysis = await service.analyze_comprehensive_token_usage()
            
            # Should handle errors gracefully
            assert len(analysis.errors_encountered) == 0  # Empty files shouldn't cause errors
            assert analysis.total_files_processed >= 1  # Should process valid entries
    
    @pytest.mark.asyncio 
    async def test_zero_token_scenarios(self, tmp_path):
        """Test scenarios with zero reported tokens."""
        service = EnhancedTokenCounterService()
        
        # File with no usage statistics at all
        test_file = tmp_path / "no_usage.jsonl"
        entries = [
            {
                "type": "user",
                "timestamp": datetime.now().isoformat(),
                "session_id": "no_usage_session",
                "message": {"role": "user", "content": "Message with no usage stats"}
            }
        ]
        
        with open(test_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        with patch.object(service, 'cache_dir', tmp_path):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False
            )
            
            session = analysis.sessions["no_usage_session"]
            
            # Should handle zero reported tokens gracefully
            assert session.total_reported_tokens == 0
            assert session.calculated_total_tokens > 0  # But still estimate content
            # Undercount percentage should be calculated correctly (100% in this case)
            assert session.undercount_percentage == 100.0
    
    @pytest.mark.asyncio
    async def test_extremely_large_undercount(self, tmp_path):
        """Test detection of extremely large undercounts (> 95%)."""
        service = EnhancedTokenCounterService()
        
        test_file = tmp_path / "extreme_undercount.jsonl"
        
        # Create scenario with massive missed content
        entries = [
            # Tiny reported usage
            {
                "type": "assistant",
                "timestamp": datetime.now().isoformat(),
                "session_id": "extreme_session",
                "message": {
                    "role": "assistant",
                    "content": "Ok",  # Minimal content
                    "usage": {"input_tokens": 1, "output_tokens": 1, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
                }
            },
            # Massive missed content
            *[{
                "type": "user",
                "timestamp": datetime.now().isoformat(),
                "session_id": "extreme_session",
                "message": {
                    "role": "user",
                    "content": f"Extremely long user message {i} with enormous amounts of text content that represents significant token usage. " * 100
                }
            } for i in range(50)]
        ]
        
        with open(test_file, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        with patch.object(service, 'cache_dir', tmp_path):
            analysis = await service.analyze_comprehensive_token_usage(
                use_count_tokens_api=False
            )
            
            session = analysis.sessions["extreme_session"]
            
            # Should detect extreme undercount
            assert session.total_reported_tokens == 2  # Minimal
            assert session.calculated_total_tokens > 10000  # Massive
            assert session.undercount_percentage > 95.0  # Extreme undercount


if __name__ == "__main__":
    pytest.main([__file__, "-v"])