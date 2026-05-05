"""Utility helpers: short code generation, URL validation, user-agent parsing."""

import string
import random
import re
from urllib.parse import urlparse
from user_agents import parse as parse_ua


def generate_short_code(length: int = 7) -> str:
    """Generate a random short code (a-z, A-Z, 0-9)."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def validate_url(url: str) -> bool:
    """Validate that a string is a proper URL."""
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def parse_user_agent(ua_string: str) -> dict:
    """Parse user-agent string to extract browser and device info."""
    ua = parse_ua(ua_string)
    device = "Mobile" if ua.is_mobile else ("Tablet" if ua.is_tablet else "Desktop")
    browser = ua.browser.family or "Unknown"
    os_info = ua.os.family or "Unknown"
    return {
        "device": device,
        "browser": browser,
        "os": os_info,
    }


def sanitize_alias(alias: str) -> str:
    """Sanitize custom alias input."""
    return re.sub(r"[^a-zA-Z0-9_-]", "", alias)
