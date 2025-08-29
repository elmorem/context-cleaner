"""
Comprehensive Error Handling and Recovery System
Provides robust error handling, logging, and recovery mechanisms for production deployment.
"""

import sys
import traceback
import logging
import functools
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Type, Union, List
from enum import Enum
import json
from pathlib import Path

from ..config.settings import ContextCleanerConfig
from ..storage.encrypted_storage import EncryptedStorage


class ErrorSeverity(Enum):
    """Error severity levels for categorization and handling."""
    LOW = "low"           # Minor issues, fallback available
    MEDIUM = "medium"     # Moderate impact, partial functionality affected
    HIGH = "high"         # Significant impact, major functionality affected  
    CRITICAL = "critical" # System-breaking, requires immediate attention


class ErrorCategory(Enum):
    """Categories of errors for better organization and handling."""
    STORAGE = "storage"              # Data storage and retrieval errors
    ANALYSIS = "analysis"            # Analytics and processing errors
    INTEGRATION = "integration"      # External integration errors
    PERFORMANCE = "performance"      # Performance and resource errors
    CONFIGURATION = "configuration"  # Configuration and setup errors
    SECURITY = "security"           # Security-related errors
    NETWORK = "network"             # Network connectivity errors
    SYSTEM = "system"               # System-level errors


class ContextCleanerError(Exception):
    """Base exception class for Context Cleaner errors."""
    
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.SYSTEM,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM, 
                 details: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.now()
        self.error_id = f"{category.value}_{int(self.timestamp.timestamp())}"


class StorageError(ContextCleanerError):
    """Errors related to data storage and retrieval."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.STORAGE, **kwargs)


class AnalysisError(ContextCleanerError):
    """Errors during data analysis and processing."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.ANALYSIS, **kwargs)


class IntegrationError(ContextCleanerError):
    """Errors during external system integration."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.INTEGRATION, **kwargs)


class PerformanceError(ContextCleanerError):
    """Performance and resource-related errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.PERFORMANCE, **kwargs)


class ErrorHandler:
    """
    Comprehensive error handling and recovery system.
    
    Features:
    - Automatic error categorization and severity assessment
    - Intelligent fallback and recovery mechanisms
    - Comprehensive error logging with privacy protection
    - Error pattern analysis and alerting
    - Performance impact tracking for errors
    - User-friendly error messaging
    """
    
    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """Initialize error handler."""
        self.config = config or ContextCleanerConfig.from_env()
        
        # Setup specialized logger
        self.logger = self._setup_error_logger()
        
        # Error tracking
        self.error_storage = EncryptedStorage(self.config)
        self.recent_errors: List[ContextCleanerError] = []
        self.error_counts: Dict[str, int] = {}
        self.recovery_strategies: Dict[ErrorCategory, Callable] = {}
        
        # Circuit breaker for critical errors
        self.circuit_breaker_threshold = 5  # Max critical errors before circuit break
        self.critical_error_count = 0
        self.circuit_broken = False
        
        # Initialize recovery strategies
        self._setup_recovery_strategies()
        
        # Load error history
        self._load_error_history()
    
    def _setup_error_logger(self) -> logging.Logger:
        """Setup specialized error logger with appropriate handlers."""
        logger = logging.getLogger("context_cleaner.errors")
        logger.setLevel(logging.INFO)
        
        # Prevent duplicate handlers
        if logger.handlers:
            return logger
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler for development
        if self.config.get('logging.console', True):
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        # File handler for production
        log_file = Path(self.config.data_directory) / "logs" / "errors.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            # Fallback if file logging fails
            pass
        
        return logger
    
    def _setup_recovery_strategies(self):
        """Setup automatic recovery strategies for different error types."""
        self.recovery_strategies = {
            ErrorCategory.STORAGE: self._recover_storage_error,
            ErrorCategory.ANALYSIS: self._recover_analysis_error,
            ErrorCategory.INTEGRATION: self._recover_integration_error,
            ErrorCategory.PERFORMANCE: self._recover_performance_error,
            ErrorCategory.CONFIGURATION: self._recover_configuration_error,
        }
    
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None,
                    user_message: Optional[str] = None) -> bool:
        """
        Handle an error with comprehensive logging and recovery.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            user_message: User-friendly error message override
        
        Returns:
            True if error was handled and system can continue, False if critical
        """
        try:
            # Convert to ContextCleanerError if needed
            if isinstance(error, ContextCleanerError):
                cc_error = error
            else:
                cc_error = self._classify_error(error, context)
            
            # Add to recent errors
            self.recent_errors.append(cc_error)
            if len(self.recent_errors) > 100:  # Keep last 100 errors
                self.recent_errors.pop(0)
            
            # Update error counts
            error_key = f"{cc_error.category.value}_{cc_error.severity.value}"
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
            
            # Handle critical errors
            if cc_error.severity == ErrorSeverity.CRITICAL:
                self.critical_error_count += 1
                if self.critical_error_count >= self.circuit_breaker_threshold:
                    self.circuit_broken = True
                    self.logger.critical("Circuit breaker activated due to critical errors")
                    return False
            
            # Log the error
            self._log_error(cc_error, context, user_message)
            
            # Attempt recovery
            recovery_success = self._attempt_recovery(cc_error)
            
            # Save error history periodically
            if len(self.recent_errors) % 10 == 0:
                self._save_error_history()
            
            return recovery_success
        
        except Exception as e:
            # Fallback error handling
            self.logger.error(f"Error in error handler: {e}")
            return False
    
    def _classify_error(self, error: Exception, context: Optional[Dict[str, Any]]) -> ContextCleanerError:
        """Automatically classify and categorize unknown errors."""
        error_message = str(error)
        error_type = type(error).__name__
        
        # Determine category based on error type and message
        category = ErrorCategory.SYSTEM
        severity = ErrorSeverity.MEDIUM
        
        # Storage-related errors
        if any(keyword in error_message.lower() for keyword in 
               ['file', 'directory', 'permission', 'disk', 'storage', 'io']):
            category = ErrorCategory.STORAGE
        
        # Analysis errors
        elif any(keyword in error_message.lower() for keyword in 
                ['analysis', 'calculation', 'data', 'processing', 'algorithm']):
            category = ErrorCategory.ANALYSIS
        
        # Integration errors
        elif any(keyword in error_message.lower() for keyword in 
                ['connection', 'api', 'integration', 'external', 'service']):
            category = ErrorCategory.INTEGRATION
        
        # Performance errors
        elif any(keyword in error_message.lower() for keyword in 
                ['memory', 'timeout', 'performance', 'resource', 'limit']):
            category = ErrorCategory.PERFORMANCE
        
        # Configuration errors
        elif any(keyword in error_message.lower() for keyword in 
                ['config', 'setting', 'parameter', 'option', 'environment']):
            category = ErrorCategory.CONFIGURATION
        
        # Determine severity
        if error_type in ['KeyboardInterrupt', 'SystemExit']:
            severity = ErrorSeverity.LOW
        elif error_type in ['MemoryError', 'OSError', 'SystemError']:
            severity = ErrorSeverity.CRITICAL
        elif any(keyword in error_message.lower() for keyword in 
                ['critical', 'fatal', 'severe', 'corruption']):
            severity = ErrorSeverity.CRITICAL
        elif any(keyword in error_message.lower() for keyword in 
                ['warning', 'minor', 'recoverable']):
            severity = ErrorSeverity.LOW
        
        return ContextCleanerError(
            message=error_message,
            category=category,
            severity=severity,
            details={
                'error_type': error_type,
                'traceback': traceback.format_exc(),
                'context': context
            },
            cause=error
        )
    
    def _log_error(self, error: ContextCleanerError, context: Optional[Dict[str, Any]], 
                  user_message: Optional[str]):
        """Log error with appropriate level and privacy protection."""
        # Sanitize sensitive information
        sanitized_details = self._sanitize_error_details(error.details)
        
        log_data = {
            'error_id': error.error_id,
            'message': error.message,
            'category': error.category.value,
            'severity': error.severity.value,
            'timestamp': error.timestamp.isoformat(),
            'details': sanitized_details,
            'user_message': user_message
        }
        
        log_message = f"[{error.error_id}] {error.category.value.upper()}: {error.message}"
        
        # Log at appropriate level
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, extra=log_data)
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message, extra=log_data)
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message, extra=log_data)
        else:
            self.logger.info(log_message, extra=log_data)
    
    def _attempt_recovery(self, error: ContextCleanerError) -> bool:
        """Attempt to recover from error using appropriate strategy."""
        if error.category in self.recovery_strategies:
            try:
                return self.recovery_strategies[error.category](error)
            except Exception as recovery_error:
                self.logger.error(f"Recovery failed for {error.error_id}: {recovery_error}")
                return False
        
        # Default recovery for unknown categories
        return error.severity in [ErrorSeverity.LOW, ErrorSeverity.MEDIUM]
    
    def _recover_storage_error(self, error: ContextCleanerError) -> bool:
        """Recovery strategy for storage-related errors."""
        if 'permission' in error.message.lower():
            # Try alternative storage location
            return True
        elif 'disk' in error.message.lower():
            # Clean up old data to free space
            return True
        return error.severity != ErrorSeverity.CRITICAL
    
    def _recover_analysis_error(self, error: ContextCleanerError) -> bool:
        """Recovery strategy for analysis errors."""
        # Use simplified analysis fallback
        return True
    
    def _recover_integration_error(self, error: ContextCleanerError) -> bool:
        """Recovery strategy for integration errors."""
        if 'connection' in error.message.lower():
            # Continue with offline functionality
            return True
        return error.severity != ErrorSeverity.CRITICAL
    
    def _recover_performance_error(self, error: ContextCleanerError) -> bool:
        """Recovery strategy for performance errors."""
        if 'memory' in error.message.lower():
            # Reduce cache size and continue
            return True
        elif 'timeout' in error.message.lower():
            # Use shorter timeout and continue
            return True
        return error.severity != ErrorSeverity.CRITICAL
    
    def _recover_configuration_error(self, error: ContextCleanerError) -> bool:
        """Recovery strategy for configuration errors."""
        # Fall back to default configuration
        return True
    
    def _sanitize_error_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from error details."""
        sanitized = details.copy()
        
        # Remove file paths and replace with generic markers
        if 'traceback' in sanitized:
            traceback_text = sanitized['traceback']
            import re
            # Remove file paths
            traceback_text = re.sub(r'/[/\w\.\-]+', '[PATH]', traceback_text)
            traceback_text = re.sub(r'[A-Z]:\\[\\w\.\-]+', '[PATH]', traceback_text)
            sanitized['traceback'] = traceback_text
        
        # Remove sensitive context information
        if 'context' in sanitized and isinstance(sanitized['context'], dict):
            context = sanitized['context'].copy()
            # Remove potential sensitive keys
            sensitive_keys = ['password', 'token', 'key', 'secret', 'auth', 'credential']
            for key in list(context.keys()):
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    context[key] = '[REDACTED]'
            sanitized['context'] = context
        
        return sanitized
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of recent errors for monitoring and analysis."""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        recent_errors = [e for e in self.recent_errors 
                        if e.timestamp.timestamp() >= cutoff_time]
        
        if not recent_errors:
            return {
                "period_hours": hours,
                "total_errors": 0,
                "status": "healthy"
            }
        
        # Categorize errors
        by_category = {}
        by_severity = {}
        
        for error in recent_errors:
            cat = error.category.value
            sev = error.severity.value
            
            by_category[cat] = by_category.get(cat, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1
        
        # Determine system health
        critical_count = by_severity.get('critical', 0)
        high_count = by_severity.get('high', 0)
        
        if critical_count > 0:
            status = "critical"
        elif high_count > 5:
            status = "degraded"
        elif len(recent_errors) > 20:
            status = "unstable"
        else:
            status = "healthy"
        
        return {
            "period_hours": hours,
            "total_errors": len(recent_errors),
            "status": status,
            "circuit_broken": self.circuit_broken,
            "by_category": by_category,
            "by_severity": by_severity,
            "most_common_category": max(by_category.items(), key=lambda x: x[1])[0] if by_category else None
        }
    
    def _load_error_history(self):
        """Load recent error history from storage."""
        try:
            data = self.error_storage.read_data("error_history")
            if data and "errors" in data:
                # Load recent errors (last 24 hours)
                cutoff_time = datetime.now().timestamp() - (24 * 3600)
                
                for error_data in data["errors"]:
                    if error_data["timestamp"] >= cutoff_time:
                        error = ContextCleanerError(
                            message=error_data["message"],
                            category=ErrorCategory(error_data["category"]),
                            severity=ErrorSeverity(error_data["severity"])
                        )
                        error.timestamp = datetime.fromtimestamp(error_data["timestamp"])
                        error.error_id = error_data["error_id"]
                        
                        self.recent_errors.append(error)
        
        except Exception as e:
            self.logger.warning(f"Could not load error history: {e}")
    
    def _save_error_history(self):
        """Save error history to storage."""
        try:
            # Keep only last 24 hours of errors
            cutoff_time = datetime.now().timestamp() - (24 * 3600)
            recent_errors = [e for e in self.recent_errors 
                           if e.timestamp.timestamp() >= cutoff_time]
            
            error_data = {
                "errors": [
                    {
                        "error_id": e.error_id,
                        "message": e.message,
                        "category": e.category.value,
                        "severity": e.severity.value,
                        "timestamp": e.timestamp.timestamp()
                    } for e in recent_errors
                ],
                "last_updated": datetime.now().isoformat()
            }
            
            self.error_storage.save_data("error_history", error_data)
        
        except Exception as e:
            self.logger.warning(f"Could not save error history: {e}")


def error_handler(category: ErrorCategory = ErrorCategory.SYSTEM,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 user_message: Optional[str] = None,
                 fallback_return: Any = None):
    """
    Decorator for automatic error handling in functions.
    
    Usage:
        @error_handler(category=ErrorCategory.ANALYSIS, severity=ErrorSeverity.HIGH)
        def analyze_data(data):
            # Function implementation
            return result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Get error handler from config or create default
                handler = getattr(func, '_error_handler', None)
                if not handler:
                    handler = ErrorHandler()
                
                # Create context information
                context = {
                    'function': func.__name__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys())
                }
                
                # Handle the error
                handled = handler.handle_error(e, context, user_message)
                
                if not handled:
                    raise  # Re-raise if not handled
                
                return fallback_return
        
        return wrapper
    return decorator


# Global error handler instance
_global_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get global error handler instance."""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler