from typing import Any, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class APIResponseFormatter:
    """Standardized API response formatting for consistent frontend consumption."""
    
    @staticmethod
    def success(data: Any, message: str = None) -> Dict[str, Any]:
        """Format successful API response."""
        return {
            "status": "success",
            "data": data,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "error": None
        }
    
    @staticmethod
    def error(message: str, error_code: str = None, data: Any = None, status_code: int = 500) -> Dict[str, Any]:
        """Format error API response."""
        return {
            "status": "error",
            "data": data,
            "message": message,
            "error_code": error_code,
            "timestamp": datetime.now().isoformat(),
            "error": message
        }
    
    @staticmethod
    def degraded(data: Any, message: str, warning_code: str = None) -> Dict[str, Any]:
        """Format degraded service response with partial data."""
        return {
            "status": "degraded",
            "data": data,
            "message": message,
            "warning_code": warning_code,
            "timestamp": datetime.now().isoformat(),
            "error": None
        }
    
    @staticmethod
    def loading(message: str = "Loading...", progress: float = None) -> Dict[str, Any]:
        """Format loading state response."""
        return {
            "status": "loading",
            "data": None,
            "message": message,
            "progress": progress,
            "timestamp": datetime.now().isoformat(),
            "error": None
        }

    @staticmethod
    def validate_and_format(data: Any, expected_schema: Dict = None) -> Dict[str, Any]:
        """Validate data against schema and format response."""
        if expected_schema:
            try:
                # Basic schema validation
                if isinstance(expected_schema, dict) and isinstance(data, dict):
                    for required_field in expected_schema.get('required', []):
                        if required_field not in data:
                            return APIResponseFormatter.error(
                                f"Missing required field: {required_field}",
                                error_code="INVALID_SCHEMA"
                            )
                return APIResponseFormatter.success(data)
            except Exception as e:
                logger.error(f"Schema validation error: {e}")
                return APIResponseFormatter.error(
                    "Data validation failed",
                    error_code="VALIDATION_ERROR"
                )
        else:
            return APIResponseFormatter.success(data)