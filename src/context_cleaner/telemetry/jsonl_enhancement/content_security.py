"""Manage security and privacy for full content storage."""
import re
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ContentSecurityManager:
    """Manage security and privacy for full content storage."""
    
    # Comprehensive PII patterns
    PII_PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'ssn': r'\b\d{3}-?\d{2}-?\d{4}\b',
        'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        'api_key': r'\b(sk-[A-Za-z0-9]{20,}|[A-Za-z0-9]{32,})\b',
        'password_field': r'\b(password|passwd|pwd)[\s=:\'\"]+[^\s\'"]+',
        'token_field': r'\b(?!.*(?:github|ghp_))(token|key|secret)[\s=:\'\"]+[^\s\'"]+',
        'private_key': r'-----BEGIN (RSA |EC |)PRIVATE KEY-----.*?-----END (RSA |EC |)PRIVATE KEY-----',
        'aws_key': r'AKIA[0-9A-Z]{16}',
        'github_token': r'ghp_[A-Za-z0-9]{36}',
        'slack_token': r'xox[baprs]-[A-Za-z0-9-]+'
    }
    
    @classmethod
    def sanitize_content(cls, content: str, privacy_level: str = 'standard') -> str:
        """Sanitize content based on privacy level."""
        if not content:
            return content
        
        if privacy_level == 'strict':
            return cls._strict_sanitization(content)
        elif privacy_level == 'standard':
            return cls._standard_sanitization(content)
        elif privacy_level == 'minimal':
            return cls._minimal_sanitization(content)
        
        return content
    
    @classmethod
    def _strict_sanitization(cls, content: str) -> str:
        """Strict sanitization - redact most potentially sensitive content."""
        sanitized = content
        
        # Redact all PII patterns
        for pattern_name, pattern in cls.PII_PATTERNS.items():
            flags = re.IGNORECASE | re.DOTALL if pattern_name == 'private_key' else re.IGNORECASE
            sanitized = re.sub(pattern, f'[REDACTED_{pattern_name.upper()}]', sanitized, flags=flags)
        
        # Redact file paths that might contain usernames
        sanitized = re.sub(r'/home/[^/\s]+', '/home/[REDACTED]', sanitized)
        sanitized = re.sub(r'C:\\\\Users\\\\[^\\\\]+', r'C:\\Users\\[REDACTED]', sanitized)
        
        # Redact URLs with sensitive info
        sanitized = re.sub(r'https?://[^\s]+', '[REDACTED_URL]', sanitized)
        
        return sanitized
    
    @classmethod  
    def _standard_sanitization(cls, content: str) -> str:
        """Standard sanitization - redact obvious secrets and PII."""
        sanitized = content
        
        # Redact critical patterns
        critical_patterns = ['api_key', 'password_field', 'token_field', 'private_key', 'aws_key', 'github_token', 'slack_token']
        for pattern_name in critical_patterns:
            if pattern_name in cls.PII_PATTERNS:
                pattern = cls.PII_PATTERNS[pattern_name]
                flags = re.IGNORECASE | re.DOTALL if pattern_name == 'private_key' else re.IGNORECASE
                sanitized = re.sub(pattern, f'[REDACTED_{pattern_name.upper()}]', sanitized, flags=flags)
        
        # Redact email addresses
        sanitized = re.sub(cls.PII_PATTERNS['email'], '[REDACTED_EMAIL]', sanitized)
        
        return sanitized
    
    @classmethod
    def _minimal_sanitization(cls, content: str) -> str:
        """Minimal sanitization - only redact obvious API keys and tokens."""
        sanitized = content
        
        # Only redact the most critical patterns
        critical_patterns = ['private_key', 'aws_key', 'github_token', 'slack_token']
        for pattern_name in critical_patterns:
            if pattern_name in cls.PII_PATTERNS:
                pattern = cls.PII_PATTERNS[pattern_name]
                flags = re.IGNORECASE | re.DOTALL if pattern_name == 'private_key' else re.IGNORECASE
                sanitized = re.sub(pattern, f'[REDACTED_{pattern_name.upper()}]', sanitized, flags=flags)
        
        return sanitized
    
    @classmethod
    def analyze_content_risks(cls, content: str) -> Dict[str, Any]:
        """Analyze content for potential security risks."""
        risks = {
            'contains_pii': False,
            'contains_secrets': False,
            'contains_credentials': False,
            'risk_level': 'low',
            'detected_patterns': []
        }
        
        for pattern_name, pattern in cls.PII_PATTERNS.items():
            flags = re.IGNORECASE | re.DOTALL if pattern_name == 'private_key' else re.IGNORECASE
            matches = re.findall(pattern, content, flags)
            if matches:
                risks['detected_patterns'].append({
                    'type': pattern_name,
                    'count': len(matches)
                })
                
                if pattern_name in ['email', 'phone', 'ssn', 'credit_card']:
                    risks['contains_pii'] = True
                elif pattern_name in ['api_key', 'token_field', 'private_key', 'aws_key', 'github_token']:
                    risks['contains_secrets'] = True
                elif pattern_name in ['password_field']:
                    risks['contains_credentials'] = True
        
        # Determine overall risk level
        if risks['contains_secrets'] or risks['contains_credentials']:
            risks['risk_level'] = 'high'
        elif risks['contains_pii']:
            risks['risk_level'] = 'medium'
        
        return risks