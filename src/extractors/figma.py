"""
Figma URL extraction utilities.
"""
import re
from typing import List, Optional, Set
from urllib.parse import urlparse


# Default regex patterns for different Figma URL formats
DEFAULT_FIGMA_PATTERNS = [
    r'https?://(?:www\.)?figma\.com/file/([a-zA-Z0-9]+)/([^?\s]+)',
    r'https?://(?:www\.)?figma\.com/design/([a-zA-Z0-9]+)/([^?\s]+)',
    r'https?://(?:www\.)?figma\.com/proto/([a-zA-Z0-9]+)/([^?\s]+)'
]


def extract_figma_urls(text: str, patterns: Optional[List[str]] = None) -> List[str]:
    """
    Extract Figma URLs from text.
    
    Args:
        text: Text to search for Figma URLs
        patterns: Optional list of regex patterns to use (defaults to DEFAULT_FIGMA_PATTERNS)
    
    Returns:
        List of unique Figma URLs found
    """
    if not text:
        return []
    
    urls: Set[str] = set()
    pattern_list = patterns if patterns else DEFAULT_FIGMA_PATTERNS
    
    # Find all Figma file URLs
    for pattern_str in pattern_list:
        pattern = re.compile(pattern_str)
        matches = pattern.finditer(text)
        for match in matches:
            urls.add(match.group(0))
    
    return list(urls)


def extract_figma_file_key(figma_url: str, patterns: Optional[List[str]] = None) -> str:
    """
    Extract the file key from a Figma URL.
    
    Args:
        figma_url: Full Figma URL
        patterns: Optional list of regex patterns to use (defaults to DEFAULT_FIGMA_PATTERNS)
    
    Returns:
        Figma file key (alphanumeric ID)
    """
    pattern_list = patterns if patterns else DEFAULT_FIGMA_PATTERNS
    # Try each pattern
    for pattern_str in pattern_list:
        pattern = re.compile(pattern_str)
        match = pattern.match(figma_url)
        if match:
            return match.group(1)
    
    return ""


def extract_figma_file_name(figma_url: str, patterns: Optional[List[str]] = None) -> str:
    """
    Extract the file name from a Figma URL.
    
    Args:
        figma_url: Full Figma URL
        patterns: Optional list of regex patterns to use (defaults to DEFAULT_FIGMA_PATTERNS)
    
    Returns:
        Figma file name (URL slug)
    """
    pattern_list = patterns if patterns else DEFAULT_FIGMA_PATTERNS
    # Try each pattern
    for pattern_str in pattern_list:
        pattern = re.compile(pattern_str)
        match = pattern.match(figma_url)
        if match:
            # Replace hyphens with spaces and decode URL encoding
            name = match.group(2).replace('-', ' ')
            # Remove query parameters if present
            name = name.split('?')[0]
            return name
    
    return ""


def validate_figma_url(url: str, patterns: Optional[List[str]] = None) -> bool:
    """
    Validate that a URL is a valid Figma URL.
    
    Args:
        url: URL to validate
        patterns: Optional list of regex patterns to use (defaults to DEFAULT_FIGMA_PATTERNS)
    
    Returns:
        True if valid Figma URL
    """
    pattern_list = patterns if patterns else DEFAULT_FIGMA_PATTERNS
    for pattern_str in pattern_list:
        pattern = re.compile(pattern_str)
        if pattern.match(url):
            return True
    return False


def normalize_figma_url(url: str) -> str:
    """
    Normalize a Figma URL (remove query parameters, fragments).
    
    Args:
        url: Figma URL to normalize
    
    Returns:
        Normalized Figma URL
    """
    parsed = urlparse(url)
    # Reconstruct without query and fragment
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return normalized
