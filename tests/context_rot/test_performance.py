"""Performance tests for Context Rot Meter system."""

import pytest
import asyncio
import time
import psutil
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from src.context_cleaner.telemetry.context_rot.analyzer import ContextRotAnalyzer
from src.context_cleaner.telemetry.context_rot.ml_analysis import MLFrustrationDetector, SentimentPipeline
from src.context_cleaner.telemetry.context_rot.adaptive_thresholds import AdaptiveThresholdManager
from src.context_cleaner.telemetry.context_rot.widget import ContextRotWidget
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
from src.context_cleaner.telemetry.error_recovery.manager import ErrorRecoveryManager
from tests.telemetry.conftest import MockTelemetryClient


class TestContextRotPerformance:
    """Performance benchmark tests for Context Rot system."""

    @pytest.fixture
    def mock_clickhouse_client(self):
        """Mock ClickHouse client that simulates realistic response times."""
        client = AsyncMock(spec=ClickHouseClient)
        client.health_check.return_value = True
        
        # Simulate realistic database response times
        async def mock_query(*args, **kwargs):
            await asyncio.sleep(0.01)  # 10ms simulated latency
            return [{'mock': 'data'}]
        
        client.execute_query.side_effect = mock_query
        return client

    @pytest.fixture
    def performance_analyzer(self, mock_clickhouse_client):
        """Create analyzer optimized for performance testing."""
        mock_client = MockTelemetryClient()
        recovery_manager = ErrorRecoveryManager(mock_client, max_retries=3)
        return ContextRotAnalyzer(mock_clickhouse_client, recovery_manager)

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_real_time_analysis_latency(self, performance_analyzer):
        """Test real-time analysis meets latency requirements (<100ms)."""
        test_data = {
            'session_id': 'perf-test-latency',
            'timestamp': datetime.now().isoformat(),
            'user_message': 'This is a test message for performance analysis',
            'context_size': 5000,
            'tools_used': ['Read', 'Edit', 'Bash']
        }
        
        # Warm up
        await performance_analyzer.analyze_realtime(test_data)
        
        # Measure actual performance
        latencies = []
        for i in range(50):
            start_time = time.perf_counter()
            
            result = await performance_analyzer.analyze_realtime({
                **test_data,
                'session_id': f'perf-test-{i}',
                'user_message': f'Test message {i} for performance testing'
            })
            
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
            
            assert result['status'] in ['success', 'warning', 'error']
        
        # Performance assertions
        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(0.95 * len(latencies))]
        max_latency = max(latencies)
        
        print(f"\nReal-time Analysis Performance:")
        print(f"  Average latency: {avg_latency:.2f}ms")
        print(f"  95th percentile: {p95_latency:.2f}ms") 
        print(f"  Maximum latency: {max_latency:.2f}ms")
        
        # Requirements from roadmap: Real-time analysis < 100ms
        assert avg_latency < 100, f"Average latency {avg_latency:.2f}ms exceeds 100ms requirement"
        assert p95_latency < 150, f"95th percentile {p95_latency:.2f}ms too high"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_conversation_analysis_throughput(self, performance_analyzer):
        """Test conversation analysis throughput."""
        conversations = []
        for i in range(20):
            conversation = [
                f"Message {j} in conversation {i}: testing performance analysis"
                for j in range(10)  # 10 messages per conversation
            ]
            conversations.append(conversation)
        
        start_time = time.perf_counter()
        
        # Process conversations concurrently
        tasks = []
        for i, conversation in enumerate(conversations):
            task = performance_analyzer.analyze_conversation_sentiment(f'perf-user-{i}', conversation)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        successful_results = [r for r in results if not isinstance(r, Exception)]
        throughput = len(successful_results) / total_time
        
        print(f"\nConversation Analysis Performance:")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Successful analyses: {len(successful_results)}/{len(conversations)}")
        print(f"  Throughput: {throughput:.2f} conversations/second")
        
        # Should handle multiple conversations efficiently
        assert len(successful_results) >= len(conversations) * 0.9  # 90% success rate
        assert throughput >= 5.0  # At least 5 conversations per second

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_ml_sentiment_analysis_performance(self):
        """Test ML sentiment analysis performance."""
        sentiment_pipeline = SentimentPipeline(confidence_threshold=0.6)
        
        # Generate test messages
        test_messages = [
            f"Test message number {i} with various sentiment content for performance testing"
            for i in range(100)
        ]
        
        # Single message analysis
        start_time = time.perf_counter()
        
        single_results = []
        for message in test_messages:
            result = await sentiment_pipeline.analyze(message)
            single_results.append(result)
        
        single_time = time.perf_counter() - start_time
        
        # Batch analysis
        start_time = time.perf_counter()
        batch_results = await sentiment_pipeline.analyze_batch(test_messages)
        batch_time = time.perf_counter() - start_time
        
        print(f"\nSentiment Analysis Performance:")
        print(f"  Single analysis: {single_time:.2f}s ({single_time/len(test_messages)*1000:.2f}ms per message)")
        print(f"  Batch analysis: {batch_time:.2f}s ({batch_time/len(test_messages)*1000:.2f}ms per message)")
        print(f"  Batch speedup: {single_time/batch_time:.2f}x")
        
        # Batch should be more efficient
        assert batch_time < single_time, "Batch analysis should be faster than individual analysis"
        assert len(batch_results) == len(test_messages)

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_adaptive_thresholds_scaling(self, mock_clickhouse_client):
        """Test adaptive thresholds system scaling."""
        threshold_manager = AdaptiveThresholdManager(mock_clickhouse_client)
        
        # Test scaling with many users
        user_ids = [f'perf-user-{i:04d}' for i in range(100)]
        
        start_time = time.perf_counter()
        
        # Get personalized thresholds for all users concurrently
        tasks = [threshold_manager.get_personalized_thresholds(user_id) for user_id in user_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        successful_results = [r for r in results if not isinstance(r, Exception)]
        
        print(f"\nAdaptive Thresholds Scaling:")
        print(f"  Users processed: {len(successful_results)}/{len(user_ids)}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Rate: {len(successful_results)/total_time:.2f} users/second")
        
        # Should handle many users efficiently
        assert len(successful_results) >= len(user_ids) * 0.95  # 95% success rate
        assert total_time < 5.0  # Complete within 5 seconds

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_widget_data_retrieval_performance(self, mock_clickhouse_client):
        """Test widget data retrieval performance."""
        widget = ContextRotWidget(mock_clickhouse_client)
        
        # Mock large dataset response
        large_dataset = []
        for i in range(1000):
            large_dataset.append({
                'timestamp': f'2024-01-01 {i%24:02d}:{i%60:02d}:00',
                'rot_score': 0.1 + (i % 10) * 0.08,
                'confidence_score': 0.7 + (i % 3) * 0.1,
                'indicator_breakdown': '{"repetition": 0.2, "frustration": 0.3}',
                'analysis_version': 1
            })
        
        mock_clickhouse_client.execute_query.return_value = large_dataset
        
        start_time = time.perf_counter()
        
        widget_data = await widget.get_widget_data(
            session_id='perf-test-widget',
            time_window_minutes=120
        )
        
        end_time = time.perf_counter()
        processing_time = end_time - start_time
        
        print(f"\nWidget Data Retrieval Performance:")
        print(f"  Dataset size: {len(large_dataset)} records")
        print(f"  Processing time: {processing_time:.3f}s")
        print(f"  Rate: {len(large_dataset)/processing_time:.0f} records/second")
        
        # Should process large datasets efficiently
        assert processing_time < 1.0  # Less than 1 second
        assert len(widget_data.data) == len(large_dataset)

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_memory_efficiency_under_load(self, performance_analyzer):
        """Test memory efficiency under sustained load."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Sustained load test
        for batch in range(10):
            tasks = []
            
            # Create 20 concurrent analyses per batch
            for i in range(20):
                test_data = {
                    'session_id': f'memory-test-{batch}-{i}',
                    'timestamp': datetime.now().isoformat(),
                    'user_message': 'Memory efficiency test message ' * 50,  # Larger message
                    'context_size': 10000,
                    'tools_used': ['Read', 'Edit', 'Bash', 'Grep', 'TodoWrite']
                }
                task = performance_analyzer.analyze_realtime(test_data)
                tasks.append(task)
            
            # Wait for batch completion
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check memory usage
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_growth = current_memory - initial_memory
            
            print(f"  Batch {batch + 1}: Memory usage {current_memory:.1f}MB (growth: {memory_growth:.1f}MB)")
            
            # Memory growth should be bounded
            assert memory_growth < 100, f"Memory growth {memory_growth:.1f}MB exceeds limit"
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_growth = final_memory - initial_memory
        
        print(f"\nMemory Efficiency Test:")
        print(f"  Initial memory: {initial_memory:.1f}MB")
        print(f"  Final memory: {final_memory:.1f}MB")
        print(f"  Total growth: {total_growth:.1f}MB")
        
        # Total memory growth should be reasonable
        assert total_growth < 150, f"Total memory growth {total_growth:.1f}MB exceeds limit"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_user_analysis(self, performance_analyzer):
        """Test system performance with concurrent users."""
        # Simulate 50 concurrent users
        user_count = 50
        messages_per_user = 5
        
        async def simulate_user_session(user_id: str):
            """Simulate a user session with multiple analyses."""
            results = []
            
            for i in range(messages_per_user):
                test_data = {
                    'session_id': f'{user_id}-session',
                    'timestamp': datetime.now().isoformat(),
                    'user_message': f'User {user_id} message {i}: testing concurrent analysis',
                    'context_size': 3000 + i * 500,
                    'tools_used': ['Read', 'Edit']
                }
                
                result = await performance_analyzer.analyze_realtime(test_data)
                results.append(result)
                
                # Small delay between messages
                await asyncio.sleep(0.01)
            
            return results
        
        start_time = time.perf_counter()
        
        # Create concurrent user sessions
        user_tasks = [
            simulate_user_session(f'concurrent-user-{i:03d}')
            for i in range(user_count)
        ]
        
        user_results = await asyncio.gather(*user_tasks, return_exceptions=True)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Analyze results
        successful_sessions = [r for r in user_results if not isinstance(r, Exception)]
        total_analyses = sum(len(session) for session in successful_sessions)
        
        print(f"\nConcurrent User Performance:")
        print(f"  Users: {user_count}")
        print(f"  Successful sessions: {len(successful_sessions)}")
        print(f"  Total analyses: {total_analyses}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Rate: {total_analyses/total_time:.2f} analyses/second")
        
        # Performance requirements
        assert len(successful_sessions) >= user_count * 0.9  # 90% success rate
        assert total_analyses/total_time >= 50  # At least 50 analyses per second

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_error_recovery_performance(self, mock_clickhouse_client):
        """Test performance impact of error recovery mechanisms."""
        # Create analyzer with error-prone client
        error_prone_client = AsyncMock(spec=ClickHouseClient)
        error_prone_client.health_check.return_value = True
        
        # Simulate intermittent failures (30% failure rate)
        call_count = 0
        async def failing_query(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Every 3rd call fails
                raise Exception("Simulated database error")
            await asyncio.sleep(0.01)  # Normal latency
            return [{'mock': 'data'}]
        
        error_prone_client.execute_query.side_effect = failing_query
        
        mock_telemetry_client = MockTelemetryClient()
        recovery_manager = ErrorRecoveryManager(mock_telemetry_client, max_retries=3)
        analyzer = ContextRotAnalyzer(error_prone_client, recovery_manager)
        
        start_time = time.perf_counter()
        
        # Run analyses with error recovery
        tasks = []
        for i in range(30):
            test_data = {
                'session_id': f'error-recovery-{i}',
                'timestamp': datetime.now().isoformat(),
                'user_message': f'Error recovery test message {i}',
                'context_size': 4000
            }
            task = analyzer.analyze_realtime(test_data)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        successful_results = [r for r in results if not isinstance(r, Exception)]
        
        print(f"\nError Recovery Performance:")
        print(f"  Total requests: {len(tasks)}")
        print(f"  Successful: {len(successful_results)}")
        print(f"  Total time with recovery: {total_time:.2f}s")
        print(f"  Average time per request: {total_time/len(tasks)*1000:.0f}ms")
        
        # Should recover from most errors
        assert len(successful_results) >= len(tasks) * 0.7  # 70% success rate with 30% failures


class TestContextRotStressTests:
    """Stress tests for Context Rot system limits."""

    @pytest.mark.performance
    @pytest.mark.stress
    @pytest.mark.asyncio
    async def test_sustained_high_load(self, mock_clickhouse_client):
        """Test system under sustained high load."""
        mock_telemetry_client = MockTelemetryClient()
        recovery_manager = ErrorRecoveryManager(mock_telemetry_client, max_retries=3)
        analyzer = ContextRotAnalyzer(mock_clickhouse_client, recovery_manager)
        
        # Run for 30 seconds with high request rate
        duration = 30  # seconds
        target_rps = 20  # requests per second
        
        start_time = time.perf_counter()
        request_count = 0
        
        while time.perf_counter() - start_time < duration:
            batch_start = time.perf_counter()
            
            # Create batch of requests
            batch_size = min(10, target_rps)  # Batch size
            tasks = []
            
            for i in range(batch_size):
                test_data = {
                    'session_id': f'stress-test-{request_count + i}',
                    'timestamp': datetime.now().isoformat(),
                    'user_message': f'Stress test message {request_count + i}',
                    'context_size': 3000
                }
                task = analyzer.analyze_realtime(test_data)
                tasks.append(task)
            
            # Execute batch
            await asyncio.gather(*tasks, return_exceptions=True)
            request_count += batch_size
            
            # Rate limiting to maintain target RPS
            batch_time = time.perf_counter() - batch_start
            sleep_time = max(0, 1.0 - batch_time)  # Target 1 batch per second
            await asyncio.sleep(sleep_time)
        
        total_time = time.perf_counter() - start_time
        actual_rps = request_count / total_time
        
        print(f"\nSustained Load Test:")
        print(f"  Duration: {total_time:.1f}s")
        print(f"  Requests: {request_count}")
        print(f"  Actual RPS: {actual_rps:.1f}")
        print(f"  Target RPS: {target_rps}")
        
        # System should maintain reasonable performance
        assert actual_rps >= target_rps * 0.8  # Within 80% of target

    @pytest.mark.performance
    @pytest.mark.stress
    @pytest.mark.asyncio
    async def test_memory_stability_long_running(self, mock_clickhouse_client):
        """Test memory stability over extended runtime."""
        analyzer = ContextRotAnalyzer(
            mock_clickhouse_client, 
            ErrorRecoveryManager(MockTelemetryClient(), max_retries=3)
        )
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        memory_samples = []
        
        # Run for 5 minutes with periodic sampling
        runtime = 5 * 60  # 5 minutes
        sample_interval = 30  # 30 seconds
        
        start_time = time.perf_counter()
        
        while time.perf_counter() - start_time < runtime:
            # Process requests for sample interval
            interval_start = time.perf_counter()
            
            while time.perf_counter() - interval_start < sample_interval:
                test_data = {
                    'session_id': f'memory-stability-{int(time.time())}',
                    'timestamp': datetime.now().isoformat(),
                    'user_message': 'Memory stability test message',
                    'context_size': 5000
                }
                
                await analyzer.analyze_realtime(test_data)
                await asyncio.sleep(0.1)  # 10 requests per second
            
            # Sample memory usage
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_samples.append(current_memory)
            
            elapsed = time.perf_counter() - start_time
            print(f"  {elapsed/60:.1f}min: {current_memory:.1f}MB")
        
        # Analyze memory stability
        final_memory = memory_samples[-1]
        max_memory = max(memory_samples)
        memory_growth = final_memory - initial_memory
        
        print(f"\nMemory Stability Test:")
        print(f"  Initial: {initial_memory:.1f}MB")
        print(f"  Final: {final_memory:.1f}MB")
        print(f"  Maximum: {max_memory:.1f}MB") 
        print(f"  Growth: {memory_growth:.1f}MB")
        
        # Memory should be stable (no significant leaks)
        assert memory_growth < 50, f"Memory growth {memory_growth:.1f}MB indicates leak"
        assert max_memory - initial_memory < 100, f"Peak memory usage too high"


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-m", "performance"])