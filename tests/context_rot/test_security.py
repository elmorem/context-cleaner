"""Test suite for Context Rot Meter security components."""

import pytest
from src.context_cleaner.telemetry.context_rot.security import (
    PrivacyConfig, 
    InputValidator, 
    ContentSanitizer,
    SecureContextRotAnalyzer
)


class TestInputValidator:
    """Test input validation functionality."""
    
    def test_valid_session_id(self):
        validator = InputValidator()
        
        # Valid session IDs
        assert validator.validate_session_id("abcd1234efgh5678")
        assert validator.validate_session_id("test_session_123")
        assert validator.validate_session_id("a1b2c3d4e5f6g7h8")
        
    def test_invalid_session_id(self):
        validator = InputValidator()
        
        # Invalid session IDs
        assert not validator.validate_session_id("")  # Empty
        assert not validator.validate_session_id("abc")  # Too short
        assert not validator.validate_session_id("a" * 70)  # Too long
        assert not validator.validate_session_id("test@session")  # Invalid chars
        assert not validator.validate_session_id("test session")  # Space
        assert not validator.validate_session_id("test;session")  # SQL injection attempt
        
    def test_content_validation(self):
        validator = InputValidator()
        
        # Valid content
        assert validator.validate_content("Hello, this is a test message")
        assert validator.validate_content("Code: print('hello')")
        assert validator.validate_content("")  # Empty content is valid
        
    def test_dangerous_content_patterns(self):
        validator = InputValidator()
        
        # SQL injection attempts
        assert not validator.validate_content("'; DROP TABLE users; --")
        assert not validator.validate_content("test; DELETE FROM users")
        assert not validator.validate_content("' OR 1=1 --")
        
        # XSS attempts
        assert not validator.validate_content("<script>alert('xss')</script>")
        assert not validator.validate_content("javascript:alert(1)")
        
        # Code injection attempts
        assert not validator.validate_content("eval('malicious code')")
        assert not validator.validate_content("exec('rm -rf /')")
        
    def test_content_length_validation(self):
        validator = InputValidator(max_window_size=10)
        
        # Should fail if content is too long
        long_content = "a" * 2000
        assert not validator.validate_content(long_content, max_length=100)
        
        # Should pass if content is reasonable length
        short_content = "a" * 50
        assert validator.validate_content(short_content, max_length=100)
        
    def test_window_size_validation(self):
        validator = InputValidator(max_window_size=100)
        
        # Valid window sizes
        assert validator.validate_window_size(1)
        assert validator.validate_window_size(50)
        assert validator.validate_window_size(100)
        
        # Invalid window sizes
        assert not validator.validate_window_size(0)
        assert not validator.validate_window_size(-1)
        assert not validator.validate_window_size(101)
        assert not validator.validate_window_size(1000)


class TestContentSanitizer:
    """Test content sanitization functionality."""
    
    def test_pii_removal(self):
        config = PrivacyConfig(remove_pii=True)
        sanitizer = ContentSanitizer(config)
        
        # Test email sanitization
        content = "Contact me at user@example.com for details"
        sanitized = sanitizer.sanitize(content)
        assert "[REDACTED_EMAIL]" in sanitized
        assert "user@example.com" not in sanitized
        
    def test_file_path_anonymization(self):
        config = PrivacyConfig(anonymize_file_paths=True)
        sanitizer = ContentSanitizer(config)
        
        # Test various file path patterns
        content = "/Users/john/project/file.py and /home/jane/code/script.py"
        sanitized = sanitizer.sanitize(content)
        
        assert "/Users/[USER]" in sanitized or "[PROJECT_PATH]" in sanitized
        assert "/home/[USER]" in sanitized or "[PROJECT_PATH]" in sanitized
        assert "john" not in sanitized
        assert "jane" not in sanitized
        
    def test_content_truncation(self):
        config = PrivacyConfig(max_content_length=100)
        sanitizer = ContentSanitizer(config)
        
        # Long content should be truncated
        long_content = "a" * 200
        sanitized = sanitizer.sanitize(long_content)
        
        assert len(sanitized) <= 120  # 100 + truncation marker
        assert "[TRUNCATED]" in sanitized
        
    def test_sensitive_pattern_hashing(self):
        config = PrivacyConfig(hash_sensitive_patterns=True, remove_pii=False)
        sanitizer = ContentSanitizer(config)
        
        # Test long alphanumeric strings (potential API keys) without PII removal
        content = "Here is a long string abc1234567890defghijk1234567890 for testing"
        sanitized = sanitizer.sanitize(content)
        
        # Should contain hash markers for long alphanumeric strings
        assert "[HASH:" in sanitized or "abc1234567890defghijk1234567890" not in sanitized


class TestSecureContextRotAnalyzer:
    """Test the main secure analyzer."""
    
    @pytest.fixture
    def analyzer(self):
        config = PrivacyConfig()
        return SecureContextRotAnalyzer(config)
    
    def test_valid_input_processing(self, analyzer):
        session_id = "test_session_123"
        content = "This is a test message for analysis"
        
        result = analyzer.validate_and_sanitize_input(session_id, content)
        
        assert result is not None
        assert result['session_id'] == session_id
        assert 'content' in result
        assert 'window_size' in result
        assert result['original_length'] == len(content)
        
    def test_invalid_input_rejection(self, analyzer):
        # Invalid session ID
        result = analyzer.validate_and_sanitize_input("", "test content")
        assert result is None
        
        # Invalid content (SQL injection)
        result = analyzer.validate_and_sanitize_input("valid_session_123", "'; DROP TABLE users; --")
        assert result is None
        
    def test_content_risk_analysis(self, analyzer):
        # Safe content
        safe_content = "Hello, how can I help you today?"
        risks = analyzer.analyze_content_risks(safe_content)
        assert risks['risk_level'] == 'low'
        assert not risks['contains_pii']
        assert not risks['contains_secrets']
        
        # Risky content
        risky_content = "My API key is sk-1234567890abcdef and email is user@test.com"
        risks = analyzer.analyze_content_risks(risky_content)
        assert risks['risk_level'] in ['medium', 'high']
        assert risks['contains_pii'] or risks['contains_secrets']
        assert len(risks['detected_patterns']) > 0


class TestPrivacyConfig:
    """Test privacy configuration."""
    
    def test_default_config(self):
        config = PrivacyConfig()
        
        assert config.remove_pii is True
        assert config.hash_sensitive_patterns is True
        assert config.anonymize_file_paths is True
        assert config.max_content_length == 50000
        assert 'text' in config.allowed_content_types
        
    def test_custom_config(self):
        config = PrivacyConfig(
            remove_pii=False,
            max_content_length=1000,
            allowed_content_types=['json']
        )
        
        assert config.remove_pii is False
        assert config.max_content_length == 1000
        assert config.allowed_content_types == ['json']


if __name__ == "__main__":
    pytest.main([__file__])