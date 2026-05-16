"""
Pytest configuration and fixtures.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.agent.state import (
    PRData,
    PRFile,
    PRCommit,
    JiraTicket,
    FigmaFile,
    ConfluencePage,
)


@pytest.fixture
def sample_pr_data():
    """Sample PR data for testing."""
    return PRData(
        number=123,
        title="feat: Add new feature",
        body="This PR adds a new feature.\n\nJira: PROJ-456",
        author="testuser",
        merged_at=datetime(2026, 4, 1, 12, 0, 0),
        source_branch="feature/new-feature",
        target_branch="main",
        url="https://github.com/owner/repo/pull/123",
        files=[
            PRFile(path="src/main.py", additions=50, deletions=10, status="modified"),
            PRFile(path="tests/test_main.py", additions=30, deletions=0, status="added"),
        ],
        commits=[
            PRCommit(
                sha="abc123",
                message="feat: Add new feature",
                author="Test User",
                date=datetime(2026, 4, 1, 10, 0, 0),
            )
        ],
        reviews=[],
        review_comments=[],
    )


@pytest.fixture
def sample_jira_ticket():
    """Sample Jira ticket for testing."""
    return JiraTicket(
        key="PROJ-456",
        title="Implement new feature",
        description="As a user, I want a new feature",
        status="Done",
        priority="High",
        ticket_type="Story",
        url="https://company.atlassian.net/browse/PROJ-456",
    )


@pytest.fixture
def sample_figma_file():
    """Sample Figma file for testing."""
    return FigmaFile(
        file_key="abc123xyz",
        name="Design System",
        url="https://www.figma.com/file/abc123xyz",
    )


@pytest.fixture
def sample_confluence_page():
    """Sample Confluence page for testing."""
    return ConfluencePage(
        page_id="123456",
        title="Feature Documentation",
        url="https://company.atlassian.net/wiki/spaces/PROJ/pages/123456",
        excerpt="This page documents the new feature",
    )


@pytest.fixture
def mock_mcp_manager():
    """Mock MCP client manager."""
    manager = MagicMock()
    manager.call_tool = AsyncMock(return_value={})
    manager.is_connected = MagicMock(return_value=True)
    return manager


@pytest.fixture
def agent_config():
    """Sample agent configuration."""
    return {
        "llm": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.7,
            "max_tokens": 4096,
        },
        "processing": {
            "max_prs": 5,
            "enable_parallel": True,
        },
        "file_categories": {
            "backend": ["**/*.py"],
            "frontend": ["**/*.js", "**/*.tsx"],
            "tests": ["**/*.test.*", "**/test_*.py"],
            "config": ["**/*.json", "**/*.yaml"],
            "docs": ["**/*.md"],
            "other": [],
        },
        "output": {
            "directory": "outputs",
        },
        "templates": {
            "directory": "templates",
        },
        "jira_url": "https://company.atlassian.net",
        "atlassian_cloud_id": "test-cloud-id-1234",
    }
