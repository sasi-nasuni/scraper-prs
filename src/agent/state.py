"""
State schema and data models for the PR summary agent.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field, HttpUrl


# Pydantic Models for structured data

class PRFile(BaseModel):
    """Represents a file changed in a PR."""
    path: str
    additions: int
    deletions: int
    status: str  # added, modified, deleted, renamed
    patch: Optional[str] = None  # unified diff (omitted for binary/very large files)


class PRCommit(BaseModel):
    """Represents a commit in a PR."""
    sha: str
    message: str
    author: str
    date: datetime


class PRReview(BaseModel):
    """Represents a PR review."""
    reviewer: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED
    body: Optional[str] = None
    submitted_at: datetime


class PRReviewComment(BaseModel):
    """Represents a review comment on a PR."""
    id: Optional[int] = None
    in_reply_to_id: Optional[int] = None
    author: str
    body: str
    path: Optional[str] = None
    line: Optional[int] = None
    start_line: Optional[int] = None
    diff_hunk: Optional[str] = None
    subject_type: Optional[str] = None  # "line" or "file"
    pull_request_review_id: Optional[int] = None
    created_at: datetime


class ReviewThread(BaseModel):
    """A threaded conversation from PR review comments."""
    file_path: Optional[str] = None
    line_range: Optional[str] = None  # e.g. "42" or "38-42"
    diff_hunk: Optional[str] = None   # Full code context from first comment
    comments: List["PRReviewComment"] = Field(default_factory=list)
    is_resolved: bool = False


class PRData(BaseModel):
    """Complete PR metadata."""
    number: int
    title: str
    body: Optional[str] = None
    author: str
    merged_at: datetime
    source_branch: str
    target_branch: str
    url: str
    files: List[PRFile] = Field(default_factory=list)
    commits: List[PRCommit] = Field(default_factory=list)
    reviews: List[PRReview] = Field(default_factory=list)
    review_comments: List[PRReviewComment] = Field(default_factory=list)


class JiraTicket(BaseModel):
    """Jira ticket information."""
    key: str  # e.g., PROJ-123
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    ticket_type: str  # Story, Bug, Task, etc.
    epic: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    url: str
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None


class FigmaFile(BaseModel):
    """Figma design file information."""
    file_key: str
    name: str
    url: str
    thumbnail_url: Optional[str] = None
    last_modified: Optional[datetime] = None
    version: Optional[str] = None


class ConfluencePage(BaseModel):
    """Confluence page information."""
    page_id: str
    title: str
    url: str
    excerpt: Optional[str] = None
    body: Optional[str] = None            # Full page content (markdown)
    content_summary: Optional[str] = None # LLM summary of body (when body is large)
    space_name: Optional[str] = None
    last_modified: Optional[datetime] = None
    author: Optional[str] = None


class FileStats(BaseModel):
    """Statistics for a category of files."""
    count: int = 0
    additions: int = 0
    deletions: int = 0


class FileCategoryStats(BaseModel):
    """File change statistics by category."""
    backend: FileStats = Field(default_factory=FileStats)
    frontend: FileStats = Field(default_factory=FileStats)
    tests: FileStats = Field(default_factory=FileStats)
    config: FileStats = Field(default_factory=FileStats)
    docs: FileStats = Field(default_factory=FileStats)
    other: FileStats = Field(default_factory=FileStats)


class PRSummary(BaseModel):
    """Generated summary for a PR."""
    pr_number: int
    summary_text: str
    coding_standards: Optional[str] = None
    architectural_patterns: Optional[str] = None
    breaking_changes: Optional[str] = None
    review_summary: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.now)


# TypedDict for LangGraph state (mutable, passed between nodes)

class AgentState(TypedDict, total=False):
    """
    Main state object passed between LangGraph nodes.
    Using TypedDict for LangGraph compatibility.
    """
    # Input
    repo_url: str
    repo_owner: str
    repo_name: str
    
    # PR processing
    pr_list: List[PRData]
    current_pr_index: int
    current_pr: Optional[PRData]
    
    # Extracted references
    jira_ids: List[str]
    figma_urls: List[str]
    confluence_urls: List[str]
    
    # Fetched context
    jira_tickets: List[JiraTicket]
    figma_files: List[FigmaFile]
    confluence_pages: List[ConfluencePage]
    
    # File analysis
    file_stats: Optional[FileCategoryStats]
    grouped_files: Dict[str, List[PRFile]]
    diff_summaries: Dict[str, str]  # category -> cumulative diff summary
    
    # Review threading
    review_threads: List[ReviewThread]
    
    # Generated content
    ai_summary: Optional[str]
    coding_standards: Optional[str]
    architectural_patterns: Optional[str]
    breaking_changes: Optional[str]
    review_summary: Optional[str]
    
    # Output
    summaries: List[PRSummary]
    output_files: List[str]
    
    # Error tracking
    errors: List[Dict[str, str]]
    warnings: List[str]
    
    # Metadata
    processing_started: datetime
    processing_completed: Optional[datetime]


# Helper functions for state management

def create_initial_state(repo_url: str) -> AgentState:
    """Create initial state for the agent."""
    return AgentState(
        repo_url=repo_url,
        repo_owner="",
        repo_name="",
        pr_list=[],
        current_pr_index=0,
        current_pr=None,
        jira_ids=[],
        figma_urls=[],
        confluence_urls=[],
        jira_tickets=[],
        figma_files=[],
        confluence_pages=[],
        file_stats=None,
        grouped_files={},
        diff_summaries={},
        review_threads=[],
        ai_summary=None,
        coding_standards=None,
        architectural_patterns=None,
        breaking_changes=None,
        review_summary=None,
        summaries=[],
        output_files=[],
        errors=[],
        warnings=[],
        processing_started=datetime.now(),
        processing_completed=None,
    )


def reset_pr_context(state: AgentState) -> AgentState:
    """Reset context-specific state for processing next PR."""
    state["current_pr"] = None
    state["jira_ids"] = []
    state["figma_urls"] = []
    state["confluence_urls"] = []
    state["jira_tickets"] = []
    state["figma_files"] = []
    state["confluence_pages"] = []
    state["file_stats"] = None
    state["grouped_files"] = {}
    state["diff_summaries"] = {}
    state["review_threads"] = []
    state["ai_summary"] = None
    state["coding_standards"] = None
    state["architectural_patterns"] = None
    state["breaking_changes"] = None
    state["review_summary"] = None
    
    return state


def add_error(state: AgentState, error_message: str, context: str = "", config: Dict[str, Any] = None) -> AgentState:
    """Add an error to the state if configured to do so.
    
    Args:
        state: Current agent state
        error_message: Error message
        context: Context where error occurred
        config: Agent configuration (to check error_handling settings)
    
    Returns:
        Updated state
    """
    # Only add error if logging is enabled in config
    if config:
        error_config = config.get("error_handling", {})
        if not error_config.get("log_errors", True):
            return state
    
    state["errors"].append({
        "message": error_message,
        "context": context,
        "timestamp": datetime.now().isoformat(),
    })
    return state


def add_warning(state: AgentState, warning_message: str) -> AgentState:
    """Add a warning to the state."""
    state["warnings"].append(warning_message)
    return state


def should_continue_on_error(config: Dict[str, Any]) -> bool:
    """Check if processing should continue on error.
    
    Args:
        config: Agent configuration
    
    Returns:
        True if should continue, False if should raise exception
    """
    error_config = config.get("error_handling", {})
    return error_config.get("continue_on_error", True)


def should_log_errors(config: Dict[str, Any]) -> bool:
    """Check if errors should be logged.
    
    Args:
        config: Agent configuration
    
    Returns:
        True if should log errors
    """
    error_config = config.get("error_handling", {})
    return error_config.get("log_errors", True)


def should_generate_partial_summaries(config: Dict[str, Any]) -> bool:
    """Check if partial summaries should be generated.
    
    Args:
        config: Agent configuration
    
    Returns:
        True if should generate partial summaries
    """
    error_config = config.get("error_handling", {})
    return error_config.get("generate_partial_summaries", True)


def should_include_errors_in_summary(config: Dict[str, Any]) -> bool:
    """Check if errors should be included in summary output.
    
    Args:
        config: Agent configuration
    
    Returns:
        True if should include errors
    """
    error_config = config.get("error_handling", {})
    return error_config.get("include_errors_in_summary", False)
