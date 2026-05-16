"""
Tool wrappers for MCP server calls.
These functions wrap MCP tool calls with error handling and retry logic.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from src.agent.state import (
    ConfluencePage,
    FigmaFile,
    JiraTicket,
    PRCommit,
    PRData,
    PRFile,
    PRReview,
    PRReviewComment,
)
from src.mcp.client import MCPClientManager
from src.utils.rate_limiter import RateLimiter, create_rate_limiter_from_config

logger = logging.getLogger(__name__)


def create_retry_decorator(config: Dict[str, Any]):
    """Create a retry decorator from config settings.
    
    Args:
        config: Full config dict containing retry settings
    
    Returns:
        Configured retry decorator
    """
    retry_config = config.get("retry", {})
    max_attempts = retry_config.get("max_attempts", 3)
    initial_delay = retry_config.get("initial_delay", 2)
    max_delay = retry_config.get("max_delay", 30)
    exponential_base = retry_config.get("exponential_base", 2)
    
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=exponential_base, min=initial_delay, max=max_delay)
    )


def get_retry_params(config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract retry parameters from config.
    
    Args:
        config: Full config dict
    
    Returns:
        Dict with retry parameters
    """
    retry_config = config.get("retry", {})
    return {
        "max_attempts": retry_config.get("max_attempts", 3),
        "initial_delay": retry_config.get("initial_delay", 2),
        "max_delay": retry_config.get("max_delay", 30),
        "exponential_base": retry_config.get("exponential_base", 2),
    }


class GitHubTools:
    """GitHub MCP tool wrappers."""

    def __init__(self, mcp_manager: MCPClientManager, config: Dict[str, Any] = None):
        self.mcp_manager = mcp_manager
        self.server_name = "github"
        # Custom GitHub MCP server for paginated endpoints (files, reviews, comments)
        self.custom_server_name = "custom-github"
        self.config = config or {}
        retry_params = get_retry_params(self.config)
        self._retry_decorator = retry(
            stop=stop_after_attempt(retry_params["max_attempts"]),
            wait=wait_exponential(
                multiplier=retry_params["exponential_base"],
                min=retry_params["initial_delay"],
                max=retry_params["max_delay"]
            )
        )
        self.rate_limiter = create_rate_limiter_from_config(self.config, "github")
    
    async def get_merged_prs(
        self,
        owner: str,
        repo: str,
        limit: int = 5
    ) -> List[PRData]:
        """
        Get recently merged PRs from a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            limit: Maximum number of PRs to fetch
        
        Returns:
            List of PRData objects
        """
        @self._retry_decorator
        async def _do_fetch():
            try:
                logger.info(f"Fetching {limit} merged PRs from {owner}/{repo}")
                
                # Rate limit before API call
                if self.rate_limiter:
                    await self.rate_limiter.acquire()
                
                # Call GitHub MCP tool - use list_pull_requests, not search
                result = await self.mcp_manager.call_tool(
                    self.server_name,
                    "list_pull_requests",
                    {
                        "owner": owner,
                        "repo": repo,
                        "state": "closed",
                        "sort": "updated",
                        "direction": "desc",
                        "per_page": limit,
                    }
                )
                
                if not result:
                    logger.warning(f"No PRs found for {owner}/{repo}")
                    return []
                
                # Parse MCP result - result.content is a list of content blocks
                # Extract text/data from the first content block
                data = None
                if hasattr(result, 'content') and result.content:
                    import json
                    first_content = result.content[0]
                    if hasattr(first_content, 'text'):
                        data = json.loads(first_content.text)
                    elif hasattr(first_content, 'data'):
                        data = first_content.data
                
                if not data:
                    logger.warning(f"No PR data found for {owner}/{repo}")
                    return []
                
                # Get PR numbers from the list
                pr_list = data if isinstance(data, list) else data.get("items", [])
                pr_numbers = [pr_data["number"] for pr_data in pr_list[:limit]]
                
                logger.info(f"Found {len(pr_numbers)} PRs, fetching full details for each...")
                
                # Fetch full details for each PR (includes files, reviews, review_comments)
                prs = []
                for pr_number in pr_numbers:
                    pr = await self.get_pr_details(owner, repo, pr_number)
                    if pr:
                        prs.append(pr)
                    else:
                        logger.warning(f"Failed to fetch details for PR #{pr_number}")
                
                logger.info(f"Successfully fetched full details for {len(prs)} PRs")
                return prs
            
            except Exception as e:
                logger.error(f"Error fetching PRs: {e}")
                return []
        
        return await _do_fetch()
    
    async def get_prs_by_label(
        self,
        owner: str,
        repo: str,
        label: str,
        limit: int = 5
    ) -> List[PRData]:
        """
        Search for merged PRs with a specific label.

        Args:
            owner: Repository owner
            repo: Repository name
            label: GitHub label to filter by
            limit: Maximum number of PRs to fetch

        Returns:
            List of PRData objects
        """
        @self._retry_decorator
        async def _do_fetch():
            try:
                logger.info(f"Searching for merged PRs with label '{label}' in {owner}/{repo}")

                if self.rate_limiter:
                    await self.rate_limiter.acquire()

                # Use search_issues (covers both issues and PRs) with GitHub search syntax
                # Add is:pr and is:merged to scope results, plus repo filter
                query = f'repo:{owner}/{repo} is:pr is:merged label:"{label}"'
                result = await self.mcp_manager.call_tool(
                    self.server_name,
                    "search_issues",
                    {
                        "q": query,
                        "sort": "updated",
                        "order": "desc",
                        "per_page": limit,
                    }
                )

                if not result:
                    logger.warning(f"No PRs found with label '{label}' in {owner}/{repo}")
                    return []

                # Parse MCP result
                data = None
                if hasattr(result, 'content') and result.content:
                    import json
                    first_content = result.content[0]
                    if hasattr(first_content, 'text'):
                        data = json.loads(first_content.text)
                    elif hasattr(first_content, 'data'):
                        data = first_content.data

                if not data:
                    logger.warning(f"No PR data found for label '{label}' in {owner}/{repo}")
                    return []

                # Search results come under "items" key
                pr_list = data.get("items", []) if isinstance(data, dict) else data
                pr_numbers = [pr_data["number"] for pr_data in pr_list[:limit]]

                logger.info(f"Found {len(pr_numbers)} PRs with label '{label}', fetching full details...")

                # Fetch full details for each PR
                prs = []
                for pr_number in pr_numbers:
                    pr = await self.get_pr_details(owner, repo, pr_number)
                    if pr:
                        prs.append(pr)
                    else:
                        logger.warning(f"Failed to fetch details for PR #{pr_number}")

                logger.info(f"Successfully fetched full details for {len(prs)} PRs with label '{label}'")
                return prs

            except Exception as e:
                logger.error(f"Error searching PRs by label '{label}': {e}")
                return []

        return await _do_fetch()

    async def get_pr_details(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> Optional[PRData]:
        """
        Get detailed information about a specific PR.

        Uses the official GitHub MCP server for PR metadata (single object)
        and the custom-github MCP server for paginated endpoints (files,
        reviews, comments) to ensure ALL items are fetched.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
        
        Returns:
            PRData object or None
        """
        @self._retry_decorator
        async def _do_fetch():
            try:
                logger.info(f"Fetching PR details for {owner}/{repo}#{pr_number}")
                
                # ── 1. PR metadata (single object – official server is fine) ──
                if self.rate_limiter:
                    await self.rate_limiter.acquire()
                
                pr_result = await self.mcp_manager.call_tool(
                    self.server_name,
                    "get_pull_request",
                    {
                        "owner": owner,
                        "repo": repo,
                        "pull_number": pr_number,
                    }
                )
                
                if not pr_result:
                    return None

                # Determine which server to use for paginated calls.
                # Fall back to the official server if custom-github is not connected.
                custom_available = self.mcp_manager.is_connected(self.custom_server_name)
                paginated_server = self.custom_server_name if custom_available else self.server_name

                if custom_available:
                    logger.info(
                        f"Using custom-github MCP server for full pagination "
                        f"on {owner}/{repo}#{pr_number}"
                    )
                else:
                    logger.warning(
                        f"custom-github MCP server not connected – falling back "
                        f"to official github server (results may be capped at 30)"
                    )

                # ── 2. PR files (paginated) ──────────────────────────────────
                if self.rate_limiter:
                    await self.rate_limiter.acquire()

                if custom_available:
                    files_result = await self.mcp_manager.call_tool(
                        paginated_server,
                        "fetch_pr_files",
                        {
                            "owner": owner,
                            "repo": repo,
                            "pull_number": pr_number,
                        }
                    )
                else:
                    files_result = await self.mcp_manager.call_tool(
                        paginated_server,
                        "get_pull_request_files",
                        {
                            "owner": owner,
                            "repo": repo,
                            "pull_number": pr_number,
                        }
                    )
                
                # ── 3. PR commits (paginated) ─────────────────────────────
                if self.rate_limiter:
                    await self.rate_limiter.acquire()

                if custom_available:
                    commits_result = await self.mcp_manager.call_tool(
                        paginated_server,
                        "fetch_pr_commits",
                        {
                            "owner": owner,
                            "repo": repo,
                            "pull_number": pr_number,
                        }
                    )
                else:
                    # Official GitHub MCP doesn't have a PR-specific commits tool;
                    # list_commits returns ALL repo commits. Skip when unavailable.
                    commits_result = None
                
                # ── 4. PR reviews (paginated) ────────────────────────────────
                if self.rate_limiter:
                    await self.rate_limiter.acquire()

                if custom_available:
                    reviews_result = await self.mcp_manager.call_tool(
                        paginated_server,
                        "fetch_pr_reviews",
                        {
                            "owner": owner,
                            "repo": repo,
                            "pull_number": pr_number,
                        }
                    )
                else:
                    reviews_result = await self.mcp_manager.call_tool(
                        paginated_server,
                        "get_pull_request_reviews",
                        {
                            "owner": owner,
                            "repo": repo,
                            "pull_number": pr_number,
                        }
                    )
                
                # ── 5. PR review comments (paginated) ────────────────────────
                if self.rate_limiter:
                    await self.rate_limiter.acquire()

                if custom_available:
                    review_comments_result = await self.mcp_manager.call_tool(
                        paginated_server,
                        "fetch_pr_comments",
                        {
                            "owner": owner,
                            "repo": repo,
                            "pull_number": pr_number,
                            "comment_type": "review",
                        }
                    )
                else:
                    review_comments_result = await self.mcp_manager.call_tool(
                        paginated_server,
                        "get_pull_request_comments",
                        {
                            "owner": owner,
                            "repo": repo,
                            "pull_number": pr_number,
                        }
                    )
                
                # ── Parse and combine data ───────────────────────────────────
                pr_data = self._extract_json_from_result(pr_result)
                pr = self._parse_pr_data(pr_data, owner, repo)
                
                if pr and files_result:
                    files_data = self._extract_json_from_result(files_result)
                    if files_data:
                        # Custom server wraps items under a "files" key
                        if isinstance(files_data, dict) and "files" in files_data:
                            pr.files = self._parse_files(files_data["files"])
                            logger.info(
                                f"Fetched {len(pr.files)} files (all pages) "
                                f"for PR #{pr_number}"
                            )
                        else:
                            pr.files = self._parse_files(files_data)
                
                if pr and commits_result:
                    commits_data = self._extract_json_from_result(commits_result)
                    if commits_data:
                        # Custom server wraps items under a "commits" key
                        if isinstance(commits_data, dict) and "commits" in commits_data:
                            pr.commits = self._parse_commits(commits_data["commits"])
                            logger.info(
                                f"Fetched {len(pr.commits)} commits (all pages) "
                                f"for PR #{pr_number}"
                            )
                        else:
                            pr.commits = self._parse_commits(commits_data)
                elif pr:
                    pr.commits = []
                
                if pr and reviews_result:
                    reviews_data = self._extract_json_from_result(reviews_result)
                    if reviews_data:
                        # Custom server wraps items under a "reviews" key
                        if isinstance(reviews_data, dict) and "reviews" in reviews_data:
                            pr.reviews = self._parse_reviews(reviews_data["reviews"])
                            logger.info(
                                f"Fetched {len(pr.reviews)} reviews (all pages) "
                                f"for PR #{pr_number}"
                            )
                        else:
                            pr.reviews = self._parse_reviews(reviews_data)
                
                if pr and review_comments_result:
                    review_comments_data = self._extract_json_from_result(review_comments_result)
                    if review_comments_data:
                        # Custom server wraps items under a "comments" key
                        if isinstance(review_comments_data, dict) and "comments" in review_comments_data:
                            pr.review_comments = self._parse_review_comments(
                                review_comments_data["comments"]
                            )
                        else:
                            pr.review_comments = self._parse_review_comments(review_comments_data)
                        logger.info(f"Fetched {len(pr.review_comments)} review comments for PR #{pr_number}")
                    else:
                        logger.info("No review comments data found")
                
                return pr
            
            except Exception as e:
                logger.error(f"Error fetching PR details: {e}")
                return None
        
        return await _do_fetch()
    
    def _extract_json_from_result(self, result: Any) -> Any:
        """Extract JSON data from MCP result."""
        if not result:
            return None
        
        # Parse MCP result - result.content is a list of content blocks
        # Extract text/data from the first content block
        if hasattr(result, 'content') and result.content:
            import json
            first_content = result.content[0]
            if hasattr(first_content, 'text'):
                try:
                    return json.loads(first_content.text)
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON from MCP result: {e}")
                    return None
            elif hasattr(first_content, 'data'):
                return first_content.data
        
        return None
    
    def _parse_pr_data(
        self,
        pr_data: Dict[str, Any],
        owner: str,
        repo: str
    ) -> Optional[PRData]:
        """Parse PR data from GitHub API response."""
        try:
            # Handle merged_at which might be None for non-merged PRs
            merged_at_str = pr_data.get("merged_at")
            if merged_at_str:
                merged_at = datetime.fromisoformat(merged_at_str.replace("Z", "+00:00"))
            else:
                # Use current time as fallback for non-merged PRs
                merged_at = datetime.now()
            
            return PRData(
                number=pr_data["number"],
                title=pr_data["title"],
                body=pr_data.get("body", ""),
                author=pr_data["user"]["login"],
                merged_at=merged_at,
                source_branch=pr_data["head"]["ref"],
                target_branch=pr_data["base"]["ref"],
                url=pr_data["html_url"],
            )
        except Exception as e:
            logger.error(f"Error parsing PR data: {e}")
            return None
    
    def _parse_files(self, files_data: List[Dict[str, Any]]) -> List[PRFile]:
        """Parse file data from GitHub API response."""
        files = []
        for file_data in files_data:
            try:
                files.append(PRFile(
                    path=file_data["filename"],
                    additions=file_data["additions"],
                    deletions=file_data["deletions"],
                    status=file_data["status"],
                    patch=file_data.get("patch"),  # unified diff text (None for binary/large files)
                ))
            except Exception as e:
                logger.error(f"Error parsing file data: {e}")
        return files
    
    def _parse_commits(self, commits_data: List[Dict[str, Any]]) -> List[PRCommit]:
        """Parse commit data from GitHub API response."""
        commits = []
        for commit_data in commits_data:
            try:
                commits.append(PRCommit(
                    sha=commit_data["sha"],
                    message=commit_data["commit"]["message"],
                    author=commit_data["commit"]["author"]["name"],
                    date=datetime.fromisoformat(
                        commit_data["commit"]["author"]["date"].replace("Z", "+00:00")
                    ),
                ))
            except Exception as e:
                logger.error(f"Error parsing commit data: {e}")
        return commits
    
    def _parse_reviews(self, reviews_data: List[Dict[str, Any]]) -> List[PRReview]:
        """Parse review data from GitHub API response."""
        reviews = []
        for review_data in reviews_data:
            try:
                reviews.append(PRReview(
                    reviewer=review_data["user"]["login"],
                    state=review_data["state"],
                    body=review_data.get("body"),
                    submitted_at=datetime.fromisoformat(
                        review_data["submitted_at"].replace("Z", "+00:00")
                    ),
                ))
            except Exception as e:
                logger.error(f"Error parsing review data: {e}")
        return reviews
    
    def _parse_review_comments(self, comments_data: List[Dict[str, Any]]) -> List[PRReviewComment]:
        """Parse review comment data from GitHub API response."""
        comments = []
        for comment_data in comments_data:
            try:
                comments.append(PRReviewComment(
                    id=comment_data.get("id"),
                    in_reply_to_id=comment_data.get("in_reply_to_id"),
                    author=comment_data["user"]["login"],
                    body=comment_data["body"],
                    path=comment_data.get("path"),
                    line=comment_data.get("line"),
                    start_line=comment_data.get("start_line"),
                    diff_hunk=comment_data.get("diff_hunk"),
                    subject_type=comment_data.get("subject_type"),
                    pull_request_review_id=comment_data.get("pull_request_review_id"),
                    created_at=datetime.fromisoformat(
                        comment_data["created_at"].replace("Z", "+00:00")
                    ),
                ))
            except Exception as e:
                logger.error(f"Error parsing review comment data: {e}")
        return comments


class JiraTools:
    """Jira MCP tool wrappers."""

    def __init__(self, mcp_manager: MCPClientManager, jira_base_url: str, cloud_id: str, config: Dict[str, Any] = None):
        self.mcp_manager = mcp_manager
        self.server_name = "atlassian"
        self.jira_base_url = jira_base_url
        self.cloud_id = cloud_id
        self.config = config or {}
        retry_params = get_retry_params(self.config)
        self._retry_decorator = retry(
            stop=stop_after_attempt(retry_params["max_attempts"]),
            wait=wait_exponential(
                multiplier=retry_params["exponential_base"],
                min=retry_params["initial_delay"],
                max=retry_params["max_delay"]
            )
        )
        self.rate_limiter = create_rate_limiter_from_config(self.config, "jira")
    
    async def get_issue(self, issue_key: str) -> Optional[JiraTicket]:
        """
        Get Jira issue details.
        
        Args:
            issue_key: Jira issue key (e.g., PROJ-123)
        
        Returns:
            JiraTicket object or None
        """
        @self._retry_decorator
        async def _do_fetch():
            try:
                logger.info(f"Fetching Jira issue: {issue_key}")
                
                # Rate limit before API call
                if self.rate_limiter:
                    await self.rate_limiter.acquire()
                
                result = await self.mcp_manager.call_tool(
                    self.server_name,
                    "getJiraIssue",
                    {
                        "cloudId": self.cloud_id,
                        "issueIdOrKey": issue_key,
                        "responseContentFormat": "markdown",
                    }
                )
                
                if not result:
                    logger.warning(f"Jira issue not found: {issue_key}")
                    return None
                
                # Debug: Log the result structure
                logger.debug(f"Jira result type: {type(result)}")
                logger.debug(f"Jira result attributes: {dir(result)}")
                if hasattr(result, 'content'):
                    logger.debug(f"Jira result content length: {len(result.content) if result.content else 0}")
                    if result.content:
                        logger.debug(f"First content type: {type(result.content[0])}")
                        logger.debug(f"First content: {result.content[0]}")
                
                # Parse MCP result - extract data from CallToolResult
                import json
                data = None
                if hasattr(result, 'content') and result.content:
                    first_content = result.content[0]
                    if hasattr(first_content, 'text'):
                        try:
                            data = json.loads(first_content.text)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse Jira response for {issue_key}")
                            return None
                    elif hasattr(first_content, 'data'):
                        data = first_content.data
                
                if not data:
                    logger.warning(f"No data in Jira response for {issue_key}")
                    return None
                
                # Parse Jira issue data
                ticket = self._parse_jira_issue(data)
                return ticket
            
            except Exception as e:
                logger.error(f"Error fetching Jira issue {issue_key}: {e}")
                return None
        
        return await _do_fetch()
    
    def _parse_jira_issue(self, issue_data: Dict[str, Any]) -> Optional[JiraTicket]:
        """Parse Jira issue data.

        With ``responseContentFormat: "markdown"`` the description field is
        returned as a plain markdown string.  Without it the field is ADF
        JSON (a dict).  We handle both: dicts are serialised to a compact
        JSON string so downstream code always sees a string.
        """
        try:
            fields = issue_data.get("fields", {})

            # ── description ──────────────────────────────────────────
            raw_desc = fields.get("description", "")
            if isinstance(raw_desc, dict):
                # ADF JSON fallback — serialise so the LLM at least sees
                # something rather than a Python repr of a dict.
                import json as _json
                description = _json.dumps(raw_desc, ensure_ascii=False)
            else:
                description = raw_desc or ""

            # ── acceptance criteria (configurable custom field) ──────
            ac_field = (
                self.config
                .get("extraction", {})
                .get("jira", {})
                .get("acceptance_criteria_field")
            )
            acceptance_criteria: str | None = None
            if ac_field:
                raw_ac = fields.get(ac_field)
                if isinstance(raw_ac, dict):
                    import json as _json
                    acceptance_criteria = _json.dumps(raw_ac, ensure_ascii=False)
                elif raw_ac:
                    acceptance_criteria = str(raw_ac)

            return JiraTicket(
                key=issue_data["key"],
                title=fields.get("summary", ""),
                description=description,
                status=fields.get("status", {}).get("name", "Unknown"),
                priority=fields.get("priority", {}).get("name", "Unknown"),
                ticket_type=fields.get("issuetype", {}).get("name", "Unknown"),
                epic=fields.get("epic", {}).get("key") if "epic" in fields else None,
                acceptance_criteria=acceptance_criteria,
                url=f"{self.jira_base_url}/browse/{issue_data['key']}",
                assignee=fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
                reporter=fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
                created=datetime.fromisoformat(
                    fields["created"].replace("Z", "+00:00")
                ) if "created" in fields else None,
                updated=datetime.fromisoformat(
                    fields["updated"].replace("Z", "+00:00")
                ) if "updated" in fields else None,
            )
        except Exception as e:
            logger.error(f"Error parsing Jira issue: {e}")
            return None


class ConfluenceTools:
    """Confluence MCP tool wrappers."""

    def __init__(self, mcp_manager: MCPClientManager, cloud_id: str, config: Dict[str, Any] = None):
        self.mcp_manager = mcp_manager
        self.server_name = "atlassian"
        self.cloud_id = cloud_id
        self.config = config or {}
        retry_params = get_retry_params(self.config)
        self._retry_decorator = retry(
            stop=stop_after_attempt(retry_params["max_attempts"]),
            wait=wait_exponential(
                multiplier=retry_params["exponential_base"],
                min=retry_params["initial_delay"],
                max=retry_params["max_delay"]
            )
        )
        self.rate_limiter = create_rate_limiter_from_config(self.config, "confluence")
    
    async def search_pages(
        self,
        query: str,
        max_results: int = 3
    ) -> List[ConfluencePage]:
        """
        Search for Confluence pages.
        
        Args:
            query: Search query (CQL)
            max_results: Maximum number of results
        
        Returns:
            List of ConfluencePage objects
        """
        @self._retry_decorator
        async def _do_fetch():
            try:
                logger.info(f"Searching Confluence with query: {query}")
                
                # Rate limit before API call
                if self.rate_limiter:
                    await self.rate_limiter.acquire()
                
                result = await self.mcp_manager.call_tool(
                    self.server_name,
                    "searchConfluenceUsingCql",
                    {
                        "cloudId": self.cloud_id,
                        "cql": query,
                        "limit": max_results,
                    }
                )
                
                if not result:
                    return []
                
                # Parse MCP result - extract data from CallToolResult
                import json
                data = None
                if hasattr(result, 'content') and result.content:
                    first_content = result.content[0]
                    if hasattr(first_content, 'text'):
                        try:
                            if first_content.text.strip():  # Check for empty string
                                data = json.loads(first_content.text)
                            else:
                                logger.warning(f"Empty response from Confluence search")
                                return []
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse Confluence response: {e}")
                            return []
                    elif hasattr(first_content, 'data'):
                        data = first_content.data
                
                if not data:
                    logger.debug("No data in Confluence response")
                    return []
                
                pages = []
                folder_ids = []
                results = data if isinstance(data, list) else data.get("results", [])
                for page_data in results:
                    content = page_data.get("content", {})
                    content_type = content.get("type", "page")
                    if content_type == "folder":
                        folder_ids.append(content.get("id"))
                        continue
                    page = self._parse_confluence_page(page_data)
                    if page:
                        pages.append(page)
                
                # Search for child pages inside any matched folders
                if folder_ids:
                    logger.info(
                        f"Found {len(folder_ids)} folder(s), "
                        f"searching for child pages inside them"
                    )
                    for folder_id in folder_ids:
                        child_pages = await self._get_folder_children(
                            folder_id, max_results
                        )
                        pages.extend(child_pages)

                logger.info(f"Found {len(pages)} Confluence pages")
                return pages
            
            except Exception as e:
                logger.error(f"Error searching Confluence: {e}")
                return []
        
        return await _do_fetch()

    async def _get_folder_children(
        self, folder_id: str, max_results: int = 5
    ) -> List["ConfluencePage"]:
        """Fetch child pages that live inside a Confluence folder.

        Confluence folders show up in CQL search results but have no body.
        The actual content pages are children of the folder.
        """
        try:
            logger.info(
                f"Fetching child pages for Confluence folder {folder_id}"
            )
            if self.rate_limiter:
                await self.rate_limiter.acquire()

            result = await self.mcp_manager.call_tool(
                self.server_name,
                "getConfluencePageDescendants",
                {
                    "cloudId": self.cloud_id,
                    "pageId": folder_id,
                },
            )

            if not result:
                return []

            import json
            children: List["ConfluencePage"] = []
            if hasattr(result, "content") and result.content:
                text = getattr(result.content[0], "text", None)
                if text:
                    try:
                        data = json.loads(text)
                    except (json.JSONDecodeError, AttributeError):
                        data = {}

                    results_list = (
                        data if isinstance(data, list)
                        else data.get("results", [])
                    )
                    for child in results_list[:max_results]:
                        # Descendants API returns page objects directly
                        # (not wrapped in search-result envelopes)
                        child_type = child.get("type", "page")
                        if child_type not in ("page", "blogpost"):
                            continue
                        try:
                            space = child.get("space", {})
                            space_key = space.get("key", "")
                            page = ConfluencePage(
                                page_id=child["id"],
                                title=child.get("title", ""),
                                url=(
                                    f"/wiki/spaces/{space_key}"
                                    f"/pages/{child['id']}"
                                ),
                                excerpt=child.get("excerpt", ""),
                                space_name=space.get("name"),
                            )
                            children.append(page)
                        except (KeyError, TypeError) as exc:
                            logger.warning(
                                f"Skipping folder child: {exc}"
                            )
            logger.info(
                f"Found {len(children)} child page(s) in folder {folder_id}"
            )
            return children
        except Exception as e:
            logger.error(
                f"Error fetching children for folder {folder_id}: {e}"
            )
            return []

    async def get_page(self, page_id: str) -> Optional[str]:
        """Fetch the full body of a Confluence page as markdown.

        Args:
            page_id: Confluence page ID.

        Returns:
            Markdown-formatted page body, or None on failure.
        """

        @self._retry_decorator
        async def _do_fetch():
            try:
                logger.info(f"Fetching Confluence page body: {page_id}")

                if self.rate_limiter:
                    await self.rate_limiter.acquire()

                result = await self.mcp_manager.call_tool(
                    self.server_name,
                    "getConfluencePage",
                    {
                        "cloudId": self.cloud_id,
                        "pageId": page_id,
                        "contentFormat": "markdown",
                    },
                )

                if not result:
                    return None

                # The MCP response may be plain-text markdown or JSON
                import json
                if hasattr(result, "content") and result.content:
                    first = result.content[0]
                    text = getattr(first, "text", None)
                    if not text:
                        return None

                    # Try parsing as JSON first (some responses wrap body)
                    try:
                        data = json.loads(text)

                        # Detect error responses from the MCP server /
                        # Confluence API and treat them as failures.
                        if data.get("error") is True or "errors" in data:
                            error_msg = data.get("message", data.get("errors", ""))
                            logger.warning(
                                f"Confluence page {page_id}: API error – {error_msg}"
                            )
                            return None

                        # Look for body in known locations
                        body = (
                            data.get("body", {}).get("atlas_doc_format", {}).get("value")
                            or data.get("body", {}).get("storage", {}).get("value")
                            or data.get("body", {}).get("view", {}).get("value")
                            or data.get("body")
                        )
                        if isinstance(body, str):
                            return body
                        # Fallback: return the raw text if body isn't found
                        return text
                    except (json.JSONDecodeError, AttributeError):
                        # Response is already plain markdown
                        return text

                return None
            except Exception as e:
                logger.error(f"Error fetching Confluence page {page_id}: {e}")
                return None

        return await _do_fetch()

    def _parse_confluence_page(
        self,
        page_data: Dict[str, Any]
    ) -> Optional[ConfluencePage]:
        """Parse Confluence page data.

        Skips non-page content types (folders, comments, attachments, etc.)
        since their body cannot be fetched via the page API.
        """
        try:
            content = page_data.get("content", {})
            content_type = content.get("type", "page")

            # Only process pages and blog posts — folders, comments, etc.
            # don't have fetchable bodies and cause 404s.
            if content_type not in ("page", "blogpost"):
                logger.info(
                    f"Skipping Confluence '{content.get('title', '?')}' "
                    f"(type={content_type}, id={content.get('id', '?')})"
                )
                return None

            return ConfluencePage(
                page_id=content["id"],
                title=content["title"],
                url=page_data["url"],
                excerpt=page_data.get("excerpt", ""),
                space_name=content.get("space", {}).get("name"),
            )
        except Exception as e:
            logger.error(f"Error parsing Confluence page: {e}")
            return None


class FigmaTools:
    """Figma MCP tool wrappers."""

    def __init__(self, mcp_manager: MCPClientManager, config: Dict[str, Any] = None):
        self.mcp_manager = mcp_manager
        self.server_name = "figma"
        self.config = config or {}
        retry_params = get_retry_params(self.config)
        self._retry_decorator = retry(
            stop=stop_after_attempt(retry_params["max_attempts"]),
            wait=wait_exponential(
                multiplier=retry_params["exponential_base"],
                min=retry_params["initial_delay"],
                max=retry_params["max_delay"]
            )
        )
        # Note: No rate limiter config for Figma in agent_config.yaml
        self.rate_limiter = None
    
    async def get_file(self, file_key: str) -> Optional[FigmaFile]:
        """
        Get Figma file metadata.
        
        Args:
            file_key: Figma file key
        
        Returns:
            FigmaFile object or None
        """
        @self._retry_decorator
        async def _do_fetch():
            try:
                logger.info(f"Fetching Figma file: {file_key}")
                
                # Rate limit before API call (if configured)
                if self.rate_limiter:
                    await self.rate_limiter.acquire()
                
                result = await self.mcp_manager.call_tool(
                    self.server_name,
                    "get_metadata",
                    {
                        "fileKey": file_key,
                    }
                )
                
                if not result:
                    return None
                
                figma_file = self._parse_figma_file(result, file_key)
                return figma_file
            
            except Exception as e:
                logger.error(f"Error fetching Figma file {file_key}: {e}")
                return None
        
        return await _do_fetch()
    
    def _parse_figma_file(
        self,
        file_data: Dict[str, Any],
        file_key: str
    ) -> Optional[FigmaFile]:
        """Parse Figma file data."""
        try:
            return FigmaFile(
                file_key=file_key,
                name=file_data.get("name", ""),
                url=f"https://www.figma.com/file/{file_key}",
                thumbnail_url=file_data.get("thumbnailUrl"),
                last_modified=datetime.fromisoformat(
                    file_data["lastModified"]
                ) if "lastModified" in file_data else None,
                version=file_data.get("version"),
            )
        except Exception as e:
            logger.error(f"Error parsing Figma file: {e}")
            return None
