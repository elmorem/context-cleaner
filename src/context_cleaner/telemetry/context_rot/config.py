"""
Configuration Management for Context Rot Meter.

This module provides centralized configuration management with
support for different environments and runtime settings.
"""

import os
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from pathlib import Path

from .data_retention import RetentionPolicy

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"  
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class SecurityConfig:
    """Security-related configuration."""
    enable_pii_scrubbing: bool = True
    enable_data_anonymization: bool = True
    max_session_id_length: int = 64
    allowed_session_id_pattern: str = r'^[a-zA-Z0-9_-]{8,64}$'
    enable_content_filtering: bool = True
    dangerous_content_patterns: List[str] = field(default_factory=lambda: [
        r'password\s*[:=]\s*\S+',
        r'api[_-]?key\s*[:=]\s*\S+',
        r'secret\s*[:=]\s*\S+',
        r'token\s*[:=]\s*\S+'
    ])


@dataclass 
class PerformanceConfig:
    """Performance-related configuration."""
    max_analysis_latency_ms: int = 100
    max_memory_usage_mb: int = 256
    max_concurrent_analyses: int = 50
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_timeout_ms: int = 50
    cache_size_limit: int = 10000
    batch_processing_size: int = 10


@dataclass
class MLConfig:
    """ML-related configuration."""
    enable_ml_analysis: bool = True
    sentiment_confidence_threshold: float = 0.6
    frustration_confidence_threshold: float = 0.7
    model_cache_size: int = 1000
    max_conversation_length: int = 1000
    enable_conversation_flow_analysis: bool = True
    enable_temporal_weighting: bool = True


@dataclass
class AlertingConfig:
    """Alerting configuration."""
    enable_alerting: bool = True
    alert_channels: List[str] = field(default_factory=lambda: ["log"])
    critical_alert_threshold: float = 0.8
    warning_alert_threshold: float = 0.6
    alert_cooldown_minutes: int = 30
    max_alerts_per_hour: int = 10


@dataclass
class DatabaseConfig:
    """Database configuration."""
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_database: str = "default"
    clickhouse_username: str = "default"
    clickhouse_password: str = ""
    connection_timeout_seconds: int = 30
    query_timeout_seconds: int = 120
    max_connections: int = 10


@dataclass
class RetentionConfig:
    """Data retention configuration."""
    retention_policy: RetentionPolicy = RetentionPolicy.PRIVACY_FOCUSED
    enable_automatic_cleanup: bool = True
    cleanup_interval_hours: int = 24
    enable_user_deletion_requests: bool = True
    anonymization_delay_days: int = 30


@dataclass
class MonitoringConfig:
    """Monitoring and health check configuration."""
    enable_health_monitoring: bool = True
    health_check_interval_seconds: int = 30
    enable_resource_monitoring: bool = True
    enable_prometheus_metrics: bool = False
    prometheus_port: int = 8080
    metrics_retention_hours: int = 24


@dataclass
class ContextRotConfig:
    """Complete Context Rot Meter configuration."""
    environment: Environment = Environment.DEVELOPMENT
    log_level: LogLevel = LogLevel.INFO
    enable_debug_mode: bool = False
    
    # Component configurations
    security: SecurityConfig = field(default_factory=SecurityConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    ml: MLConfig = field(default_factory=MLConfig)
    alerting: AlertingConfig = field(default_factory=AlertingConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    # Feature flags
    feature_flags: Dict[str, bool] = field(default_factory=lambda: {
        "enable_ml_sentiment_analysis": True,
        "enable_adaptive_thresholds": True,
        "enable_conversation_flow_analysis": True,
        "enable_real_time_alerts": True,
        "enable_user_feedback": True,
        "enable_dashboard_widget": True,
        "enable_data_export": False,
        "enable_advanced_analytics": False
    })
    
    # Custom settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        self._validate_configuration()
        self._apply_environment_overrides()
    
    def _validate_configuration(self):
        """Validate configuration values."""
        # Performance validation
        if self.performance.max_analysis_latency_ms < 10:
            raise ValueError("max_analysis_latency_ms must be at least 10ms")
        
        if self.performance.max_memory_usage_mb < 64:
            raise ValueError("max_memory_usage_mb must be at least 64MB")
        
        # ML validation
        if not 0.0 <= self.ml.sentiment_confidence_threshold <= 1.0:
            raise ValueError("sentiment_confidence_threshold must be between 0.0 and 1.0")
        
        if not 0.0 <= self.ml.frustration_confidence_threshold <= 1.0:
            raise ValueError("frustration_confidence_threshold must be between 0.0 and 1.0")
        
        # Alerting validation
        if not 0.0 <= self.alerting.critical_alert_threshold <= 1.0:
            raise ValueError("critical_alert_threshold must be between 0.0 and 1.0")
        
        if self.alerting.warning_alert_threshold >= self.alerting.critical_alert_threshold:
            raise ValueError("warning_alert_threshold must be less than critical_alert_threshold")
        
        # Database validation
        if self.database.clickhouse_port < 1 or self.database.clickhouse_port > 65535:
            raise ValueError("clickhouse_port must be a valid port number")
    
    def _apply_environment_overrides(self):
        """Apply environment-specific overrides."""
        env_overrides = {
            Environment.DEVELOPMENT: self._get_development_overrides,
            Environment.TESTING: self._get_testing_overrides,
            Environment.STAGING: self._get_staging_overrides,
            Environment.PRODUCTION: self._get_production_overrides
        }
        
        override_func = env_overrides.get(self.environment)
        if override_func:
            override_func()
    
    def _get_development_overrides(self):
        """Development environment overrides."""
        self.enable_debug_mode = True
        self.log_level = LogLevel.DEBUG
        self.retention.cleanup_interval_hours = 1  # More frequent cleanup for testing
        self.performance.circuit_breaker_failure_threshold = 10  # More lenient
        self.alerting.max_alerts_per_hour = 100  # Less restrictive
    
    def _get_testing_overrides(self):
        """Testing environment overrides."""
        self.enable_debug_mode = True
        self.log_level = LogLevel.INFO
        self.retention.retention_policy = RetentionPolicy.GDPR_STRICT  # Fast cleanup
        self.retention.cleanup_interval_hours = 1
        self.monitoring.health_check_interval_seconds = 10  # Faster checks
        self.alerting.enable_alerting = False  # Disable alerts in tests
    
    def _get_staging_overrides(self):
        """Staging environment overrides."""
        self.log_level = LogLevel.INFO
        self.retention.retention_policy = RetentionPolicy.PRIVACY_FOCUSED
        self.performance.circuit_breaker_failure_threshold = 3  # More sensitive
        self.monitoring.enable_prometheus_metrics = True
    
    def _get_production_overrides(self):
        """Production environment overrides."""
        self.enable_debug_mode = False
        self.log_level = LogLevel.WARNING
        self.retention.retention_policy = RetentionPolicy.PRIVACY_FOCUSED
        self.performance.circuit_breaker_failure_threshold = 3
        self.performance.max_memory_usage_mb = 256
        self.alerting.alert_cooldown_minutes = 60  # Longer cooldown
        self.monitoring.enable_prometheus_metrics = True
        self.security.enable_pii_scrubbing = True  # Ensure PII protection
        
        # Enable all production features
        self.feature_flags.update({
            "enable_ml_sentiment_analysis": True,
            "enable_adaptive_thresholds": True,
            "enable_conversation_flow_analysis": True,
            "enable_real_time_alerts": True,
            "enable_user_feedback": True,
            "enable_dashboard_widget": True
        })
    
    @classmethod
    def from_env(cls) -> 'ContextRotConfig':
        """Create configuration from environment variables."""
        config = cls()
        
        # Environment detection
        env_name = os.getenv('CONTEXT_ROT_ENVIRONMENT', 'development').lower()
        try:
            config.environment = Environment(env_name)
        except ValueError:
            logger.warning(f"Invalid environment '{env_name}', using development")
            config.environment = Environment.DEVELOPMENT
        
        # Log level
        log_level = os.getenv('CONTEXT_ROT_LOG_LEVEL', 'INFO').upper()
        try:
            config.log_level = LogLevel(log_level)
        except ValueError:
            logger.warning(f"Invalid log level '{log_level}', using INFO")
            config.log_level = LogLevel.INFO
        
        # Debug mode
        config.enable_debug_mode = os.getenv('CONTEXT_ROT_DEBUG', 'false').lower() == 'true'
        
        # Database configuration
        config.database.clickhouse_host = os.getenv('CLICKHOUSE_HOST', config.database.clickhouse_host)
        config.database.clickhouse_port = int(os.getenv('CLICKHOUSE_PORT', str(config.database.clickhouse_port)))
        config.database.clickhouse_database = os.getenv('CLICKHOUSE_DATABASE', config.database.clickhouse_database)
        config.database.clickhouse_username = os.getenv('CLICKHOUSE_USERNAME', config.database.clickhouse_username)
        config.database.clickhouse_password = os.getenv('CLICKHOUSE_PASSWORD', config.database.clickhouse_password)
        
        # Performance configuration
        config.performance.max_analysis_latency_ms = int(os.getenv('CONTEXT_ROT_MAX_LATENCY_MS', str(config.performance.max_analysis_latency_ms)))
        config.performance.max_memory_usage_mb = int(os.getenv('CONTEXT_ROT_MAX_MEMORY_MB', str(config.performance.max_memory_usage_mb)))
        
        # Retention configuration
        retention_policy = os.getenv('CONTEXT_ROT_RETENTION_POLICY', config.retention.retention_policy.value)
        try:
            config.retention.retention_policy = RetentionPolicy(retention_policy)
        except ValueError:
            logger.warning(f"Invalid retention policy '{retention_policy}', using default")
        
        config.retention.enable_automatic_cleanup = os.getenv('CONTEXT_ROT_AUTO_CLEANUP', 'true').lower() == 'true'
        config.retention.cleanup_interval_hours = int(os.getenv('CONTEXT_ROT_CLEANUP_INTERVAL_HOURS', str(config.retention.cleanup_interval_hours)))
        
        # Feature flags from environment
        for flag_name in config.feature_flags:
            env_var = f'CONTEXT_ROT_ENABLE_{flag_name.upper().replace("ENABLE_", "")}'
            if env_var in os.environ:
                config.feature_flags[flag_name] = os.getenv(env_var, 'false').lower() == 'true'
        
        # Apply environment overrides after loading from env
        config._apply_environment_overrides()
        
        return config
    
    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> 'ContextRotConfig':
        """Load configuration from JSON file."""
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Convert nested dictionaries to appropriate dataclasses
            config = cls()
            
            # Update configuration from file data
            for section, values in config_data.items():
                if hasattr(config, section) and isinstance(values, dict):
                    section_obj = getattr(config, section)
                    if hasattr(section_obj, '__dataclass_fields__'):
                        # Update dataclass fields
                        for field_name, field_value in values.items():
                            if hasattr(section_obj, field_name):
                                setattr(section_obj, field_name, field_value)
                    else:
                        # Direct assignment for simple fields
                        setattr(config, section, values)
                elif hasattr(config, section):
                    setattr(config, section, values)
            
            return config
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load configuration file: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        def convert_dataclass(obj):
            if hasattr(obj, '__dataclass_fields__'):
                return {k: convert_dataclass(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, Enum):
                return obj.value
            elif isinstance(obj, list):
                return [convert_dataclass(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: convert_dataclass(v) for k, v in obj.items()}
            else:
                return obj
        
        return convert_dataclass(self)
    
    def save_to_file(self, config_path: Union[str, Path]) -> None:
        """Save configuration to JSON file."""
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        
        logger.info(f"Configuration saved to {config_path}")
    
    def get_feature_flag(self, flag_name: str, default: bool = False) -> bool:
        """Get feature flag value."""
        return self.feature_flags.get(flag_name, default)
    
    def set_feature_flag(self, flag_name: str, enabled: bool) -> None:
        """Set feature flag value."""
        self.feature_flags[flag_name] = enabled
    
    def get_custom_setting(self, setting_name: str, default: Any = None) -> Any:
        """Get custom setting value."""
        return self.custom_settings.get(setting_name, default)
    
    def set_custom_setting(self, setting_name: str, value: Any) -> None:
        """Set custom setting value."""
        self.custom_settings[setting_name] = value
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT
    
    def setup_logging(self) -> None:
        """Configure logging based on configuration."""
        log_level = getattr(logging, self.log_level.value)
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Configure specific loggers
        context_rot_logger = logging.getLogger('context_cleaner.telemetry.context_rot')
        context_rot_logger.setLevel(log_level)
        
        if self.enable_debug_mode:
            context_rot_logger.setLevel(logging.DEBUG)
        
        logger.info(f"Logging configured for {self.environment.value} environment")


class ConfigManager:
    """Manages configuration loading and updates."""
    
    def __init__(self):
        self._config: Optional[ContextRotConfig] = None
        self._config_file_path: Optional[Path] = None
    
    def load_config(self, config_path: Optional[Union[str, Path]] = None) -> ContextRotConfig:
        """Load configuration from file or environment."""
        if config_path:
            self._config_file_path = Path(config_path)
            self._config = ContextRotConfig.from_file(config_path)
        else:
            self._config = ContextRotConfig.from_env()
        
        # Setup logging
        self._config.setup_logging()
        
        logger.info(f"Configuration loaded for {self._config.environment.value} environment")
        return self._config
    
    def get_config(self) -> ContextRotConfig:
        """Get current configuration."""
        if self._config is None:
            self._config = ContextRotConfig.from_env()
            self._config.setup_logging()
        
        return self._config
    
    def reload_config(self) -> ContextRotConfig:
        """Reload configuration from source."""
        if self._config_file_path:
            self._config = ContextRotConfig.from_file(self._config_file_path)
        else:
            self._config = ContextRotConfig.from_env()
        
        self._config.setup_logging()
        logger.info("Configuration reloaded")
        return self._config
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration with new values."""
        if self._config is None:
            self._config = ContextRotConfig.from_env()
        
        # Apply updates (simplified - could be more sophisticated)
        for section, values in updates.items():
            if hasattr(self._config, section):
                section_obj = getattr(self._config, section)
                if hasattr(section_obj, '__dataclass_fields__') and isinstance(values, dict):
                    for field_name, field_value in values.items():
                        if hasattr(section_obj, field_name):
                            setattr(section_obj, field_name, field_value)
                else:
                    setattr(self._config, section, values)
        
        logger.info("Configuration updated")


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None

def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

def get_config() -> ContextRotConfig:
    """Get current configuration."""
    return get_config_manager().get_config()