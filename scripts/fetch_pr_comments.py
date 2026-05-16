#!/usr/bin/env python3
"""
Fetch PR details and review comments via the GitHub MCP server.

Usage:
    python scripts/fetch_pr_comments.py <owner> <repo> <pr_number>

Example:
    python scripts/fetch_pr_comments.py nasuni portal 1554
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.mcp.client import MCPClientManager
from src.mcp.config import get_config_loader


async def fetch(owner: str, repo: str, pr_number: int, output_dir: str) -> None:
    config_loader = get_config_loader("config")
    mcp_config = config_loader.load_mcp_config()

    # Only connect the GitHub server
    github_only = {
        "mcpServers": {"github": mcp_config["mcpServers"]["github"]}
    }
    manager = MCPClientManager(github_only)
    await manager.connect_all()

    try:
        # 1. get_pull_request
        print(f"Fetching PR #{pr_number} from {owner}/{repo}...")
        pr_result = await manager.call_tool(
            "github",
            "get_pull_request",
            {"owner": owner, "repo": repo, "pull_number": pr_number},
        )
        pr_data = _extract_json(pr_result)

        # 2. get_pull_request_comments (review comments) — paginate to get all
        print("Fetching review comments...")
        all_comments = []
        page = 1
        per_page = 100
        while True:
            comments_result = await manager.call_tool(
                "github",
                "get_pull_request_comments",
                {
                    "owner": owner,
                    "repo": repo,
                    "pull_number": pr_number,
                    "per_page": per_page,
                    "page": page,
                },
            )
            page_data = _extract_json(comments_result)
            if not page_data or not isinstance(page_data, list):
                break
            all_comments.extend(page_data)
            print(f"  page {page}: {len(page_data)} comments")
            if len(page_data) < per_page:
                break
            page += 1
        comments_data = all_comments

        # Write outputs
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        pr_path = out / f"PR-{pr_number}-details.json"
        comments_path = out / f"PR-{pr_number}-review-comments.json"

        pr_path.write_text(json.dumps(pr_data, indent=2, default=str))
        print(f"  -> {pr_path}")

        comments_path.write_text(json.dumps(comments_data, indent=2, default=str))
        comment_count = len(comments_data) if isinstance(comments_data, list) else 0
        print(f"  -> {comments_path}  ({comment_count} comments)")

    finally:
        await manager.disconnect_all()


def _extract_json(result):
    """Pull JSON from an MCP CallToolResult."""
    if not result:
        return None
    if hasattr(result, "content") and result.content:
        first = result.content[0]
        if hasattr(first, "text"):
            return json.loads(first.text)
        if hasattr(first, "data"):
            return first.data
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Fetch PR details and review comments via GitHub MCP"
    )
    parser.add_argument("owner", help="Repository owner (e.g. nasuni)")
    parser.add_argument("repo", help="Repository name (e.g. portal)")
    parser.add_argument("pr_number", type=int, help="Pull request number")
    parser.add_argument(
        "-o", "--output-dir",
        default="outputs",
        help="Directory to write JSON files (default: outputs)",
    )
    args = parser.parse_args()
    asyncio.run(fetch(args.owner, args.repo, args.pr_number, args.output_dir))


if __name__ == "__main__":
    main()
