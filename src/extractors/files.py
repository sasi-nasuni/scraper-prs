"""
File categorization utilities for PR files.
"""
from fnmatch import fnmatch
from typing import Dict, List, Optional

from src.agent.state import FileStats, FileCategoryStats, PRFile


def categorize_files(
    files: List[PRFile],
    category_patterns: Dict[str, List[str]]
) -> FileCategoryStats:
    """
    Categorize PR files based on patterns.
    
    Args:
        files: List of PRFile objects
        category_patterns: Dict mapping category names to glob patterns
    
    Returns:
        FileCategoryStats with categorized file statistics
    """
    stats = FileCategoryStats()
    
    for file in files:
        categorized = False
        
        # Check each category
        for category_name, patterns in category_patterns.items():
            # Check if file matches any pattern for this category
            for pattern in patterns:
                if fnmatch(file.path, pattern):
                    # Update stats for this category
                    category_stats = getattr(stats, category_name, None)
                    if category_stats:
                        category_stats.count += 1
                        category_stats.additions += file.additions
                        category_stats.deletions += file.deletions
                    
                    categorized = True
                    break
            
            if categorized:
                break
        
        # If not categorized, add to "other"
        if not categorized:
            stats.other.count += 1
            stats.other.additions += file.additions
            stats.other.deletions += file.deletions
    
    return stats


def group_files_by_category(
    files: List[PRFile],
    category_patterns: Dict[str, List[str]]
) -> Dict[str, List[PRFile]]:
    """
    Group PR files into categories, sorted by total changes (descending).

    Each file is placed into the *first* matching category (same precedence
    order as ``categorize_files``).  Files that don't match any pattern go
    into the ``other`` bucket.

    Args:
        files: List of PRFile objects.
        category_patterns: Dict mapping category names to glob patterns.

    Returns:
        OrderedDict-style dict ``{category_name: [PRFile, ...]}``.  Only
        categories that contain at least one file are included.  Within
        each category the files are sorted by ``additions + deletions``
        descending.
    """
    buckets: Dict[str, List[PRFile]] = {}

    for file in files:
        placed = False
        for category_name, patterns in category_patterns.items():
            for pattern in patterns:
                if fnmatch(file.path, pattern):
                    buckets.setdefault(category_name, []).append(file)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            buckets.setdefault("other", []).append(file)

    # Sort files within each category by total changes descending
    for category in buckets:
        buckets[category].sort(
            key=lambda f: f.additions + f.deletions, reverse=True
        )

    return buckets


def summarize_file_changes(stats: FileCategoryStats) -> str:
    """
    Generate a human-readable summary of file changes.
    
    Args:
        stats: FileCategoryStats object
    
    Returns:
        Summary string
    """
    summaries = []
    
    categories = [
        ('backend', 'Backend'),
        ('frontend', 'Frontend'),
        ('tests', 'Tests'),
        ('config', 'Configuration'),
        ('docs', 'Documentation'),
        ('other', 'Other'),
    ]
    
    for attr_name, display_name in categories:
        category_stats = getattr(stats, attr_name)
        if category_stats.count > 0:
            summaries.append(
                f"{display_name}: {category_stats.count} files "
                f"(+{category_stats.additions}/-{category_stats.deletions})"
            )
    
    return ', '.join(summaries) if summaries else "No files changed"


def get_total_stats(stats: Optional[FileCategoryStats]) -> Dict[str, int]:
    """
    Calculate total statistics across all categories.
    
    Args:
        stats: FileCategoryStats object or None
    
    Returns:
        Dict with total_files, total_additions, total_deletions
    """
    # Handle None case
    if stats is None:
        return {
            'total_files': 0,
            'total_additions': 0,
            'total_deletions': 0,
        }
    
    total_files = 0
    total_additions = 0
    total_deletions = 0
    
    for category_name in ['backend', 'frontend', 'tests', 'config', 'docs', 'other']:
        category_stats = getattr(stats, category_name)
        total_files += category_stats.count
        total_additions += category_stats.additions
        total_deletions += category_stats.deletions
    
    return {
        'total_files': total_files,
        'total_additions': total_additions,
        'total_deletions': total_deletions,
    }


def is_breaking_change_file(file_path: str) -> bool:
    """
    Determine if a file change might indicate breaking changes.
    
    Args:
        file_path: Path to the file
    
    Returns:
        True if file might contain breaking changes
    """
    # Files that often indicate breaking changes
    breaking_indicators = [
        '**/migration*.py',
        '**/migrations/*.sql',
        '**/schema*.sql',
        '**/api/**',
        '**/*-api.ts',
        '**/*-interface.ts',
        '**/*.proto',
        '**/openapi.yaml',
        '**/swagger.yaml',
        'BREAKING*.md',
    ]
    
    for pattern in breaking_indicators:
        if fnmatch(file_path, pattern):
            return True
    
    return False
