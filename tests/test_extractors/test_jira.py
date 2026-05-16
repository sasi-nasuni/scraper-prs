"""
Tests for Jira extractor.
"""
import pytest

from src.extractors.jira import (
    extract_jira_ids,
    extract_jira_ids_from_pr,
    validate_jira_id,
    format_jira_url,
)


def test_extract_jira_ids_single():
    """Test extracting a single Jira ID."""
    text = "This PR fixes PROJ-123"
    result = extract_jira_ids(text)
    assert result == ["PROJ-123"]


def test_extract_jira_ids_multiple():
    """Test extracting multiple Jira IDs."""
    text = "This PR fixes PROJ-123 and PROJ-456"
    result = extract_jira_ids(text)
    assert set(result) == {"PROJ-123", "PROJ-456"}


def test_extract_jira_ids_with_prefix():
    """Test extracting Jira IDs with conventional commit prefix."""
    text = "feat: PROJ-789 Add new feature"
    result = extract_jira_ids(text)
    assert result == ["PROJ-789"]


def test_extract_jira_ids_none():
    """Test extracting when no Jira IDs present."""
    text = "This is a regular PR without tickets"
    result = extract_jira_ids(text)
    assert result == []


def test_extract_jira_ids_empty_string():
    """Test extracting from empty string."""
    result = extract_jira_ids("")
    assert result == []


def test_extract_jira_ids_from_pr():
    """Test extracting Jira IDs from PR components."""
    pr_title = "feat: PROJ-100 Add feature"
    pr_body = "Fixes PROJ-200"
    commit_messages = ["PROJ-300: Initial commit", "Update tests"]
    
    result = extract_jira_ids_from_pr(pr_title, pr_body, commit_messages)
    
    assert set(result) == {"PROJ-100", "PROJ-200", "PROJ-300"}


def test_validate_jira_id_valid():
    """Test validating valid Jira IDs."""
    assert validate_jira_id("PROJ-123") is True
    assert validate_jira_id("ABC-456") is True
    assert validate_jira_id("LONGNAME-789") is True


def test_validate_jira_id_invalid():
    """Test validating invalid Jira IDs."""
    assert validate_jira_id("proj-123") is False  # Lowercase
    assert validate_jira_id("P-123") is False  # Too short
    assert validate_jira_id("PROJ123") is False  # Missing dash
    assert validate_jira_id("PROJ-") is False  # Missing number


def test_format_jira_url():
    """Test formatting Jira URL."""
    url = format_jira_url("PROJ-123", "https://company.atlassian.net")
    assert url == "https://company.atlassian.net/browse/PROJ-123"


def test_format_jira_url_trailing_slash():
    """Test formatting Jira URL with trailing slash in base URL."""
    url = format_jira_url("PROJ-123", "https://company.atlassian.net/")
    assert url == "https://company.atlassian.net/browse/PROJ-123"
