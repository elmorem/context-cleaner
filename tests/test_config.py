"""
Tests for Context Cleaner configuration system.
"""

import pytest
import tempfile
import yaml
import os
from pathlib import Path

from context_cleaner.config.settings import (
    ContextCleanerConfig, 
    AnalysisConfig,
    DashboardConfig,
    TrackingConfig,
    PrivacyConfig
)


class TestContextCleanerConfig:
    """Test suite for ContextCleanerConfig."""
    
    def test_default_config_creation(self):
        """Test creation of default configuration."""
        config = ContextCleanerConfig.default()
        
        assert config.analysis.health_thresholds['excellent'] == 90
        assert config.analysis.health_thresholds['good'] == 70  
        assert config.analysis.health_thresholds['fair'] == 50
        assert config.dashboard.port == 8548
        assert config.dashboard.host == "localhost"
        assert config.tracking.enabled is True
        assert config.privacy.local_only is True
    
    def test_config_from_env_variables(self):
        """Test configuration from environment variables."""
        # Set test environment variables
        os.environ.update({
            "CONTEXT_CLEANER_PORT": "9000",
            "CONTEXT_CLEANER_DATA_DIR": "/tmp/test-data",
            "CONTEXT_CLEANER_LOG_LEVEL": "DEBUG"
        })
        
        try:
            config = ContextCleanerConfig.from_env()
            assert config.dashboard.port == 9000
            assert config.data_directory == "/tmp/test-data"
            assert config.log_level == "DEBUG"
        finally:
            # Cleanup environment variables
            for key in ["CONTEXT_CLEANER_PORT", "CONTEXT_CLEANER_DATA_DIR", "CONTEXT_CLEANER_LOG_LEVEL"]:
                os.environ.pop(key, None)
    
    def test_config_from_yaml_file(self):
        """Test configuration from YAML file."""
        config_data = {
            "dashboard": {
                "port": 8080,
                "host": "0.0.0.0",
                "auto_refresh": False
            },
            "tracking": {
                "enabled": False,
                "session_timeout_minutes": 60
            },
            "analysis": {
                "max_context_size": 200000,
                "health_thresholds": {
                    "excellent": 95,
                    "good": 75,
                    "fair": 55
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name
        
        try:
            config = ContextCleanerConfig.from_file(Path(config_file))
            assert config.dashboard.port == 8080
            assert config.dashboard.host == "0.0.0.0" 
            assert config.dashboard.auto_refresh is False
            assert config.tracking.enabled is False
            assert config.tracking.session_timeout_minutes == 60
            assert config.analysis.max_context_size == 200000
            assert config.analysis.health_thresholds['excellent'] == 95
        finally:
            os.unlink(config_file)
    
    def test_config_to_dict(self):
        """Test configuration serialization to dictionary."""
        config = ContextCleanerConfig.default()
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert "dashboard" in config_dict
        assert "tracking" in config_dict
        assert "analysis" in config_dict
        assert "privacy" in config_dict
        assert config_dict["dashboard"]["port"] == 8548
        assert config_dict["privacy"]["local_only"] is True
        
    def test_invalid_config_file(self):
        """Test handling of invalid configuration file."""
        try:
            config = ContextCleanerConfig.from_file(Path("/non/existent/config.yaml"))
            # If no exception, should fall back to defaults
            assert config is not None
            assert config.dashboard.port == 8548
        except FileNotFoundError:
            # This is also acceptable behavior
            pass


class TestConfigComponents:
    """Test individual configuration components through default config."""
    
    def test_analysis_config_values(self):
        """Test AnalysisConfig values in default configuration."""
        config = ContextCleanerConfig.default()
        assert config.analysis.max_context_size == 100000
        assert config.analysis.health_thresholds['excellent'] == 90
        assert config.analysis.health_thresholds['good'] == 70
        assert config.analysis.health_thresholds['fair'] == 50
    
    def test_dashboard_config_values(self):
        """Test DashboardConfig values in default configuration."""
        config = ContextCleanerConfig.default()
        assert config.dashboard.port == 8548
        assert config.dashboard.host == "localhost"
        assert config.dashboard.auto_refresh is True
        assert config.dashboard.cache_duration == 300
    
    def test_tracking_config_values(self):
        """Test TrackingConfig values in default configuration."""
        config = ContextCleanerConfig.default()
        assert config.tracking.enabled is True
        assert config.tracking.sampling_rate == 1.0
        assert config.tracking.session_timeout_minutes == 30
        assert config.tracking.data_retention_days == 90
    
    def test_privacy_config_values(self):
        """Test PrivacyConfig values in default configuration.""" 
        config = ContextCleanerConfig.default()
        assert config.privacy.local_only is True
        assert config.privacy.encrypt_storage is True
        assert config.privacy.require_consent is True