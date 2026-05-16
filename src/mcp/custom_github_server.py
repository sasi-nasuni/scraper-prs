"""
Custom MCP server exposing GitHub tools that the official MCP server
doesn't support well (e.g. paginated PR comments).

Run standalone:
    python -m src.mcp.custom_github_server

Or register in config/mcp_servers.json to auto-start alongside other servers.
"""

import os
from enum import Enum
from typing import Optional

import httpx
from dotenv import load_dotenv
from mcp.server import FastMCP

load_dotenv()

# ── Server instance ─────────────────────────────────────────────────────────

mcp = FastMCP(
    name="custom-github",
    instructions=(
        "Custom GitHub tools that extend the official GitHub MCP server "
        "with proper pagination and extra endpoints."
    ),
)

GITHUB_API = "https://api.github.com"


def _get_token() -> str:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN or GITHUB_PERSONAL_ACCESS_TOKEN environment variable is required"
        )
    return token


async def _github_paginate(
    url: str,
    token: str,
    params: dict,
    page: int | None,
    per_page: int,
) -> tuple[list[dict], int]:
    """
    Fetch from a GitHub REST endpoint.

    If *page* is given, fetch that single page.
    Otherwise auto-paginate through ALL pages.
    Returns ``(items, pages_fetched)``.
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        if page is not None:
            params.update({"page": page, "per_page": per_page})
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json(), 1

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


# ── Tools ───────────────────────────────────────────────────────────────────

import json


@mcp.tool(
    name="fetch_pr_comments",
    description=(
        "Fetch pull-request comments from GitHub with proper pagination support. "
        "Returns review comments (inline/diff-level), issue comments (general "
        "conversation), or both.  Supports fetching a single page or auto-paginating "
        "to retrieve ALL comments."
    ),
)
async def fetch_pr_comments(
    owner: str,
    repo: str,
    pull_number: int,
    comment_type: str = "all",
    page: Optional[int] = None,
    per_page: int = 100,
) -> str:
    """
    Fetch PR comments from GitHub REST API.

    Args:
        owner: Repository owner (user or org).
        repo: Repository name.
        pull_number: Pull request number.
        comment_type: Type of comments to fetch — "review" (inline code
            comments on diffs), "issue" (general conversation comments),
            or "all" (both).  Defaults to "all".
        page: Specific page number to fetch (1-based).  When omitted the
            tool auto-paginates and returns **all** comments.
        per_page: Number of results per page (1-100, default 100).
    """
    if comment_type not in ("review", "issue", "all"):
        return json.dumps(
            {"error": f"Invalid comment_type '{comment_type}'. Use 'review', 'issue', or 'all'."}
        )

    per_page = max(1, min(per_page, 100))
    token = _get_token()
    base = f"{GITHUB_API}/repos/{owner}/{repo}"

    all_comments: list[dict] = []
    total_pages = 0

    try:
        if comment_type in ("review", "all"):
            url = f"{base}/pulls/{pull_number}/comments"
            items, pages = await _github_paginate(url, token, {}, page, per_page)
            for c in items:
                c["_comment_type"] = "review"
            all_comments.extend(items)
            total_pages = max(total_pages, pages)

        if comment_type in ("issue", "all"):
            url = f"{base}/issues/{pull_number}/comments"
            items, pages = await _github_paginate(url, token, {}, page, per_page)
            for c in items:
                c["_comment_type"] = "issue"
            all_comments.extend(items)
            total_pages = max(total_pages, pages)

    except httpx.HTTPStatusError as e:
        return json.dumps(
            {
                "error": f"GitHub API returned {e.response.status_code}",
                "detail": e.response.text,
            }
        )

    result = {
        "owner": owner,
        "repo": repo,
        "pull_number": pull_number,
        "comment_type": comment_type,
        "total_count": len(all_comments),
        "page": page,
        "per_page": per_page,
        "total_pages_fetched": total_pages if page is None else None,
        "comments": all_comments,
    }
    return json.dumps(result, indent=2, default=str)


@mcp.tool(
    name="fetch_pr_reviews",
    description=(
        "Fetch the review verdicts (APPROVED, CHANGES_REQUESTED, COMMENTED, etc.) "
        "for a pull request.  This is different from review *comments* — these are "
        "the top-level review submissions with their state and body."
    ),
)
async def fetch_pr_reviews(
    owner: str,
    repo: str,
    pull_number: int,
    page: Optional[int] = None,
    per_page: int = 100,
) -> str:
    """
    Fetch PR review submissions from GitHub REST API.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pull_number: Pull request number.
        page: Specific page (omit for all pages).
        per_page: Results per page (1-100, default 100).
    """
    per_page = max(1, min(per_page, 100))
    token = _get_token()
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pull_number}/reviews"

    try:
        items, pages = await _github_paginate(url, token, {}, page, per_page)
    except httpx.HTTPStatusError as e:
        return json.dumps(
            {
                "error": f"GitHub API returned {e.response.status_code}",
                "detail": e.response.text,
            }
        )

    result = {
        "owner": owner,
        "repo": repo,
        "pull_number": pull_number,
        "total_count": len(items),
        "page": page,
        "per_page": per_page,
        "total_pages_fetched": pages if page is None else None,
        "reviews": items,
    }
    return json.dumps(result, indent=2, default=str)


@mcp.tool(
    name="fetch_pr_files",
    description=(
        "List files changed in a pull request with additions, deletions, "
        "and patch data.  Supports pagination for large PRs."
    ),
)
async def fetch_pr_files(
    owner: str,
    repo: str,
    pull_number: int,
    page: Optional[int] = None,
    per_page: int = 100,
) -> str:
    """
    Fetch the list of files changed in a PR.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pull_number: Pull request number.
        page: Specific page (omit for all pages).
        per_page: Results per page (1-100, default 100).
    """
    per_page = max(1, min(per_page, 100))
    token = _get_token()
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pull_number}/files"

    try:
        items, pages = await _github_paginate(url, token, {}, page, per_page)
    except httpx.HTTPStatusError as e:
        return json.dumps(
            {
                "error": f"GitHub API returned {e.response.status_code}",
                "detail": e.response.text,
            }
        )

    result = {
        "owner": owner,
        "repo": repo,
        "pull_number": pull_number,
        "total_count": len(items),
        "page": page,
        "per_page": per_page,
        "total_pages_fetched": pages if page is None else None,
        "files": items,
    }
    return json.dumps(result, indent=2, default=str)


@mcp.tool(
    name="fetch_pr_commits",
    description=(
        "Fetch commits associated with a pull request.  The official GitHub "
        "MCP server only exposes repo-level commits, not PR-specific ones.  "
        "This tool calls the PR commits endpoint with full pagination."
    ),
)
async def fetch_pr_commits(
    owner: str,
    repo: str,
    pull_number: int,
    page: Optional[int] = None,
    per_page: int = 100,
) -> str:
    """
    Fetch commits for a specific pull request.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pull_number: Pull request number.
        page: Specific page (omit for all pages).
        per_page: Results per page (1-100, default 100).
    """
    per_page = max(1, min(per_page, 100))
    token = _get_token()
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pull_number}/commits"

    try:
        items, pages = await _github_paginate(url, token, {}, page, per_page)
    except httpx.HTTPStatusError as e:
        return json.dumps(
            {
                "error": f"GitHub API returned {e.response.status_code}",
                "detail": e.response.text,
            }
        )

    result = {
        "owner": owner,
        "repo": repo,
        "pull_number": pull_number,
        "total_count": len(items),
        "page": page,
        "per_page": per_page,
        "total_pages_fetched": pages if page is None else None,
        "commits": items,
    }
    return json.dumps(result, indent=2, default=str)


# ── Entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
