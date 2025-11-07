"""Security hardening and input validation for Context Rot Meter."""

import re
import hashlib
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

from ..jsonl_enhancement.content_security import ContentSecurityManager

logger = logging.getLogger(__name__)


@dataclass
class PrivacyConfig:
    """Configuration for privacy and data protection."""

    remove_pii: bool = True
    hash_sensitive_patterns: bool = True
    anonymize_file_paths: bool = True
    max_content_length: int = 50000  # Prevent memory exhaustion
    allowed_content_types: List[str] = None

    def __post_init__(self):
        if self.allowed_content_types is None:
            self.allowed_content_types = ["text", "code", "json", "markdown"]


class InputValidator:
    """Comprehensive input validation to prevent security issues."""

    def __init__(
        self,
        max_window_size: int = 1000,
        allowed_session_id_pattern: str = r"^[a-zA-Z0-9_-]{8,64}$",
    ):
        self.max_window_size = max_window_size
        self.session_id_pattern = re.compile(allowed_session_id_pattern)

        # SQL injection prevention patterns (more specific to avoid false positives)
        self.dangerous_patterns = [
            r";\s*DROP\s+TABLE",  # SQL injection - DROP TABLE
            r";\s*DELETE\s+FROM",  # SQL injection - DELETE
            r"\'\s*OR\s+\d+\s*=\s*\d+\s*--",  # SQL injection - OR condition
            r"<script[^>]*>.*?</script>",  # XSS
            r"javascript:.*alert\s*\(",  # XSS - more specific
            r'eval\s*\(\s*["\']',  # Code injection - eval with string
            r'exec\s*\(\s*["\']',  # Code injection - exec with string
        ]

    def validate_session_id(self, session_id: str) -> bool:
        """Validate session ID format and prevent injection attacks."""
        if not session_id or len(session_id) < 8 or len(session_id) > 64:
            logger.warning(
                f"Invalid session ID length: {len(session_id) if session_id else 0}"
            )
            return False

        if not self.session_id_pattern.match(session_id):
            logger.warning("Session ID contains invalid characters")
            return False

        return True

    def validate_content(self, content: str, max_length: int = None) -> bool:
        """Validate content for security issues."""
        if not content:
            return True

        # Length validation
        max_len = max_length or self.max_window_size * 100  # Reasonable default
        if len(content) > max_len:
            logger.warning(f"Content too long: {len(content)} > {max_len}")
            return False

        # Check for dangerous patterns
        for pattern in self.dangerous_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                logger.error(f"Dangerous pattern detected: {pattern[:20]}...")
                return False

        return True

    def validate_window_size(self, window_size: int) -> bool:
        """Validate analysis window size to prevent resource exhaustion."""
        return 1 <= window_size <= self.max_window_size


class ContentSanitizer:
    """Content sanitization for privacy and security."""

    def __init__(self, privacy_config: PrivacyConfig):
        self.config = privacy_config
        self.security_manager = ContentSecurityManager()

    def sanitize(self, content: str) -> str:
        """Sanitize content based on privacy configuration."""
        if not content:
            return content

        # Truncate if too long
        if len(content) > self.config.max_content_length:
            content = content[: self.config.max_content_length] + "...[TRUNCATED]"

        # Remove PII if configured
        if self.config.remove_pii:
            content = self.security_manager.sanitize_content(
                content, privacy_level="standard"
            )

        # Anonymize file paths if configured
        if self.config.anonymize_file_paths:
            content = self._anonymize_file_paths(content)

        # Hash sensitive patterns if configured
        if self.config.hash_sensitive_patterns:
            content = self._hash_sensitive_patterns(content)

        return content

    def _anonymize_file_paths(self, content: str) -> str:
        """Anonymize file paths to protect user privacy."""
        # Replace user home directories
        content = re.sub(r"/Users/[^/\s]+", "/Users/[USER]", content)
        content = re.sub(r"/home/[^/\s]+", "/home/[USER]", content)
        content = re.sub(r"C:\\\\Users\\\\[^\\\\]+", r"C:\\Users\\[USER]", content)

        # Replace project-specific paths with generic markers
        content = re.sub(
            r"/[^/\s]*/(projects?|code|dev|work)/[^/\s]+", "/[PROJECT_PATH]", content
        )

        return content

    def _hash_sensitive_patterns(self, content: str) -> str:
        """Hash potentially sensitive data while preserving structure."""

        # Hash what looks like API keys or tokens
        def hash_match(match):
            original = match.group(0)
            if len(original) > 8:
                # Keep structure but hash the content
                prefix = original[:2]
                suffix = original[-2:]
                hashed = hashlib.sha256(original.encode()).hexdigest()[:8]
                return f"{prefix}[HASH:{hashed}]{suffix}"
            return original

        # Hash long alphanumeric strings that might be sensitive
        content = re.sub(r"\b[A-Za-z0-9]{16,}\b", hash_match, content)

        return content


class SecureContextRotAnalyzer:
    """Security-hardened Context Rot Analyzer with comprehensive input validation."""

    def __init__(self, privacy_config: PrivacyConfig):
        self.privacy_config = privacy_config
        self.input_validator = InputValidator(
            max_window_size=1000, allowed_session_id_pattern=r"^[a-zA-Z0-9_-]{8,64}$"
        )
        self.content_sanitizer = ContentSanitizer(privacy_config)

    def validate_and_sanitize_input(
        self, session_id: str, content: str, window_size: int = 50
    ) -> Optional[Dict[str, Any]]:
        """Validate and sanitize all inputs before processing."""
        # Validate session ID
        if not self.input_validator.validate_session_id(session_id):
            logger.error(f"Invalid session ID rejected: {session_id[:10]}...")
            return None

        # Validate content
        if not self.input_validator.validate_content(
            content, self.privacy_config.max_content_length
        ):
            logger.error("Invalid content rejected")
            return None

        # Validate window size
        if not self.input_validator.validate_window_size(window_size):
            logger.error(f"Invalid window size rejected: {window_size}")
            return None

        # Sanitize content
        sanitized_content = self.content_sanitizer.sanitize(content)

        return {
            "session_id": session_id,
            "content": sanitized_content,
            "window_size": window_size,
            "original_length": len(content),
            "sanitized_length": len(sanitized_content),
        }

    def analyze_content_risks(self, content: str) -> Dict[str, Any]:
        """Analyze content for security and privacy risks."""
        return self.content_sanitizer.security_manager.analyze_content_risks(content)
