"""
FastAPI application routes for PR Summary Agent.
"""
import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import yaml

from src.api.jobs import get_job_manager
from src.api.models import (
    AgentConfigResponse,
    AgentConfigUpdateRequest,
    AgentConfigWithMeta,
    ConfluenceTestRequest,
    ConfluenceTestResponse,
    ConfluenceTestPageResult,
    ConfigPriorityInfo,
    ErrorResponse,
    GenerateRequest,
    GitHubPRCommentsRequest,
    GitHubPRCommentsResponse,
    GitHubPRCommitsRequest,
    GitHubPRCommitsResponse,
    HealthResponse,
    JobCreatedResponse,
    JobListResponse,
    JobStatus,
    JobStatusResponse,
    MCPServerStatus,
    MCPServersResponse,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolInfo,
    MCPToolsResponse,
)
from src.mcp.client import MCPClient, MCPClientManager
from src.mcp.config import ConfigLoader

logger = logging.getLogger(__name__)

# ── App Setup ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="PR Summary Agent API",
    description="REST API for generating comprehensive PR summaries using LangGraph and MCP servers",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Next.js / fallback
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health & Info ───────────────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        timestamp=datetime.now(),
    )


# ── Job Endpoints ───────────────────────────────────────────────────────────


@app.post(
    "/api/jobs",
    response_model=JobCreatedResponse,
    status_code=201,
    tags=["Jobs"],
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def create_job(request: GenerateRequest):
    """
    Submit a new PR summary generation job.

    The job runs asynchronously in the background. Use the returned `job_id`
    to poll status via `GET /api/jobs/{job_id}`.
    """
    manager = get_job_manager()

    job = manager.create_job(
        repo_url=request.repo_url,
        mode=request.mode,
        pr_number=request.pr_number,
        label=request.label,
        pr_urls=request.pr_urls,
        max_prs=request.max_prs,
        output_dir=request.output_dir,
        verbose=request.verbose,
    )

    # Launch the job in the background
    job.task = asyncio.create_task(manager.run_job(job))

    logger.info(f"Created job {job.job_id} for {request.repo_url} (mode={request.mode.value})")

    return JobCreatedResponse(
        job_id=job.job_id,
        status=job.status,
        message="Job created successfully",
        created_at=job.created_at,
    )


@app.get(
    "/api/jobs",
    response_model=JobListResponse,
    tags=["Jobs"],
)
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = 20,
    offset: int = 0,
):
    """List all jobs, optionally filtered by status."""
    manager = get_job_manager()
    all_jobs = manager.list_jobs()

    if status:
        all_jobs = [j for j in all_jobs if j.status == status]

    total = len(all_jobs)
    page = all_jobs[offset : offset + limit]

    return JobListResponse(
        jobs=[j.to_status_response() for j in page],
        total=total,
    )


@app.get(
    "/api/jobs/{job_id}",
    response_model=JobStatusResponse,
    tags=["Jobs"],
    responses={404: {"model": ErrorResponse}},
)
async def get_job_status(job_id: str):
    """Get the status and results of a specific job."""
    manager = get_job_manager()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return job.to_status_response()


@app.post(
    "/api/jobs/{job_id}/cancel",
    response_model=JobStatusResponse,
    tags=["Jobs"],
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def cancel_job(job_id: str):
    """Cancel a running or pending job."""
    manager = get_job_manager()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    success = manager.cancel_job(job_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Job '{job_id}' cannot be cancelled (status: {job.status.value})",
        )

    return job.to_status_response()


# ── Output File Download ────────────────────────────────────────────────────


@app.get(
    "/api/jobs/{job_id}/files/{filename}",
    tags=["Jobs"],
    responses={404: {"model": ErrorResponse}},
)
async def download_summary_file(job_id: str, filename: str):
    """Download a generated summary markdown file."""
    manager = get_job_manager()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    # Find the file in results
    output_dir = job.output_dir or "outputs"
    file_path = Path(output_dir) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="text/markdown",
    )


# ── WebSocket for Live Logs ─────────────────────────────────────────────────


@app.websocket("/api/ws/jobs/{job_id}/logs")
async def websocket_job_logs(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for streaming job logs in real-time.

    Connect to this endpoint after submitting a job to see live output.
    The socket sends text messages with log lines and closes when the job completes.
    """
    await websocket.accept()

    manager = get_job_manager()
    job = manager.get_job(job_id)

    if not job:
        await websocket.send_json({"error": f"Job '{job_id}' not found"})
        await websocket.close(code=4004)
        return

    last_sent_index = 0

    try:
        while True:
            # Send any new log lines
            current_logs = list(job.logs)
            if len(current_logs) > last_sent_index:
                new_lines = current_logs[last_sent_index:]
                for line in new_lines:
                    try:
                        await websocket.send_text(line)
                    except Exception:
                        return
                last_sent_index = len(current_logs)

            # Send status update
            try:
                await websocket.send_json(
                    {
                        "type": "status",
                        "status": job.status.value,
                        "progress": job.progress,
                        "current_step": job.current_step,
                        "processed_prs": job.processed_prs,
                        "total_prs": job.total_prs,
                    }
                )
            except Exception:
                return

            # If job is done, send final state and close cleanly
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                try:
                    await websocket.send_json(
                        {
                            "type": "complete",
                            "status": job.status.value,
                            "results": [r.model_dump() for r in job.results],
                            "errors": job.errors,
                        }
                    )
                except Exception:
                    pass
                # Send a proper close frame so the proxy doesn't get EPIPE
                try:
                    await websocket.close(code=1000)
                except Exception:
                    pass
                return

            await asyncio.sleep(1)  # Poll interval

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


# ── MCP Tool Testing ────────────────────────────────────────────────────────

# Lazy-initialized MCP manager for tool testing
_mcp_manager: Optional[MCPClientManager] = None
_mcp_config_cache: Optional[dict] = None


def _load_mcp_config() -> dict:
    """Load MCP config (cached)."""
    global _mcp_config_cache
    if _mcp_config_cache is None:
        loader = ConfigLoader()
        _mcp_config_cache = loader.load_mcp_config()
    return _mcp_config_cache


async def _get_mcp_manager() -> MCPClientManager:
    """Get or create the shared MCP client manager."""
    global _mcp_manager
    if _mcp_manager is None or not _mcp_manager._connected:
        config = _load_mcp_config()
        _mcp_manager = MCPClientManager(config)
        await _mcp_manager.connect_all()
    return _mcp_manager


@app.on_event("shutdown")
async def _shutdown_mcp():
    global _mcp_manager
    if _mcp_manager:
        await _mcp_manager.disconnect_all()
        _mcp_manager = None


@app.get(
    "/api/mcp/servers",
    response_model=MCPServersResponse,
    tags=["MCP Tools"],
)
async def list_mcp_servers():
    """List all configured MCP servers and their connection status."""
    config = _load_mcp_config()
    servers_config = config.get("mcpServers", {})

    try:
        manager = await _get_mcp_manager()
    except Exception as e:
        logger.error(f"Failed to connect to MCP servers: {e}")
        # Return servers as disconnected
        servers = [
            MCPServerStatus(
                name=name,
                connected=False,
                tool_count=0,
                description=cfg.get("description"),
            )
            for name, cfg in servers_config.items()
        ]
        return MCPServersResponse(servers=servers)

    servers = []
    for name, cfg in servers_config.items():
        client = manager.get_client(name)
        servers.append(
            MCPServerStatus(
                name=name,
                connected=client is not None,
                tool_count=len(client.get_available_tools()) if client else 0,
                description=cfg.get("description"),
            )
        )

    return MCPServersResponse(servers=servers)


@app.get(
    "/api/mcp/servers/{server_name}/tools",
    response_model=MCPToolsResponse,
    tags=["MCP Tools"],
    responses={404: {"model": ErrorResponse}},
)
async def list_server_tools(server_name: str, q: Optional[str] = None):
    """
    List all available tools for a specific MCP server.

    Optionally filter by name/description with the `q` query param.
    """
    try:
        manager = await _get_mcp_manager()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MCP servers unavailable: {e}")

    client = manager.get_client(server_name)
    if not client:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server '{server_name}' not found or not connected",
        )

    tools = []
    for tool in client._available_tools:
        schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
        tools.append(
            MCPToolInfo(
                name=tool.name,
                description=getattr(tool, "description", None),
                input_schema=schema,
            )
        )

    # Optional search filter
    if q:
        q_lower = q.lower()
        tools = [
            t
            for t in tools
            if q_lower in t.name.lower()
            or (t.description and q_lower in t.description.lower())
        ]

    return MCPToolsResponse(server=server_name, tools=tools, total=len(tools))


@app.post(
    "/api/mcp/tools/call",
    response_model=MCPToolCallResponse,
    tags=["MCP Tools"],
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def call_mcp_tool(request: MCPToolCallRequest):
    """
    Invoke an MCP tool and return its result.

    Use `GET /api/mcp/servers/{server}/tools` to discover available tools
    and their expected input schemas.
    """
    try:
        manager = await _get_mcp_manager()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MCP servers unavailable: {e}")

    client = manager.get_client(request.server)
    if not client:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server '{request.server}' not found or not connected",
        )

    # Validate the tool exists
    available = client.get_available_tools()
    if request.tool not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{request.tool}' not found on server '{request.server}'. "
            f"Available: {available[:10]}{'...' if len(available) > 10 else ''}",
        )

    start = time.time()
    try:
        result = await client.call_tool(request.tool, request.arguments)
        duration_ms = round((time.time() - start) * 1000, 2)

        # Extract text content from MCP result
        result_data = None
        if result and hasattr(result, "content"):
            parts = []
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                else:
                    parts.append(str(block))
            result_data = "\n".join(parts) if parts else str(result)
        elif result is not None:
            result_data = str(result)

        return MCPToolCallResponse(
            server=request.server,
            tool=request.tool,
            success=True,
            result=result_data,
            duration_ms=duration_ms,
        )

    except Exception as e:
        duration_ms = round((time.time() - start) * 1000, 2)
        logger.error(f"Tool call failed: {request.server}/{request.tool}: {e}")
        return MCPToolCallResponse(
            server=request.server,
            tool=request.tool,
            success=False,
            error=str(e),
            duration_ms=duration_ms,
        )


# ── GitHub Direct API ───────────────────────────────────────────────────────

GITHUB_API = "https://api.github.com"


def _get_github_token() -> str:
    """Read GITHUB_TOKEN from environment."""
    from dotenv import load_dotenv

    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(
            status_code=500,
            detail="GITHUB_TOKEN environment variable not set",
        )
    return token


async def _fetch_github_pages(
    url: str,
    token: str,
    params: dict,
    page: Optional[int],
    per_page: int,
) -> tuple[list[dict], int]:
    """
    Fetch from a GitHub REST endpoint.

    If `page` is given, fetch that single page.
    Otherwise auto-paginate to collect ALL results.
    Returns (items, pages_fetched).
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        if page is not None:
            # Single page
            params.update({"page": page, "per_page": per_page})
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json(), 1

        # Auto-paginate: fetch all pages
        all_items: list[dict] = []
        current_page = 1
        while True:
            params.update({"page": current_page, "per_page": per_page})
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            if not data or not isinstance(data, list):
                break
            all_items.extend(data)
            if len(data) < per_page:
                break
            current_page += 1
        return all_items, current_page


@app.post(
    "/api/github/pr-comments",
    response_model=GitHubPRCommentsResponse,
    tags=["GitHub Direct"],
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def fetch_pr_comments(request: GitHubPRCommentsRequest):
    """
    Fetch PR comments directly from GitHub REST API with pagination.

    Unlike the MCP tool which silently ignores pagination params, this
    endpoint supports:
    - **page**: specific page number (omit to auto-fetch ALL pages)
    - **per_page**: results per page (1-100, default 100)
    - **comment_type**: `review` (diff-level), `issue` (conversation), or `all`
    """
    token = _get_github_token()
    base = f"{GITHUB_API}/repos/{request.owner}/{request.repo}"
    start = time.time()

    try:
        all_comments: list[dict] = []
        total_pages = 0

        # Review comments (inline code comments)
        if request.comment_type in ("review", "all"):
            url = f"{base}/pulls/{request.pull_number}/comments"
            items, pages = await _fetch_github_pages(
                url, token, {}, request.page, request.per_page
            )
            for c in items:
                c["_comment_type"] = "review"
            all_comments.extend(items)
            total_pages = max(total_pages, pages)

        # Issue comments (general PR conversation)
        if request.comment_type in ("issue", "all"):
            url = f"{base}/issues/{request.pull_number}/comments"
            items, pages = await _fetch_github_pages(
                url, token, {}, request.page, request.per_page
            )
            for c in items:
                c["_comment_type"] = "issue"
            all_comments.extend(items)
            total_pages = max(total_pages, pages)

        duration_ms = round((time.time() - start) * 1000, 2)

        return GitHubPRCommentsResponse(
            owner=request.owner,
            repo=request.repo,
            pull_number=request.pull_number,
            comment_type=request.comment_type,
            comments=all_comments,
            total_count=len(all_comments),
            page=request.page,
            per_page=request.per_page,
            total_pages_fetched=total_pages if request.page is None else None,
            duration_ms=duration_ms,
        )

    except httpx.HTTPStatusError as e:
        duration_ms = round((time.time() - start) * 1000, 2)
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"GitHub API error: {e.response.text}",
        )
    except Exception as e:
        logger.error(f"Failed to fetch PR comments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/github/pr-commits",
    response_model=GitHubPRCommitsResponse,
    tags=["GitHub Direct"],
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def fetch_pr_commits(request: GitHubPRCommitsRequest):
    """
    Fetch PR commits directly from GitHub REST API with pagination.

    Supports:
    - **page**: specific page number (omit to auto-fetch ALL pages)
    - **per_page**: results per page (1-100, default 100)
    """
    token = _get_github_token()
    url = f"{GITHUB_API}/repos/{request.owner}/{request.repo}/pulls/{request.pull_number}/commits"
    start = time.time()

    try:
        items, pages = await _fetch_github_pages(
            url, token, {}, request.page, request.per_page
        )
        duration_ms = round((time.time() - start) * 1000, 2)

        return GitHubPRCommitsResponse(
            owner=request.owner,
            repo=request.repo,
            pull_number=request.pull_number,
            commits=items,
            total_count=len(items),
            page=request.page,
            per_page=request.per_page,
            total_pages_fetched=pages if request.page is None else None,
            duration_ms=duration_ms,
        )

    except httpx.HTTPStatusError as e:
        duration_ms = round((time.time() - start) * 1000, 2)
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"GitHub API error: {e.response.text}",
        )
    except Exception as e:
        logger.error(f"Failed to fetch PR commits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Confluence Search Test ──────────────────────────────────────────────────


@app.post(
    "/api/confluence/test-search",
    response_model=ConfluenceTestResponse,
    tags=["Confluence Test"],
    responses={500: {"model": ErrorResponse}},
)
async def test_confluence_search(request: ConfluenceTestRequest):
    """
    Test the Confluence search + relevance scoring pipeline.

    Provide a PR title, optional Jira IDs and ticket titles, and see:
    - The generated CQL query
    - Raw search results from Confluence
    - Relevance score for each result
    - Which results pass the threshold
    """
    from src.extractors.confluence import (
        format_confluence_search_query,
        generate_search_keywords,
        score_confluence_relevance,
    )
    from src.agent.state import ConfluencePage

    start = time.time()

    # 1. Build search inputs
    keywords = generate_search_keywords(request.pr_title)

    free_text_phrases: list[str] = [request.pr_title]
    for title in request.jira_ticket_titles:
        if title.strip():
            free_text_phrases.append(title.strip())

    query = format_confluence_search_query(
        request.jira_ids, keywords, free_text_phrases
    )

    if not query:
        duration_ms = round((time.time() - start) * 1000, 2)
        return ConfluenceTestResponse(
            cql_query="",
            keywords=keywords,
            free_text_phrases=free_text_phrases,
            total_candidates=0,
            kept_count=0,
            relevance_threshold=request.relevance_threshold,
            pages=[],
            duration_ms=duration_ms,
        )

    # 2. Search Confluence via MCP
    try:
        manager = await _get_mcp_manager()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MCP servers unavailable: {e}")

    # Load config for ConfluenceTools
    loader = ConfigLoader()
    agent_config = loader.load_agent_config()

    from src.agent.tools import ConfluenceTools

    cloud_id = os.getenv("ATLASSIAN_CLOUD_ID", agent_config.get("atlassian_cloud_id", ""))
    confluence_tools = ConfluenceTools(manager, cloud_id, agent_config)

    fetch_limit = max(request.max_results * 3, 15)
    candidates: list[ConfluencePage] = await confluence_tools.search_pages(query, fetch_limit)

    # 3. Score each candidate
    scored_pages: list[ConfluenceTestPageResult] = []
    for page in candidates:
        score = score_confluence_relevance(
            page_title=page.title,
            page_excerpt=page.excerpt,
            jira_ids=request.jira_ids,
            pr_title=request.pr_title,
            jira_ticket_titles=request.jira_ticket_titles,
            pr_keywords=keywords,
        )
        kept = score >= request.relevance_threshold
        scored_pages.append(
            ConfluenceTestPageResult(
                page_id=page.page_id,
                title=page.title,
                url=page.url,
                excerpt=page.excerpt,
                space_name=page.space_name,
                relevance_score=round(score, 4),
                kept=kept,
            )
        )

    # Sort: kept first (by score desc), then not-kept (by score desc)
    scored_pages.sort(key=lambda p: (-int(p.kept), -p.relevance_score))
    kept_count = sum(1 for p in scored_pages if p.kept)

    duration_ms = round((time.time() - start) * 1000, 2)

    return ConfluenceTestResponse(
        cql_query=query,
        keywords=keywords,
        free_text_phrases=free_text_phrases,
        total_candidates=len(candidates),
        kept_count=kept_count,
        relevance_threshold=request.relevance_threshold,
        pages=scored_pages,
        duration_ms=duration_ms,
    )


# ── Pipeline Step Execution ─────────────────────────────────────────────────

from src.api.models import (
    PipelineCreateRequest,
    PipelineExecuteRequest,
    PipelineSessionResponse,
)
from src.api.pipeline import get_pipeline_manager

import json as _json
from fastapi.responses import StreamingResponse


@app.post(
    "/api/pipeline/sessions",
    response_model=PipelineSessionResponse,
    status_code=201,
    tags=["Pipeline"],
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def create_pipeline_session(request: PipelineCreateRequest):
    """
    Create an interactive pipeline session.

    Connects MCP servers and prepares the pipeline for step-by-step execution.
    """
    mgr = get_pipeline_manager()
    session = mgr.create(request.repo_url, request.pr_number)

    try:
        await session.initialize()
    except Exception as e:
        await mgr.delete(session.session_id)
        logger.error(f"Pipeline session init failed: {e}")
        raise HTTPException(status_code=503, detail=f"Initialization failed: {e}")

    logger.info(
        f"Pipeline session {session.session_id} created for "
        f"{request.repo_url} PR#{request.pr_number}"
    )
    return PipelineSessionResponse(**session.to_dict())


@app.get(
    "/api/pipeline/sessions/{session_id}",
    response_model=PipelineSessionResponse,
    tags=["Pipeline"],
    responses={404: {"model": ErrorResponse}},
)
async def get_pipeline_session(session_id: str):
    """Get current state of a pipeline session."""
    session = get_pipeline_manager().get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return PipelineSessionResponse(**session.to_dict())


@app.delete(
    "/api/pipeline/sessions/{session_id}",
    tags=["Pipeline"],
    responses={404: {"model": ErrorResponse}},
)
async def delete_pipeline_session(session_id: str):
    """Delete a pipeline session and free resources."""
    ok = await get_pipeline_manager().delete(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@app.post(
    "/api/pipeline/sessions/{session_id}/execute",
    tags=["Pipeline"],
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def execute_pipeline_nodes(session_id: str, request: PipelineExecuteRequest):
    """
    Execute pipeline nodes up to *target_node* (inclusive).

    Returns an **SSE stream** (``text/event-stream``).  Events:

    * ``{"type": "node_start", "node": "<name>"}``
    * ``{"type": "node_complete", "node": "<name>", "output": {...}, "duration_ms": 123}``
    * ``{"type": "node_error", "node": "<name>", "error": "..."}``
    * ``{"type": "done", "executed_nodes": [...]}``
    """
    session = get_pipeline_manager().get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.is_running:
        raise HTTPException(status_code=409, detail="Session is already executing")

    try:
        to_run = session.nodes_to_execute(request.target_node)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not to_run:
        raise HTTPException(
            status_code=400,
            detail="No nodes to execute (target already completed or invalid)",
        )

    async def _stream():
        session.is_running = True
        try:
            for node_name in to_run:
                # ── start event ──
                yield f"data: {_json.dumps({'type': 'node_start', 'node': node_name})}\n\n"

                try:
                    output = await session.execute_node(node_name)
                    event = {
                        "type": "node_complete",
                        "node": node_name,
                        "output": output,
                        "duration_ms": session.node_durations.get(node_name, 0),
                    }
                    yield f"data: {_json.dumps(event, default=str)}\n\n"
                except Exception as exc:
                    event = {
                        "type": "node_error",
                        "node": node_name,
                        "error": str(exc),
                        "duration_ms": session.node_durations.get(node_name, 0),
                    }
                    yield f"data: {_json.dumps(event, default=str)}\n\n"
                    break  # stop on first error

            yield f"data: {_json.dumps({'type': 'done', 'executed_nodes': session.executed_nodes})}\n\n"
        finally:
            session.is_running = False

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx/proxy buffering
        },
    )


@app.post(
    "/api/pipeline/sessions/{session_id}/retry/{node_name}",
    tags=["Pipeline"],
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def retry_pipeline_node(session_id: str, node_name: str):
    """
    Retry a single previously-executed (or errored) node.

    Returns an **SSE stream** with the same event shapes as the execute
    endpoint: ``node_start``, ``node_complete`` / ``node_error``, ``done``.
    """
    session = get_pipeline_manager().get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.is_running:
        raise HTTPException(status_code=409, detail="Session is already executing")

    # Validate up-front so we can 400 before the stream starts
    from src.api.pipeline import EXECUTION_ORDER
    if node_name not in EXECUTION_ORDER:
        raise HTTPException(status_code=400, detail=f"Unknown node: {node_name}")

    was_executed = node_name in session.executed_nodes
    was_errored = node_name in session.node_errors
    if not was_executed and not was_errored:
        raise HTTPException(
            status_code=400,
            detail=f"Node '{node_name}' has not been executed yet",
        )

    async def _stream():
        session.is_running = True
        try:
            yield f"data: {_json.dumps({'type': 'node_start', 'node': node_name})}\n\n"

            try:
                output = await session.retry_node(node_name)
                event = {
                    "type": "node_complete",
                    "node": node_name,
                    "output": output,
                    "duration_ms": session.node_durations.get(node_name, 0),
                }
                yield f"data: {_json.dumps(event, default=str)}\n\n"
            except Exception as exc:
                event = {
                    "type": "node_error",
                    "node": node_name,
                    "error": str(exc),
                    "duration_ms": session.node_durations.get(node_name, 0),
                }
                yield f"data: {_json.dumps(event, default=str)}\n\n"

            yield f"data: {_json.dumps({'type': 'done', 'executed_nodes': session.executed_nodes})}\n\n"
        finally:
            session.is_running = False

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Agent Config ────────────────────────────────────────────────────────────

AGENT_CONFIG_PATH = Path("config/agent_config.yaml")

# Env-var mapping used to detect overrides
_ENV_OVERRIDE_MAP = [
    ("llm.provider", "LLM_PROVIDER"),
    ("llm.model", "LLM_MODEL"),
    ("llm.temperature", "LLM_TEMPERATURE"),
    ("llm.max_tokens", "LLM_MAX_TOKENS"),
    ("llm.base_url", "OPENAI_API_BASE"),
    ("processing.max_prs", "MAX_PRS_TO_PROCESS"),
    ("output.directory", "OUTPUT_DIR"),
    ("logging.level", "LOG_LEVEL"),
    ("logging.file_path", "LOG_FILE"),
]


def _resolve_yaml_key(data: dict, dotted_key: str):
    """Resolve a dotted key like 'llm.provider' from a nested dict."""
    parts = dotted_key.split(".")
    cur = data
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur


def _deep_merge(base: dict, patch: dict) -> dict:
    """Recursively merge *patch* into *base* (mutates base)."""
    for k, v in patch.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _collect_overrides(yaml_data: dict) -> list[ConfigPriorityInfo]:
    """Check which env-vars are set and report YAML vs env values."""
    overrides: list[ConfigPriorityInfo] = []
    for key, env_var in _ENV_OVERRIDE_MAP:
        env_val = os.getenv(env_var)
        yaml_val = _resolve_yaml_key(yaml_data, key)
        if env_val is not None:
            overrides.append(
                ConfigPriorityInfo(
                    key=key,
                    env_var=env_var,
                    env_value=env_val,
                    yaml_value=yaml_val,
                    active_source="env",
                )
            )
        else:
            overrides.append(
                ConfigPriorityInfo(
                    key=key,
                    env_var=env_var,
                    env_value=None,
                    yaml_value=yaml_val,
                    active_source="yaml",
                )
            )
    return overrides


@app.get(
    "/api/config",
    response_model=AgentConfigWithMeta,
    tags=["Config"],
)
async def get_agent_config():
    """
    Read the current agent_config.yaml and report which values are
    overridden by environment variables.
    """
    if not AGENT_CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="agent_config.yaml not found")

    with open(AGENT_CONFIG_PATH, "r") as f:
        raw = yaml.safe_load(f) or {}

    overrides = _collect_overrides(raw)
    config = AgentConfigResponse(**raw)

    return AgentConfigWithMeta(config=config, overrides=overrides)


@app.put(
    "/api/config",
    response_model=AgentConfigWithMeta,
    tags=["Config"],
)
async def update_agent_config(request: AgentConfigUpdateRequest):
    """
    Update agent_config.yaml.  Only the sections present in the request body
    are merged; everything else is left untouched.

    Note: environment variable overrides will still take precedence at runtime.
    """
    if not AGENT_CONFIG_PATH.exists():
        raise HTTPException(status_code=404, detail="agent_config.yaml not found")

    # Read current YAML
    with open(AGENT_CONFIG_PATH, "r") as f:
        raw = yaml.safe_load(f) or {}

    # Build patch from the non-None sections of the request
    patch = request.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No config sections provided")

    # Deep-merge patch into existing config
    _deep_merge(raw, patch)

    # Write back
    with open(AGENT_CONFIG_PATH, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    logger.info(f"Agent config updated – sections: {list(patch.keys())}")

    overrides = _collect_overrides(raw)
    config = AgentConfigResponse(**raw)
    return AgentConfigWithMeta(config=config, overrides=overrides)
