"""
Response Optimization Middleware and Utilities

Provides gzip compression, streaming responses, optimized JSON serialization,
and performance enhancements for high-throughput dashboard APIs.
"""

import gzip
import json
import asyncio
import logging
from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union, AsyncGenerator, Callable
from io import BytesIO

from fastapi import Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
import orjson


logger = logging.getLogger(__name__)


class HighPerformanceJSONEncoder:
    """Optimized JSON encoder for dashboard data with custom serializers"""

    @staticmethod
    def encode(obj: Any) -> bytes:
        """Fast JSON encoding with custom type handlers"""
        return orjson.dumps(
            obj,
            default=HighPerformanceJSONEncoder._serialize_custom_types,
            option=orjson.OPT_UTC_Z | orjson.OPT_SERIALIZE_NUMPY
        )

    @staticmethod
    def _serialize_custom_types(obj: Any) -> Any:
        """Handle custom types for JSON serialization"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, time):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, 'dict'):  # Pydantic models
            return obj.dict()
        elif hasattr(obj, 'to_dict'):  # Custom to_dict method
            return obj.to_dict()
        elif hasattr(obj, '__dict__'):  # Generic objects
            return obj.__dict__
        else:
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class OptimizedJSONResponse(JSONResponse):
    """Optimized JSON response with high-performance encoding"""

    def render(self, content: Any) -> bytes:
        """Render content with optimized JSON encoder"""
        if content is None:
            return b""

        try:
            return HighPerformanceJSONEncoder.encode(content)
        except Exception as e:
            logger.error(f"JSON encoding error: {e}")
            # Fallback to standard JSON
            return json.dumps(content, default=str, separators=(',', ':')).encode('utf-8')


class CompressionMiddleware(BaseHTTPMiddleware):
    """Advanced compression middleware with intelligent compression strategies"""

    def __init__(
        self,
        app,
        minimum_size: int = 500,
        compression_level: int = 6,
        exclude_paths: List[str] = None,
        compress_media_types: List[str] = None
    ):
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level
        self.exclude_paths = exclude_paths or []
        self.compress_media_types = compress_media_types or [
            'application/json',
            'text/plain',
            'text/html',
            'text/css',
            'text/javascript',
            'application/javascript'
        ]

        # Compression stats
        self.stats = {
            'total_requests': 0,
            'compressed_responses': 0,
            'bytes_saved': 0,
            'compression_time_ms': 0
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with intelligent compression"""
        self.stats['total_requests'] += 1

        # Skip compression for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Check if client accepts gzip
        accept_encoding = request.headers.get('accept-encoding', '')
        if 'gzip' not in accept_encoding.lower():
            return await call_next(request)

        response = await call_next(request)

        # Only compress if response is large enough and media type is compressible
        should_compress = (
            hasattr(response, 'body') and
            len(response.body) >= self.minimum_size and
            self._should_compress_media_type(response)
        )

        if should_compress:
            start_time = datetime.now()

            # Compress response body
            compressed_body = self._compress_body(response.body)

            # Update stats
            compression_time = (datetime.now() - start_time).total_seconds() * 1000
            self.stats['compression_time_ms'] += compression_time
            self.stats['compressed_responses'] += 1
            self.stats['bytes_saved'] += len(response.body) - len(compressed_body)

            # Create new response with compressed body
            compressed_response = Response(
                content=compressed_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )

            compressed_response.headers['content-encoding'] = 'gzip'
            compressed_response.headers['content-length'] = str(len(compressed_body))

            # Remove original content-length if present
            if 'content-length' in response.headers:
                del compressed_response.headers['content-length']
                compressed_response.headers['content-length'] = str(len(compressed_body))

            logger.debug(f"Compressed response: {len(response.body)} -> {len(compressed_body)} bytes")
            return compressed_response

        return response

    def _should_compress_media_type(self, response: Response) -> bool:
        """Check if response media type should be compressed"""
        if not hasattr(response, 'media_type') or not response.media_type:
            return False

        return any(
            media_type in response.media_type
            for media_type in self.compress_media_types
        )

    def _compress_body(self, body: bytes) -> bytes:
        """Compress response body with gzip"""
        buffer = BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=self.compression_level) as gzip_file:
            gzip_file.write(body)
        return buffer.getvalue()

    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics"""
        compression_ratio = 0.0
        if self.stats['compressed_responses'] > 0:
            avg_compression_time = self.stats['compression_time_ms'] / self.stats['compressed_responses']
        else:
            avg_compression_time = 0.0

        if self.stats['total_requests'] > 0:
            compression_ratio = (self.stats['compressed_responses'] / self.stats['total_requests']) * 100

        return {
            'total_requests': self.stats['total_requests'],
            'compressed_responses': self.stats['compressed_responses'],
            'compression_ratio_percent': round(compression_ratio, 2),
            'bytes_saved': self.stats['bytes_saved'],
            'average_compression_time_ms': round(avg_compression_time, 2),
            'minimum_size_threshold': self.minimum_size,
            'compression_level': self.compression_level
        }


class StreamingDataProcessor:
    """High-performance streaming data processor for large datasets"""

    @staticmethod
    async def stream_json_array(
        data_generator: AsyncGenerator[Dict[str, Any], None],
        chunk_size: int = 100,
        include_metadata: bool = True
    ) -> AsyncGenerator[str, None]:
        """Stream JSON array data in chunks"""

        # Stream opening
        yield '{"data":['

        first_item = True
        item_count = 0
        chunk_buffer = []

        async for item in data_generator:
            if not first_item:
                chunk_buffer.append(',')
            else:
                first_item = False

            # Encode item to JSON
            try:
                json_item = HighPerformanceJSONEncoder.encode(item).decode('utf-8')
                chunk_buffer.append(json_item)
                item_count += 1

                # Yield chunk when buffer is full
                if len(chunk_buffer) >= chunk_size * 2:  # *2 for commas
                    yield ''.join(chunk_buffer)
                    chunk_buffer = []

            except Exception as e:
                logger.error(f"Error encoding item for streaming: {e}")
                continue

        # Yield remaining buffer
        if chunk_buffer:
            yield ''.join(chunk_buffer)

        # Stream closing with metadata
        yield ']'

        if include_metadata:
            metadata = {
                'total_count': item_count,
                'streamed_at': datetime.now().isoformat(),
                'chunk_size': chunk_size
            }
            metadata_json = HighPerformanceJSONEncoder.encode(metadata).decode('utf-8')
            yield f',"metadata":{metadata_json}'

        yield '}'

    @staticmethod
    async def stream_csv_data(
        data_generator: AsyncGenerator[Dict[str, Any], None],
        headers: List[str] = None
    ) -> AsyncGenerator[str, None]:
        """Stream CSV data for large exports"""

        # Determine headers from first item if not provided
        first_item = None
        if headers is None:
            try:
                first_item = await data_generator.__anext__()
                headers = list(first_item.keys()) if first_item else []
            except StopAsyncIteration:
                headers = []

        # Yield CSV headers
        if headers:
            yield ','.join(headers) + '\n'

        # Process first item if we read it for headers
        if first_item:
            yield StreamingDataProcessor._dict_to_csv_row(first_item, headers) + '\n'

        # Stream remaining data
        async for item in data_generator:
            try:
                csv_row = StreamingDataProcessor._dict_to_csv_row(item, headers)
                yield csv_row + '\n'
            except Exception as e:
                logger.error(f"Error converting item to CSV: {e}")
                continue

    @staticmethod
    def _dict_to_csv_row(data: Dict[str, Any], headers: List[str]) -> str:
        """Convert dictionary to CSV row"""
        values = []
        for header in headers:
            value = data.get(header, '')
            # Escape CSV special characters
            if isinstance(value, str) and (',' in value or '"' in value or '\n' in value):
                value = f'"{value.replace("""", """""")}"'
            values.append(str(value))
        return ','.join(values)


class ResponseStreamFactory:
    """Factory for creating optimized streaming responses"""

    @staticmethod
    def create_json_stream(
        data_generator: AsyncGenerator[Dict[str, Any], None],
        chunk_size: int = 100,
        filename: Optional[str] = None
    ) -> StreamingResponse:
        """Create streaming JSON response"""

        content_generator = StreamingDataProcessor.stream_json_array(
            data_generator, chunk_size=chunk_size
        )

        headers = {'Content-Type': 'application/json'}
        if filename:
            headers['Content-Disposition'] = f'attachment; filename="{filename}"'

        return StreamingResponse(
            content_generator,
            media_type='application/json',
            headers=headers
        )

    @staticmethod
    def create_csv_stream(
        data_generator: AsyncGenerator[Dict[str, Any], None],
        headers: List[str] = None,
        filename: Optional[str] = None
    ) -> StreamingResponse:
        """Create streaming CSV response"""

        content_generator = StreamingDataProcessor.stream_csv_data(
            data_generator, headers=headers
        )

        response_headers = {'Content-Type': 'text/csv'}
        if filename:
            response_headers['Content-Disposition'] = f'attachment; filename="{filename}"'

        return StreamingResponse(
            content_generator,
            media_type='text/csv',
            headers=response_headers
        )

    @staticmethod
    def create_chunked_json_response(
        data: List[Dict[str, Any]],
        chunk_size: int = 1000
    ) -> StreamingResponse:
        """Create chunked JSON response for large in-memory datasets"""

        async def chunk_generator():
            # Process data in chunks
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]

                if i == 0:
                    # First chunk with opening
                    chunk_json = HighPerformanceJSONEncoder.encode({
                        'data': chunk,
                        'chunk_info': {
                            'chunk_index': i // chunk_size,
                            'chunk_size': len(chunk),
                            'total_chunks': (len(data) + chunk_size - 1) // chunk_size
                        }
                    }).decode('utf-8')
                else:
                    # Subsequent chunks
                    chunk_json = HighPerformanceJSONEncoder.encode({
                        'data': chunk,
                        'chunk_info': {
                            'chunk_index': i // chunk_size,
                            'chunk_size': len(chunk),
                            'total_chunks': (len(data) + chunk_size - 1) // chunk_size
                        }
                    }).decode('utf-8')

                yield chunk_json

                # Add small delay to prevent overwhelming the client
                await asyncio.sleep(0.001)

        return StreamingResponse(
            chunk_generator(),
            media_type='application/json'
        )


class PerformanceMetrics:
    """Track response optimization performance metrics"""

    def __init__(self):
        self.metrics = {
            'json_encoding_time_ms': 0,
            'responses_optimized': 0,
            'total_response_size_bytes': 0,
            'streaming_responses': 0,
            'chunked_responses': 0,
            'average_serialization_time_ms': 0
        }

    def record_json_encoding(self, time_ms: float, size_bytes: int):
        """Record JSON encoding performance"""
        self.metrics['json_encoding_time_ms'] += time_ms
        self.metrics['responses_optimized'] += 1
        self.metrics['total_response_size_bytes'] += size_bytes

        # Update average
        self.metrics['average_serialization_time_ms'] = (
            self.metrics['json_encoding_time_ms'] / self.metrics['responses_optimized']
        )

    def record_streaming_response(self):
        """Record streaming response usage"""
        self.metrics['streaming_responses'] += 1

    def record_chunked_response(self):
        """Record chunked response usage"""
        self.metrics['chunked_responses'] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            'optimization_metrics': dict(self.metrics),
            'total_optimized_responses': (
                self.metrics['responses_optimized'] +
                self.metrics['streaming_responses'] +
                self.metrics['chunked_responses']
            ),
            'average_response_size_kb': round(
                self.metrics['total_response_size_bytes'] /
                max(self.metrics['responses_optimized'], 1) / 1024, 2
            )
        }


# Global performance metrics instance
performance_metrics = PerformanceMetrics()


# Utility functions for easy integration
def create_optimized_response(
    data: Any,
    use_streaming: bool = False,
    chunk_size: int = 1000
) -> Union[OptimizedJSONResponse, StreamingResponse]:
    """Create optimized response based on data characteristics"""

    start_time = datetime.now()

    # Determine if we should use streaming based on data size
    if use_streaming and isinstance(data, list) and len(data) > chunk_size:
        performance_metrics.record_streaming_response()
        return ResponseStreamFactory.create_chunked_json_response(data, chunk_size)

    # Use optimized JSON response
    response = OptimizedJSONResponse(content=data)

    # Record performance metrics
    encoding_time = (datetime.now() - start_time).total_seconds() * 1000
    response_size = len(response.body) if hasattr(response, 'body') else 0
    performance_metrics.record_json_encoding(encoding_time, response_size)

    return response


async def health_check() -> Dict[str, Any]:
    """Health check for response optimization components"""
    try:
        # Test JSON encoding
        test_data = {"test": "data", "timestamp": datetime.now()}
        encoded = HighPerformanceJSONEncoder.encode(test_data)

        return {
            'response_optimization_healthy': True,
            'json_encoder_working': len(encoded) > 0,
            'performance_metrics': performance_metrics.get_stats(),
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Response optimization health check failed: {e}")
        return {
            'response_optimization_healthy': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }