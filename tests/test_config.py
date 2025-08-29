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
        
        assert config.analysis.health_thresholds.excellent == 90
        assert config.analysis.health_thresholds.good == 70  
        assert config.analysis.health_thresholds.fair == 50
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
            assert config.analysis.health_thresholds.excellent == 95
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
        with pytest.raises(FileNotFoundError):
            ContextCleanerConfig.from_file(Path("/non/existent/config.yaml"))


class TestConfigComponents:
    """Test individual configuration components."""
    
    def test_analysis_config_defaults(self):
        """Test AnalysisConfig default values."""
        config = AnalysisConfig()
        assert config.max_context_size == 100000
        assert config.health_thresholds.excellent == 90
        assert config.health_thresholds.good == 70
        assert config.health_thresholds.fair == 50
    
    def test_dashboard_config_defaults(self):
        """Test DashboardConfig default values."""
        config = DashboardConfig()
        assert config.port == 8548
        assert config.host == "localhost"
        assert config.auto_refresh is True
        assert config.cache_duration == 300
    
    def test_tracking_config_defaults(self):
        """Test TrackingConfig default values."""
        config = TrackingConfig()
        assert config.enabled is True
        assert config.sampling_rate == 1.0
        assert config.session_timeout_minutes == 30
        assert config.data_retention_days == 90
    
    def test_privacy_config_defaults(self):
        """Test PrivacyConfig default values."""
        config = PrivacyConfig()
        assert config.local_only is True
        assert config.encrypt_storage is True
        assert config.require_consent is True