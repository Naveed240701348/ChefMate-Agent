"""
ChefMate-Agent — Utility helpers

General-purpose helpers used across routes and services.
"""

import re
import html
import unicodedata
from datetime import datetime


def sanitize_input(text: str, max_length: int = 2000) -> str:
    """
    Strip dangerous characters, collapse whitespace, and enforce a length cap.
    Returns the cleaned string.
    """
    if not isinstance(text, str):
        return ""
    # Escape HTML entities
    text = html.escape(text, quote=True)
    # Remove non-printable / control characters (keep newlines)
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in "\n\t")
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Trim
    text = text.strip()
    return text[:max_length]


def format_timestamp(dt: datetime | None = None) -> str:
    """Return a human-readable timestamp string like '08 Jul 2026, 11:42 AM'."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%d %b %Y, %I:%M %p")


def build_error_response(message: str, status: int = 500) -> dict:
    """Construct a standard JSON error envelope."""
    return {
        "success": False,
        "error": message,
        "timestamp": format_timestamp(),
    }, status


def build_success_response(data: dict) -> dict:
    """Construct a standard JSON success envelope."""
    return {
        "success": True,
        "timestamp": format_timestamp(),
        **data,
    }
