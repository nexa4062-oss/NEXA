"""Input validation and security utilities."""
import re
import html
from typing import Optional


PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+above",
    r"disregard\s+(all\s+)?previous",
    r"you\s+are\s+now",
    r"new\s+instructions:",
    r"system\s*:\s*",
    r"<\s*system\s*>",
    r"</?\s*prompt\s*>",
    r"jailbreak",
    r"DAN\s+mode",
]

SQL_INJECTION_PATTERNS = [
    r"(\b(union|select|insert|update|delete|drop|alter|exec|execute)\b.*\b(from|into|table|database)\b)",
    r"(--|;|/\*|\*/)",
    r"(\b(or|and)\b\s+\d+\s*=\s*\d+)",
    r"('\s*(or|and)\s+')",
]

XSS_PATTERNS = [
    r"<\s*script",
    r"javascript\s*:",
    r"on(load|error|click|mouse|focus|blur)\s*=",
    r"<\s*iframe",
    r"<\s*object",
    r"<\s*embed",
]

PATH_TRAVERSAL_PATTERNS = [
    r"\.\./",
    r"\.\.\\",
    r"%2e%2e",
    r"%252e%252e",
    r"\.\.%2f",
]


def sanitize_input(text: str) -> str:
    """Sanitize user input for general use."""
    text = html.escape(text)
    text = text.strip()
    return text


def check_prompt_injection(text: str) -> Optional[str]:
    """Check for prompt injection attempts. Returns detected pattern or None."""
    text_lower = text.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            return pattern
    return None


def check_sql_injection(text: str) -> Optional[str]:
    """Check for SQL injection attempts."""
    text_lower = text.lower()
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            return pattern
    return None


def check_xss(text: str) -> Optional[str]:
    """Check for XSS attempts."""
    text_lower = text.lower()
    for pattern in XSS_PATTERNS:
        if re.search(pattern, text_lower):
            return pattern
    return None


def check_path_traversal(path: str) -> bool:
    """Check for path traversal attempts."""
    for pattern in PATH_TRAVERSAL_PATTERNS:
        if re.search(pattern, path, re.IGNORECASE):
            return True
    return False


def validate_filename(filename: str) -> bool:
    """Validate a filename is safe."""
    if not filename:
        return False
    if check_path_traversal(filename):
        return False
    if any(c in filename for c in ['<', '>', ':', '"', '|', '?', '*', '\x00']):
        return False
    if filename.startswith('.'):
        return False
    return True


def sanitize_for_model(text: str) -> str:
    """Sanitize text before sending to model context. Treats it as DATA not instructions."""
    injection = check_prompt_injection(text)
    if injection:
        return f"[Content contained potential prompt injection attempt - sanitized]"
    return text
