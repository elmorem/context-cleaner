"""Tests for ContentSecurityManager."""
import pytest
from src.context_cleaner.telemetry.jsonl_enhancement.content_security import ContentSecurityManager

class TestContentSecurityManager:
    
    def test_standard_sanitization(self):
        """Test standard content sanitization."""
        content_with_secrets = """
        Here's some code:
        password = "super_secret_123"
        api_key = "sk-1234567890abcdef"
        user_email = john.doe@example.com
        """
        
        sanitized = ContentSecurityManager.sanitize_content(content_with_secrets, 'standard')
        
        assert '[REDACTED_PASSWORD_FIELD]' in sanitized
        assert '[REDACTED_EMAIL]' in sanitized
        assert 'super_secret_123' not in sanitized
        assert 'john.doe@example.com' not in sanitized
    
    def test_strict_sanitization(self):
        """Test strict content sanitization."""
        content_with_pii = """
        User info:
        Email: john.doe@example.com
        Phone: 555-123-4567
        File path: /home/john/documents/secret.txt
        URL: https://api.example.com/secret-endpoint
        """
        
        sanitized = ContentSecurityManager.sanitize_content(content_with_pii, 'strict')
        
        assert '[REDACTED_EMAIL]' in sanitized
        assert '[REDACTED_PHONE]' in sanitized
        assert '/home/[REDACTED]' in sanitized
        assert '[REDACTED_URL]' in sanitized
        assert 'john.doe@example.com' not in sanitized
        assert '555-123-4567' not in sanitized
    
    def test_minimal_sanitization(self):
        """Test minimal content sanitization."""
        content_with_mixed = """
        Email: john.doe@example.com
        GitHub token: ghp_1234567890abcdef1234567890abcdef123456
        Password: my_password_123
        """
        
        sanitized = ContentSecurityManager.sanitize_content(content_with_mixed, 'minimal')
        
        # Should only redact the most critical patterns
        assert '[REDACTED_GITHUB_TOKEN]' in sanitized
        # Should NOT redact email or password in minimal mode
        assert 'john.doe@example.com' in sanitized
        assert 'my_password_123' in sanitized
    
    def test_analyze_content_risks(self):
        """Test content risk analysis."""
        risky_content = """
        password = "secret123"
        api_key = "sk-1234567890abcdef1234567890"
        email = user@example.com
        """
        
        risks = ContentSecurityManager.analyze_content_risks(risky_content)
        
        assert risks['contains_pii'] is True
        assert risks['contains_secrets'] is True
        assert risks['contains_credentials'] is True
        assert risks['risk_level'] == 'high'
        assert len(risks['detected_patterns']) > 0
        
        # Check specific pattern detection
        pattern_types = [p['type'] for p in risks['detected_patterns']]
        assert 'email' in pattern_types
        assert 'api_key' in pattern_types
        assert 'password_field' in pattern_types
    
    def test_analyze_safe_content(self):
        """Test analysis of content without risks."""
        safe_content = """
        def hello_world():
            print("Hello, World!")
        
        This is just some safe code.
        """
        
        risks = ContentSecurityManager.analyze_content_risks(safe_content)
        
        assert risks['contains_pii'] is False
        assert risks['contains_secrets'] is False
        assert risks['contains_credentials'] is False
        assert risks['risk_level'] == 'low'
        assert len(risks['detected_patterns']) == 0
    
    def test_pii_pattern_detection(self):
        """Test specific PII pattern detection."""
        # Test email detection
        email_content = "Contact us at support@example.com or admin@test.org"
        risks = ContentSecurityManager.analyze_content_risks(email_content)
        email_patterns = [p for p in risks['detected_patterns'] if p['type'] == 'email']
        assert len(email_patterns) == 1
        assert email_patterns[0]['count'] == 2  # Two emails detected
        
        # Test phone number detection  
        phone_content = "Call us at 555-123-4567 or 555.987.6543"
        risks = ContentSecurityManager.analyze_content_risks(phone_content)
        phone_patterns = [p for p in risks['detected_patterns'] if p['type'] == 'phone']
        assert len(phone_patterns) == 1
        assert phone_patterns[0]['count'] == 2
    
    def test_github_token_detection(self):
        """Test GitHub token pattern detection."""
        github_content = "export GITHUB_TOKEN=ghp_1234567890abcdef1234567890abcdef123456"
        
        sanitized = ContentSecurityManager.sanitize_content(github_content, 'standard')
        assert '[REDACTED_GITHUB_TOKEN]' in sanitized
        assert 'ghp_1234567890abcdef1234567890abcdef123456' not in sanitized
        
        risks = ContentSecurityManager.analyze_content_risks(github_content)
        assert risks['contains_secrets'] is True
    
    def test_private_key_detection(self):
        """Test private key detection."""
        key_content = """
        -----BEGIN RSA PRIVATE KEY-----
        MIIEpAIBAAKCAQEA7YQnw...
        -----END RSA PRIVATE KEY-----
        """
        
        sanitized = ContentSecurityManager.sanitize_content(key_content, 'minimal')
        assert '[REDACTED_PRIVATE_KEY]' in sanitized
        assert 'MIIEpAIBAAKCAQEA7YQnw' not in sanitized
    
    def test_empty_content(self):
        """Test handling of empty or None content."""
        assert ContentSecurityManager.sanitize_content('') == ''
        assert ContentSecurityManager.sanitize_content(None) is None
        
        risks = ContentSecurityManager.analyze_content_risks('')
        assert risks['risk_level'] == 'low'
        assert len(risks['detected_patterns']) == 0