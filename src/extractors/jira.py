"""
Jira ticket ID extraction utilities.
"""
import re
from typing import List, Optional, Set


# Default regex pattern for Jira ticket IDs (e.g., PROJ-123, ABC-456)
DEFAULT_JIRA_PATTERN = r'\b([A-Z]{2,10}-\d+)\b'


def extract_jira_ids(text: str, pattern: Optional[str] = None) -> List[str]:
    """
    Extract Jira ticket IDs from text.
    
    Args:
        text: Text to search for Jira IDs
        pattern: Optional regex pattern to use (defaults to DEFAULT_JIRA_PATTERN)
    
    Returns:
        List of unique Jira ticket IDs found
    """
    if not text:
        return []
    
    jira_pattern = re.compile(pattern if pattern else DEFAULT_JIRA_PATTERN)
    matches = jira_pattern.findall(text)
    # Return unique IDs, preserving order
    seen = set()
    unique_ids = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            unique_ids.append(match)
    
    return unique_ids


def extract_jira_ids_from_pr(
    pr_title: str,
    pr_body: str,
    commit_messages: List[str],
    pattern: Optional[str] = None
) -> List[str]:
    """
    Extract Jira IDs from all PR-related text.
    
    Args:
        pr_title: PR title
        pr_body: PR description/body
        commit_messages: List of commit messages
        pattern: Optional regex pattern to use (defaults to DEFAULT_JIRA_PATTERN)
    
    Returns:
        List of unique Jira ticket IDs
    """
    all_ids: Set[str] = set()
    
    # Extract from PR title
    all_ids.update(extract_jira_ids(pr_title, pattern))
    
    # Extract from PR body
    all_ids.update(extract_jira_ids(pr_body, pattern))
    
    # Extract from commit messages
    for message in commit_messages:
        all_ids.update(extract_jira_ids(message, pattern))
    
    return list(all_ids)


def validate_jira_id(jira_id: str, pattern: Optional[str] = None) -> bool:
    """
    Validate that a string matches Jira ticket ID format.
    
    Args:
        jira_id: String to validate
        pattern: Optional regex pattern to use (defaults to DEFAULT_JIRA_PATTERN)
    
    Returns:
        True if valid Jira ID format
    """
    jira_pattern = re.compile(pattern if pattern else DEFAULT_JIRA_PATTERN)
    return bool(jira_pattern.match(jira_id))


def format_jira_url(jira_id: str, jira_base_url: str) -> str:
    """
    Format a Jira ticket URL.
    
    Args:
        jira_id: Jira ticket ID (e.g., PROJ-123)
        jira_base_url: Base Jira URL (e.g., https://company.atlassian.net)
    
    Returns:
        Full Jira ticket URL
    """
    # Remove trailing slash from base URL if present
    base = jira_base_url.rstrip('/')
    return f"{base}/browse/{jira_id}"
