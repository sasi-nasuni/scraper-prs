"""
Tests for file categorization.
"""
import pytest

from src.agent.state import PRFile, FileStats
from src.extractors.files import (
    categorize_files,
    group_files_by_category,
    summarize_file_changes,
    get_total_stats,
    is_breaking_change_file,
)


def test_categorize_files_backend():
    """Test categorizing backend files."""
    files = [
        PRFile(path="src/main.py", additions=10, deletions=5, status="modified"),
        PRFile(path="api/server.py", additions=20, deletions=0, status="added"),
    ]
    
    category_patterns = {
        "backend": ["**/*.py"],
        "frontend": ["**/*.js"],
        "tests": [],
        "config": [],
        "docs": [],
        "other": [],
    }
    
    stats = categorize_files(files, category_patterns)
    
    assert stats.backend.count == 2
    assert stats.backend.additions == 30
    assert stats.backend.deletions == 5


def test_categorize_files_mixed():
    """Test categorizing mixed file types."""
    files = [
        PRFile(path="src/main.py", additions=10, deletions=5, status="modified"),
        PRFile(path="ui/app.js", additions=15, deletions=3, status="modified"),
        PRFile(path="tests/test_main.py", additions=5, deletions=0, status="added"),
    ]
    
    category_patterns = {
        "backend": ["**/*.py"],
        "frontend": ["**/*.js"],
        "tests": ["**/test_*.py"],
        "config": [],
        "docs": [],
        "other": [],
    }
    
    stats = categorize_files(files, category_patterns)
    
    # Note: test file matches both backend and tests, goes to tests (first match)
    assert stats.backend.count == 1
    assert stats.frontend.count == 1
    assert stats.tests.count == 1


def test_summarize_file_changes():
    """Test summarizing file changes."""
    from src.agent.state import FileCategoryStats
    
    stats = FileCategoryStats()
    stats.backend.count = 5
    stats.backend.additions = 100
    stats.backend.deletions = 20
    stats.frontend.count = 3
    stats.frontend.additions = 50
    stats.frontend.deletions = 10
    
    summary = summarize_file_changes(stats)
    
    assert "Backend: 5 files" in summary
    assert "+100/-20" in summary
    assert "Frontend: 3 files" in summary


def test_get_total_stats():
    """Test calculating total statistics."""
    from src.agent.state import FileCategoryStats, FileStats
    
    stats = FileCategoryStats()
    stats.backend = FileStats(count=5, additions=100, deletions=20)
    stats.frontend = FileStats(count=3, additions=50, deletions=10)
    stats.tests = FileStats(count=2, additions=30, deletions=5)
    
    totals = get_total_stats(stats)
    
    assert totals["total_files"] == 10
    assert totals["total_additions"] == 180
    assert totals["total_deletions"] == 35


def test_is_breaking_change_file():
    """Test identifying breaking change indicators."""
    assert is_breaking_change_file("migrations/001_add_column.sql") is True
    assert is_breaking_change_file("api/endpoints.py") is True
    assert is_breaking_change_file("src/types/api-interface.ts") is True
    assert is_breaking_change_file("src/main.py") is False
    assert is_breaking_change_file("README.md") is False


def test_group_files_by_category_basic():
    """Test grouping files by category."""
    files = [
        PRFile(path="src/main.py", additions=50, deletions=20, status="modified"),
        PRFile(path="ui/app.js", additions=15, deletions=3, status="modified"),
        PRFile(path="config/settings.yaml", additions=2, deletions=1, status="modified"),
        PRFile(path="src/helper.py", additions=5, deletions=2, status="modified"),
    ]

    category_patterns = {
        "backend": ["**/*.py"],
        "frontend": ["**/*.js"],
        "tests": [],
        "config": ["**/*.yaml"],
        "docs": [],
    }

    grouped = group_files_by_category(files, category_patterns)

    assert "backend" in grouped
    assert "frontend" in grouped
    assert "config" in grouped
    assert len(grouped["backend"]) == 2
    assert len(grouped["frontend"]) == 1
    assert len(grouped["config"]) == 1
    # Sorted by changes descending within group
    assert grouped["backend"][0].path == "src/main.py"
    assert grouped["backend"][1].path == "src/helper.py"


def test_group_files_by_category_uncategorized():
    """Files that don't match any pattern go to 'other'."""
    files = [
        PRFile(path="random.xyz", additions=1, deletions=0, status="added"),
    ]
    category_patterns = {"backend": ["**/*.py"]}
    grouped = group_files_by_category(files, category_patterns)

    assert "other" in grouped
    assert len(grouped["other"]) == 1


def test_group_files_by_category_sorted_by_changes():
    """Files within each group are sorted by total changes descending."""
    files = [
        PRFile(path="src/a.py", additions=2, deletions=1, status="modified"),
        PRFile(path="src/b.py", additions=100, deletions=50, status="modified"),
        PRFile(path="src/c.py", additions=10, deletions=5, status="modified"),
    ]
    category_patterns = {"backend": ["**/*.py"]}
    grouped = group_files_by_category(files, category_patterns)

    assert [f.path for f in grouped["backend"]] == ["src/b.py", "src/c.py", "src/a.py"]
