"""
Context Cleaner Configuration Management.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class AnalysisConfig:
    """Configuration for context analysis engine."""
    health_thresholds: Dict[str, int]
    max_context_size: int
    token_estimation_factor: float
    circuit_breaker_threshold: int

@dataclass
class DashboardConfig:
    """Configuration for web dashboard."""
    port: int
    host: str
    auto_refresh: bool
    cache_duration: int
    max_concurrent_users: int

@dataclass
class TrackingConfig:
    """Configuration for productivity tracking."""
    enabled: bool
    sampling_rate: float
    session_timeout_minutes: int
    data_retention_days: int
    anonymize_data: bool

@dataclass
class PrivacyConfig:
    """Configuration for privacy and security."""
    local_only: bool
    encrypt_storage: bool
    auto_cleanup_days: int
    require_consent: bool

@dataclass
class ContextCleanerConfig:
    """Main configuration class for Context Cleaner."""
    
    analysis: AnalysisConfig
    dashboard: DashboardConfig
    tracking: TrackingConfig
    privacy: PrivacyConfig
    data_directory: str
    log_level: str
    
    @classmethod
    def default(cls) -> 'ContextCleanerConfig':
        """Create default configuration."""
        return cls(
            analysis=AnalysisConfig(
                health_thresholds={
                    "excellent": 90,
                    "good": 70,
                    "fair": 50,
                },
                max_context_size=100000,
                token_estimation_factor=0.25,
                circuit_breaker_threshold=5,
            ),
            dashboard=DashboardConfig(
                port=8548,
                host="localhost",
                auto_refresh=True,
                cache_duration=300,
                max_concurrent_users=10,
            ),
            tracking=TrackingConfig(
                enabled=True,
                sampling_rate=1.0,
                session_timeout_minutes=30,
                data_retention_days=90,
                anonymize_data=True,
            ),
            privacy=PrivacyConfig(
                local_only=True,
                encrypt_storage=True,
                auto_cleanup_days=90,
                require_consent=True,
            ),
            data_directory=str(Path.home() / ".context_cleaner" / "data"),
            log_level="INFO",
        )
    
    @classmethod
    def from_file(cls, config_path: Path) -> 'ContextCleanerConfig':
        """Load configuration from file."""
        if not config_path.exists():
            return cls.default()
        
        try:
            with open(config_path, 'r') as f:
                if config_path.suffix.lower() == '.json':
                    data = json.load(f)
                elif config_path.suffix.lower() in ('.yaml', '.yml'):
                    data = yaml.safe_load(f)
                else:
                    raise ValueError(f"Unsupported config format: {config_path.suffix}")
            
            return cls.from_dict(data)
        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")
            return cls.default()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextCleanerConfig':
        """Create configuration from dictionary."""
        default_config = cls.default()
        
        # Update with provided values
        config_dict = asdict(default_config)
        
        # Merge nested dictionaries
        for key, value in data.items():
            if key in config_dict:
                if isinstance(value, dict) and isinstance(config_dict[key], dict):
                    config_dict[key].update(value)
                else:
                    config_dict[key] = value
        
        return cls(
            analysis=AnalysisConfig(**config_dict['analysis']),
            dashboard=DashboardConfig(**config_dict['dashboard']),
            tracking=TrackingConfig(**config_dict['tracking']),
            privacy=PrivacyConfig(**config_dict['privacy']),
            data_directory=config_dict['data_directory'],
            log_level=config_dict['log_level'],
        )
    
    @classmethod
    def from_env(cls) -> 'ContextCleanerConfig':
        """Create configuration from environment variables."""
        default_config = cls.default()
        
        # Override with environment variables
        env_overrides = {}
        
        # Dashboard configuration
        if port := os.getenv('CONTEXT_CLEANER_PORT'):
            env_overrides.setdefault('dashboard', {})['port'] = int(port)
        
        if host := os.getenv('CONTEXT_CLEANER_HOST'):
            env_overrides.setdefault('dashboard', {})['host'] = host
        
        # Data directory
        if data_dir := os.getenv('CONTEXT_CLEANER_DATA_DIR'):
            env_overrides['data_directory'] = data_dir
        
        # Log level
        if log_level := os.getenv('CONTEXT_CLEANER_LOG_LEVEL'):
            env_overrides['log_level'] = log_level.upper()
        
        # Privacy settings
        if local_only := os.getenv('CONTEXT_CLEANER_LOCAL_ONLY'):
            env_overrides.setdefault('privacy', {})['local_only'] = local_only.lower() in ('true', '1', 'yes')
        
        if env_overrides:
            return cls.from_dict(env_overrides)
        
        return default_config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)
    
    def save(self, config_path: Path) -> None:
        """Save configuration to file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config_dict = self.to_dict()
        
        with open(config_path, 'w') as f:
            if config_path.suffix.lower() == '.json':
                json.dump(config_dict, f, indent=2)
            elif config_path.suffix.lower() in ('.yaml', '.yml'):
                yaml.safe_dump(config_dict, f, default_flow_style=False, indent=2)
            else:
                raise ValueError(f"Unsupported config format: {config_path.suffix}")
    
    def get_data_path(self, subdir: str = "") -> Path:
        """Get path for data storage."""
        path = Path(self.data_directory)
        if subdir:
            path = path / subdir
        path.mkdir(parents=True, exist_ok=True)
        return path