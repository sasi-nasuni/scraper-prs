"""
Pydantic models for API request/response schemas.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class PRSelectionMode(str, Enum):
    """How PRs are selected for processing."""
    LATEST = "latest"
    LABEL = "label"
    PR_NUMBER = "pr_number"
    PR_URLS = "pr_urls"


class JobStatus(str, Enum):
    """Status of a processing job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Request Models ──────────────────────────────────────────────────────────


class GenerateRequest(BaseModel):
    """Request to generate PR summaries."""
    repo_url: str = Field(
        default="",
        description="GitHub repository URL (e.g., https://github.com/owner/repo). Not required for pr_urls mode.",
        examples=["https://github.com/nasuni/portal"],
    )
    mode: PRSelectionMode = Field(
        default=PRSelectionMode.LATEST,
        description="PR selection mode: latest merged, by label, or specific PR number",
    )
    pr_number: Optional[int] = Field(
        default=None,
        description="Specific PR number (required when mode=pr_number)",
        gt=0,
    )
    label: Optional[str] = Field(
        default=None,
        description="GitHub label to filter PRs (required when mode=label)",
    )
    max_prs: int = Field(
        default=5,
        description="Maximum number of PRs to process",
        ge=1,
        le=50,
    )
    output_dir: Optional[str] = Field(
        default=None,
        description="Output directory for summaries (defaults to 'outputs')",
    )
    pr_urls: Optional[List[str]] = Field(
        default=None,
        description="List of GitHub PR URLs (required when mode=pr_urls)",
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose/debug logging",
    )

    @model_validator(mode="after")
    def validate_mode_fields(self):
        """Validate fields based on the selected mode."""
        import re

        # repo_url validation (not required for pr_urls mode)
        if self.mode != PRSelectionMode.PR_URLS:
            pattern = r"^https://github\.com/[\w.\-]+/[\w.\-]+$"
            if not re.match(pattern, self.repo_url.rstrip("/")):
                raise ValueError(
                    "Invalid GitHub URL. Expected format: https://github.com/owner/repo"
                )
            self.repo_url = self.repo_url.rstrip("/")
        else:
            self.repo_url = self.repo_url.rstrip("/") if self.repo_url else ""

        # pr_number validation
        if self.mode == PRSelectionMode.PR_NUMBER and self.pr_number is None:
            raise ValueError("pr_number is required when mode is 'pr_number'")

        # label validation
        if self.mode == PRSelectionMode.LABEL and (self.label is None or self.label.strip() == ""):
            raise ValueError("label is required when mode is 'label'")

        # pr_urls validation
        if self.mode == PRSelectionMode.PR_URLS:
            if not self.pr_urls or len(self.pr_urls) == 0:
                raise ValueError("At least one PR URL is required when mode is 'pr_urls'")
            pr_url_pattern = r"^https://github\.com/[\w.\-]+/[\w.\-]+/pull/\d+$"
            for url in self.pr_urls:
                clean_url = url.strip().rstrip("/")
                if not re.match(pr_url_pattern, clean_url):
                    raise ValueError(
                        f"Invalid PR URL: {url}. Expected format: https://github.com/owner/repo/pull/123"
                    )

        return self


# ── Response Models ─────────────────────────────────────────────────────────


class JobCreatedResponse(BaseModel):
    """Response when a job is successfully created."""
    job_id: str
    status: JobStatus = JobStatus.PENDING
    message: str = "Job created successfully"
    created_at: datetime


class PRSummaryResult(BaseModel):
    """Summary result for a single PR."""
    pr_number: int
    title: Optional[str] = None
    summary_file: Optional[str] = None
    status: str = "completed"
    error: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Response for job status query."""
    job_id: str
    status: JobStatus
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Percentage complete")
    current_step: Optional[str] = None
    repo_url: str
    mode: PRSelectionMode
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: List[PRSummaryResult] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    total_prs: int = 0
    processed_prs: int = 0
    logs: List[str] = Field(default_factory=list, description="Recent log messages")


class JobListResponse(BaseModel):
    """Response for listing all jobs."""
    jobs: List[JobStatusResponse]
    total: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "0.1.0"
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None


# ── MCP Tool Testing Models ─────────────────────────────────────────────────


class MCPToolInfo(BaseModel):
    """Information about a single MCP tool."""
    name: str
    description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON Schema for the tool's input parameters"
    )


class MCPServerStatus(BaseModel):
    """Status of a single MCP server."""
    name: str
    connected: bool
    tool_count: int
    description: Optional[str] = None


class MCPServersResponse(BaseModel):
    """Response listing all MCP server statuses."""
    servers: List[MCPServerStatus]


class MCPToolsResponse(BaseModel):
    """Response listing tools for a server."""
    server: str
    tools: List[MCPToolInfo]
    total: int


class MCPToolCallRequest(BaseModel):
    """Request to call a specific MCP tool."""
    server: str = Field(..., description="MCP server name (e.g. 'github', 'atlassian')")
    tool: str = Field(..., description="Tool name to invoke")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Arguments to pass to the tool"
    )


class MCPToolCallResponse(BaseModel):
    """Response from calling an MCP tool."""
    server: str
    tool: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None


# ── GitHub Direct API Models ────────────────────────────────────────────────


class CommentType(str, Enum):
    """Type of PR comments to fetch."""
    REVIEW = "review"        # Review (diff-level) comments
    ISSUE = "issue"          # Issue-level (conversation) comments
    ALL = "all"              # Both types combined


class GitHubPRCommentsRequest(BaseModel):
    """Request to fetch PR comments directly from GitHub API."""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    pull_number: int = Field(..., gt=0, description="Pull request number")
    comment_type: CommentType = Field(
        default=CommentType.ALL,
        description="Type of comments: review (diff-level), issue (conversation), or all",
    )
    page: Optional[int] = Field(default=None, ge=1, description="Page number (omit to fetch ALL pages)")
    per_page: int = Field(default=100, ge=1, le=100, description="Results per page (max 100)")


class GitHubPRCommentsResponse(BaseModel):
    """Response containing PR comments from GitHub API."""
    owner: str
    repo: str
    pull_number: int
    comment_type: str
    comments: List[Dict[str, Any]]
    total_count: int
    page: Optional[int] = None
    per_page: int = 100
    total_pages_fetched: Optional[int] = None
    duration_ms: float


class GitHubPRCommitsRequest(BaseModel):
    """Request to fetch PR commits directly from GitHub API."""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    pull_number: int = Field(..., gt=0, description="Pull request number")
    page: Optional[int] = Field(default=None, ge=1, description="Page number (omit to fetch ALL pages)")
    per_page: int = Field(default=100, ge=1, le=100, description="Results per page (max 100)")


class GitHubPRCommitsResponse(BaseModel):
    """Response containing PR commits from GitHub API."""
    owner: str
    repo: str
    pull_number: int
    commits: List[Dict[str, Any]]
    total_count: int
    page: Optional[int] = None
    per_page: int = 100
    total_pages_fetched: Optional[int] = None
    duration_ms: float


# ── Agent Config Models ─────────────────────────────────────────────────────


class LLMConfig(BaseModel):
    """LLM settings."""
    provider: str = Field(default="openai", description="LLM provider: openai or anthropic")
    model: str = Field(default="gpt-4.1", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=4096, ge=1, description="Max tokens")
    streaming: bool = Field(default=False, description="Stream responses")
    base_url: Optional[str] = Field(default=None, description="Custom base URL for the LLM API")


class ProcessingConfig(BaseModel):
    """Processing settings."""
    max_prs: int = Field(default=5, ge=1, le=50, description="Max PRs to process per run")
    enable_parallel: bool = Field(default=True, description="Enable parallel processing")
    parallel_workers: int = Field(default=3, ge=1, le=10, description="Number of parallel workers")
    timeout_per_pr: int = Field(default=300, ge=30, description="Timeout per PR in seconds")


class TemplatesConfig(BaseModel):
    """Template settings."""
    main_template: str = Field(default="pr_summary_template.md", description="Main summary template file")
    fallback_template: str = Field(default="pr_summary_fallback.md", description="Fallback template file")
    use_fallback_when_missing: bool = Field(default=True, description="Use fallback template when main is missing")


class JiraExtractionConfig(BaseModel):
    """Jira extraction settings."""
    pattern: str = Field(default=r"[A-Z]{2,10}-\d+", description="Jira ticket ID regex pattern")
    search_in: List[str] = Field(
        default=["pr_title", "pr_body", "commit_messages"],
        description="Where to search for Jira IDs",
    )


class FigmaExtractionConfig(BaseModel):
    """Figma extraction settings."""
    patterns: List[str] = Field(
        default=[
            r"https://www\.figma\.com/file/[^/]+/[^?\s]+",
            r"https://www\.figma\.com/design/[^/]+/[^?\s]+",
            r"https://www\.figma\.com/proto/[^/]+/[^?\s]+",
        ],
        description="Figma URL regex patterns",
    )
    search_in: List[str] = Field(
        default=["pr_title", "pr_body"],
        description="Where to search for Figma URLs",
    )


class ConfluenceExtractionConfig(BaseModel):
    """Confluence extraction settings."""
    strategies: List[str] = Field(
        default=["jira_ticket_id", "pr_title_keywords", "explicit_urls"],
        description="Search strategies for Confluence pages",
    )
    max_pages_per_pr: int = Field(default=3, ge=1, le=20, description="Max Confluence pages per PR")


class ExtractionConfig(BaseModel):
    """Extraction settings."""
    jira: JiraExtractionConfig = Field(default_factory=JiraExtractionConfig)
    figma: FigmaExtractionConfig = Field(default_factory=FigmaExtractionConfig)
    confluence: ConfluenceExtractionConfig = Field(default_factory=ConfluenceExtractionConfig)


class RetryConfig(BaseModel):
    """Retry / exponential-backoff settings."""
    max_attempts: int = Field(default=1, ge=1, le=10, description="Retry attempts (1 = no retries)")
    initial_delay: int = Field(default=2, ge=1, description="Initial delay in seconds")
    max_delay: int = Field(default=30, ge=1, description="Max delay in seconds")
    exponential_base: int = Field(default=2, ge=2, le=5, description="Backoff multiplier")


class ErrorHandlingConfig(BaseModel):
    """Error handling settings."""
    continue_on_error: bool = Field(default=True, description="Continue processing next PRs on error")
    generate_partial_summaries: bool = Field(default=True, description="Generate summaries even without rich context")
    log_errors: bool = Field(default=True, description="Log errors to console/file")
    include_errors_in_summary: bool = Field(default=False, description="Append error details to summary files")


class OutputConfig(BaseModel):
    """Output settings."""
    directory: str = Field(default="outputs", description="Output directory for summaries")
    filename_pattern: str = Field(
        default="PR-{number}-{repo_name}-summary.md",
        description="Filename pattern for summary files",
    )
    overwrite_existing: bool = Field(default=True, description="Overwrite existing summary files")
    include_metadata: bool = Field(default=True, description="Include metadata in summaries")


class LoggingConfig(BaseModel):
    """Logging settings."""
    level: str = Field(default="INFO", description="Log level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )
    console: bool = Field(default=True, description="Log to console")
    file: bool = Field(default=True, description="Log to file")
    file_path: str = Field(default="scraper-prs.log", description="Log file path")
    max_bytes: int = Field(default=10485760, ge=1024, description="Max log file size in bytes")
    backup_count: int = Field(default=5, ge=0, description="Number of backup log files")


class RateLimitEntry(BaseModel):
    """Rate limit for a single service."""
    requests_per_hour: Optional[int] = Field(default=None, description="Max requests per hour")
    requests_per_minute: Optional[int] = Field(default=None, description="Max requests per minute")
    min_delay_between_requests: float = Field(default=0.1, ge=0.0, description="Min delay between requests (s)")


class RateLimitsConfig(BaseModel):
    """Rate limiting settings."""
    github: RateLimitEntry = Field(default_factory=lambda: RateLimitEntry(requests_per_hour=4500, min_delay_between_requests=0.1))
    jira: RateLimitEntry = Field(default_factory=lambda: RateLimitEntry(requests_per_minute=100, min_delay_between_requests=0.6))
    confluence: RateLimitEntry = Field(default_factory=lambda: RateLimitEntry(requests_per_minute=100, min_delay_between_requests=0.6))


class AgentConfigResponse(BaseModel):
    """Full agent config matching agent_config.yaml structure."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    templates: TemplatesConfig = Field(default_factory=TemplatesConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    error_handling: ErrorHandlingConfig = Field(default_factory=ErrorHandlingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    rate_limits: RateLimitsConfig = Field(default_factory=RateLimitsConfig)
    file_categories: Optional[Dict[str, List[str]]] = Field(
        default=None, description="File categorisation glob patterns"
    )


class AgentConfigUpdateRequest(BaseModel):
    """
    Partial update for agent config.  Only supplied sections are updated
    (deep-merged into the existing YAML).
    """
    llm: Optional[LLMConfig] = None
    processing: Optional[ProcessingConfig] = None
    templates: Optional[TemplatesConfig] = None
    extraction: Optional[ExtractionConfig] = None
    retry: Optional[RetryConfig] = None
    error_handling: Optional[ErrorHandlingConfig] = None
    output: Optional[OutputConfig] = None
    logging: Optional[LoggingConfig] = None
    rate_limits: Optional[RateLimitsConfig] = None
    file_categories: Optional[Dict[str, List[str]]] = None


class ConfigPriorityInfo(BaseModel):
    """Describes which env-var overrides are active."""
    key: str
    env_var: str
    env_value: Optional[str] = None
    yaml_value: Optional[Any] = None
    active_source: str = Field(description="'yaml', 'env', or 'cli'")


class AgentConfigWithMeta(BaseModel):
    """Config response that includes override metadata."""
    config: AgentConfigResponse
    overrides: List[ConfigPriorityInfo] = Field(
        default_factory=list,
        description="Active env-var overrides (highest priority wins)",
    )


# ── Confluence Test Models ──────────────────────────────────────────────────


class ConfluenceTestRequest(BaseModel):
    """Request to test the Confluence search + relevance scoring pipeline."""
    pr_title: str = Field(
        ...,
        description="PR title (used for free-text search and keyword extraction)",
        min_length=1,
    )
    jira_ids: List[str] = Field(
        default_factory=list,
        description="Jira ticket IDs (e.g. ['PORTAL-1687'])",
    )
    jira_ticket_titles: List[str] = Field(
        default_factory=list,
        description="Jira ticket summaries/titles (used for free-text search and relevance scoring)",
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Max Confluence pages to return after filtering",
    )
    relevance_threshold: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score to include a page (0.0-1.0)",
    )


class ConfluenceTestPageResult(BaseModel):
    """A single Confluence page result with relevance metadata."""
    page_id: str
    title: str
    url: str
    excerpt: Optional[str] = None
    space_name: Optional[str] = None
    relevance_score: float = Field(description="Computed relevance score (0.0-1.0)")
    kept: bool = Field(description="Whether this page passed the relevance threshold")


class ConfluenceTestResponse(BaseModel):
    """Response from the Confluence test endpoint."""
    cql_query: str = Field(description="The generated CQL query")
    keywords: List[str] = Field(description="Keywords extracted from PR title")
    free_text_phrases: List[str] = Field(description="Free-text phrases used in search")
    total_candidates: int = Field(description="Total pages returned by Confluence")
    kept_count: int = Field(description="Pages that passed relevance filter")
    relevance_threshold: float
    pages: List[ConfluenceTestPageResult] = Field(
        description="All candidate pages sorted by relevance (kept pages first)",
    )
    duration_ms: float


# ── Pipeline Step Execution ─────────────────────────────────────────────────


class PipelineCreateRequest(BaseModel):
    """Request to create an interactive pipeline session."""
    repo_url: str = Field(
        ...,
        description="GitHub repository URL",
        examples=["https://github.com/nasuni/portal"],
    )
    pr_number: int = Field(..., description="PR number to analyze", gt=0)


class PipelineExecuteRequest(BaseModel):
    """Request to execute pipeline nodes."""
    target_node: Optional[str] = Field(
        None,
        description="Execute up to and including this node. null or '__all__' = all remaining.",
    )


class PipelineNodeResult(BaseModel):
    """Result of executing a single pipeline node."""
    node: str
    status: str = Field(description="completed | error")
    duration_ms: float = 0.0
    output: Optional[Dict[str, Any]] = Field(
        None, description="State diff produced by this node (changed keys only)"
    )
    error: Optional[str] = None


class PipelineSessionResponse(BaseModel):
    """Full status of a pipeline session."""
    session_id: str
    repo_url: str
    pr_number: int
    created_at: str
    is_initialized: bool
    is_running: bool
    executed_nodes: List[str]
    total_nodes: int
    execution_order: List[str]
    node_outputs: Dict[str, Any] = Field(default_factory=dict)
    node_durations: Dict[str, float] = Field(default_factory=dict)
    node_errors: Dict[str, str] = Field(default_factory=dict)
