"""
Job manager for async PR summary processing.

Manages background jobs, tracks their state, and provides
log streaming capabilities.
"""
import asyncio
import logging
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, Optional

from src.agent.graph import run_pr_summary_agent
from src.api.models import (
    JobStatus,
    JobStatusResponse,
    PRSelectionMode,
    PRSummaryResult,
)
from src.mcp.client import MCPClientManager
from src.mcp.config import get_config_loader
from src.utils.logger import setup_logging

logger = logging.getLogger(__name__)

# Maximum log lines kept per job
MAX_LOG_LINES = 500


class JobLogHandler(logging.Handler):
    """Custom log handler that captures logs for a specific job."""

    def __init__(self, job_id: str, log_buffer: Deque[str]):
        super().__init__()
        self.job_id = job_id
        self.log_buffer = log_buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.log_buffer.append(msg)
        except Exception:
            self.handleError(record)


class Job:
    """Represents a single PR summary generation job."""

    def __init__(
        self,
        job_id: str,
        repo_url: str,
        mode: PRSelectionMode,
        pr_number: Optional[int] = None,
        label: Optional[str] = None,
        max_prs: int = 5,
        output_dir: Optional[str] = None,
        verbose: bool = False,
    ):
        self.job_id = job_id
        self.repo_url = repo_url
        self.mode = mode
        self.pr_number = pr_number
        self.label = label
        self.max_prs = max_prs
        self.output_dir = output_dir
        self.verbose = verbose

        # State tracking
        self.status: JobStatus = JobStatus.PENDING
        self.progress: float = 0.0
        self.current_step: Optional[str] = None
        self.created_at: datetime = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.results: list[PRSummaryResult] = []
        self.errors: list[Dict[str, Any]] = []
        self.warnings: list[str] = []
        self.total_prs: int = 0
        self.processed_prs: int = 0
        self.logs: Deque[str] = deque(maxlen=MAX_LOG_LINES)
        self.task: Optional[asyncio.Task] = None

    def to_status_response(self) -> JobStatusResponse:
        """Convert job to API status response."""
        return JobStatusResponse(
            job_id=self.job_id,
            status=self.status,
            progress=self.progress,
            current_step=self.current_step,
            repo_url=self.repo_url,
            mode=self.mode,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            results=self.results,
            errors=self.errors,
            warnings=self.warnings,
            total_prs=self.total_prs,
            processed_prs=self.processed_prs,
            logs=list(self.logs),
        )


class JobManager:
    """Manages background PR summary generation jobs."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}

    def create_job(
        self,
        repo_url: str,
        mode: PRSelectionMode,
        pr_number: Optional[int] = None,
        label: Optional[str] = None,
        max_prs: int = 5,
        output_dir: Optional[str] = None,
        verbose: bool = False,
    ) -> Job:
        """Create a new processing job."""
        job_id = str(uuid.uuid4())[:8]
        job = Job(
            job_id=job_id,
            repo_url=repo_url,
            mode=mode,
            pr_number=pr_number,
            label=label,
            max_prs=max_prs,
            output_dir=output_dir,
            verbose=verbose,
        )
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        """List all jobs, most recent first."""
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.RUNNING, JobStatus.PENDING):
            if job.task and not job.task.done():
                job.task.cancel()
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            return True
        return False

    async def run_job(self, job: Job) -> None:
        """Execute a PR summary job in the background."""
        log_handler = JobLogHandler(job.job_id, job.logs)
        log_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

        try:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            job.current_step = "Loading configuration"
            job.progress = 5.0

            # Load config
            config_loader = get_config_loader("config")
            mcp_config = config_loader.load_mcp_config()
            agent_config = config_loader.load_agent_config()
            config_loader.validate_mcp_config(mcp_config)
            config_loader.validate_agent_config(agent_config)

            # Setup logging level (this clears root logger handlers)
            log_level = "DEBUG" if job.verbose else agent_config.get("logging", {}).get(
                "level", "INFO"
            )
            logging_config = agent_config.get("logging", {})
            setup_logging(
                level=log_level,
                log_file=logging_config.get("file_path", "scraper-prs.log"),
                max_bytes=logging_config.get("max_bytes", 10485760),
                backup_count=logging_config.get("backup_count", 5),
                enable_console=logging_config.get("console", True),
                enable_file=logging_config.get("file", True),
                log_format=logging_config.get(
                    "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                ),
            )

            # Add job log handler AFTER setup_logging (which clears handlers)
            root_logger = logging.getLogger()
            root_logger.addHandler(log_handler)

            # Apply CLI overrides
            if job.output_dir:
                agent_config["output"]["directory"] = job.output_dir
            if job.max_prs:
                agent_config["processing"]["max_prs"] = job.max_prs
            if job.pr_number:
                agent_config["processing"]["pr_number"] = job.pr_number
                agent_config["processing"]["max_prs"] = 1
            if job.label:
                agent_config["processing"]["label"] = job.label

            import os
            agent_config["jira_url"] = os.getenv("JIRA_URL", "https://nasuni.atlassian.net")
            agent_config["atlassian_cloud_id"] = os.getenv("ATLASSIAN_CLOUD_ID", "")

            # Connect MCP servers (create fresh manager per job to avoid lifecycle issues)
            job.current_step = "Connecting to MCP servers"
            job.progress = 10.0
            mcp_manager = MCPClientManager(mcp_config)
            await mcp_manager.connect_all()

            connected = list(mcp_manager.clients.keys())
            logger.info(f"[Job {job.job_id}] Connected to MCP servers: {connected}")

            # Run agent with progress tracking
            job.current_step = "Processing PRs"
            job.progress = 15.0

            # Progress callback to update job state as the graph executes
            async def on_state_change(node_name: str, state: dict) -> None:
                """Update job progress based on graph node completions."""
                pr_list = state.get("pr_list", [])
                current_index = state.get("current_pr_index", 0)
                total_prs = len(pr_list) if pr_list else 1

                # Map node names to progress steps
                node_steps = {
                    "parse_repo_url": "Parsing repository URL",
                    "fetch_prs": "Fetching PRs from GitHub",
                    "select_next_pr": f"Selecting PR ({current_index}/{total_prs})",
                    "extract_references": f"Extracting references (PR {current_index}/{total_prs})",
                    "fetch_jira_context": "Fetching Jira context",
                    "enrich_references_from_jira": "Enriching references from Jira tickets",
                    "fetch_figma_context": "Fetching Figma context",
                    "fetch_confluence_context": "Fetching Confluence context",
                    "analyze_files": "Analyzing files",
                    "generate_summary": f"Generating summary (PR {current_index}/{total_prs})",
                    "identify_coding_standards": "Identifying coding standards",
                    "identify_architectural_patterns": "Identifying architectural patterns",
                    "generate_review_summary": "Generating review summary",
                    "identify_breaking_changes": "Identifying breaking changes",
                    "save_summary": f"Saving summary (PR {current_index}/{total_prs})",
                }

                if node_name in node_steps:
                    job.current_step = node_steps[node_name]

                # Calculate progress: 15% (start) to 90% (before finalize)
                # Distribute based on PR index and node within the PR pipeline
                node_order = [
                    "parse_repo_url", "fetch_prs", "select_next_pr",
                    "extract_references", "fetch_jira_context", "enrich_references_from_jira", "fetch_figma_context",
                    "fetch_confluence_context", "analyze_files", "generate_summary",
                    "identify_coding_standards", "identify_architectural_patterns",
                    "generate_review_summary", "identify_breaking_changes", "save_summary",
                ]
                # Per-PR nodes (after initial setup)
                per_pr_nodes = node_order[3:]  # extract_references onwards
                setup_nodes = node_order[:3]

                if node_name in setup_nodes:
                    idx = setup_nodes.index(node_name)
                    job.progress = 15.0 + (idx / len(setup_nodes)) * 10.0
                elif node_name in per_pr_nodes:
                    node_idx = per_pr_nodes.index(node_name)
                    pr_base = 25.0
                    pr_range = 65.0  # 25% to 90%
                    pr_progress = (current_index / total_prs) * pr_range
                    node_progress = (node_idx / len(per_pr_nodes)) * (pr_range / total_prs)
                    job.progress = min(pr_base + pr_progress + node_progress, 90.0)

                job.total_prs = total_prs
                job.processed_prs = len(state.get("summaries", []))

            final_state = await run_pr_summary_agent(
                job.repo_url, mcp_manager, agent_config,
                on_state_change=on_state_change,
            )

            # Cleanup MCP
            await mcp_manager.disconnect_all()

            # Extract results
            summaries = final_state.get("summaries", [])
            output_files = final_state.get("output_files", [])
            errors = final_state.get("errors", [])
            warnings = final_state.get("warnings", [])

            job.total_prs = len(final_state.get("pr_list", []))
            job.processed_prs = len(summaries)
            job.errors = errors
            job.warnings = warnings

            for i, summary in enumerate(summaries):
                result = PRSummaryResult(
                    pr_number=summary.pr_number if hasattr(summary, "pr_number") else 0,
                    title=None,
                    summary_file=output_files[i] if i < len(output_files) else None,
                    status="completed",
                )
                job.results.append(result)

            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.current_step = "Done"
            job.completed_at = datetime.now()

            logger.info(
                f"[Job {job.job_id}] Completed: {job.processed_prs}/{job.total_prs} PRs processed"
            )

        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            logger.warning(f"[Job {job.job_id}] Cancelled")

        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now()
            job.errors.append({"message": str(e), "context": "job_runner"})
            logger.error(f"[Job {job.job_id}] Failed: {e}", exc_info=True)

        finally:
            logging.getLogger().removeHandler(log_handler)


# Singleton job manager
_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    """Get or create the singleton JobManager."""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
