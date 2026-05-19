"""
LangGraph node implementations for PR summary agent.
"""
import hashlib
import logging
import re
from datetime import datetime
from fnmatch import fnmatch
from typing import Any, Dict

from jinja2 import Template
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from src.agent.state import (
    AgentState,
    PRSummary,
    add_error,
    add_warning,
    reset_pr_context,
    should_continue_on_error,
    should_generate_partial_summaries,
    should_include_errors_in_summary,
    should_log_errors,
)
from src.agent.tools import ConfluenceTools, FigmaTools, GitHubTools, JiraTools
from src.extractors.confluence import (
    extract_confluence_urls,
    format_confluence_search_query,
    generate_search_keywords,
    score_confluence_relevance,
)
from src.extractors.figma import extract_figma_file_key, extract_figma_urls
from src.extractors.files import categorize_files, get_total_stats, group_files_by_category
from src.extractors.jira import extract_jira_ids_from_pr
from src.extractors.review_threads import build_review_threads
from src.mcp.client import MCPClientManager
from src.utils.tokens import batch_texts_by_tokens, count_tokens
from templates.prompts import (
    ARCHITECTURAL_PATTERNS_PROMPT,
    BREAKING_CHANGES_PROMPT,
    CODING_STANDARDS_PROMPT,
    CONFLUENCE_PAGE_SUMMARY_PROMPT,
    DIFF_BATCH_SUMMARY_PROMPT,
    PR_SUMMARY_PROMPT,
    REVIEW_SUMMARY_PROMPT,
    REVIEW_THREADS_CONDENSE_PROMPT,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class PRSummaryNodes:
    """Container for all LangGraph node functions."""

    def __init__(
        self,
        mcp_manager: MCPClientManager,
        config: Dict[str, Any],
    ):
        self.mcp_manager = mcp_manager
        self.config = config
        
        # Initialize tools
        jira_url = config.get("jira_url", "")
        cloud_id = config.get("atlassian_cloud_id", "")
        self.github_tools = GitHubTools(mcp_manager, config)
        self.jira_tools = JiraTools(mcp_manager, jira_url, cloud_id, config)
        self.confluence_tools = ConfluenceTools(mcp_manager, cloud_id, config)
        self.figma_tools = FigmaTools(mcp_manager, config)
        
        # Initialize LLM
        self.llm = self._init_llm(config.get("llm", {}))
    
    def _init_llm(self, llm_config: Dict[str, Any]):
        """Initialize LLM based on configuration."""
        provider = llm_config.get("provider", "openai")
        model = llm_config.get("model", "gpt-4o")
        temperature = llm_config.get("temperature", 0.7)
        max_tokens = llm_config.get("max_tokens", 4096)
        base_url = llm_config.get("base_url")  # For GitHub Models or custom endpoints
        
        if provider == "anthropic":
            return ChatAnthropic(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            # OpenAI or OpenAI-compatible (like GitHub Models)
            kwargs = {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "max_retries": 0,  # Disable automatic retries
            }
            if base_url:
                kwargs["base_url"] = base_url
            
            return ChatOpenAI(**kwargs)
    
    async def parse_repo_url(self, state: AgentState) -> Dict[str, Any]:
        """Parse repository URL to extract owner and name."""
        logger.info("Parsing repository URL")
        
        repo_url = state["repo_url"]
        
        # Parse GitHub URL
        # Formats: https://github.com/owner/repo or git@github.com:owner/repo.git
        patterns = [
            r'github\.com[/:]([^/]+)/([^/\s]+?)(?:\.git)?$',
            r'github\.com/([^/]+)/([^/\s]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, repo_url)
            if match:
                owner = match.group(1)
                name = match.group(2).replace(".git", "")
                logger.info(f"Parsed repo: {owner}/{name}")
                return {"repo_owner": owner, "repo_name": name}
        
        # If no match, add error
        error_msg = f"Invalid GitHub repository URL: {repo_url}"
        logger.error(error_msg)
        add_error(state, error_msg, "parse_repo_url")
        
        return {}
    
    async def fetch_prs(self, state: AgentState) -> Dict[str, Any]:
        """Fetch merged PRs from the repository."""
        logger.info("Fetching merged PRs")
        
        owner = state.get("repo_owner", "")
        repo = state.get("repo_name", "")
        max_prs = self.config.get("processing", {}).get("max_prs", 5)
        pr_number = self.config.get("processing", {}).get("pr_number")
        label = self.config.get("processing", {}).get("label")
        
        if not owner or not repo:
            add_error(state, "Repository owner/name not set", "fetch_prs")
            return {"pr_list": []}
        
        prs = []
        try:
            # If specific PR number is requested, fetch only that PR
            if pr_number:
                logger.info(f"Fetching specific PR #{pr_number}")
                pr = await self.github_tools.get_pr_details(owner, repo, pr_number)
                prs = [pr] if pr else []
                if not pr:
                    add_warning(
                        state,
                        f"PR #{pr_number} not found in {owner}/{repo}"
                    )
            elif label:
                # Fetch PRs filtered by label using search
                logger.info(f"Fetching PRs with label '{label}' from {owner}/{repo}")
                prs = await self.github_tools.get_prs_by_label(owner, repo, label, max_prs)
            else:
                # Otherwise fetch list of merged PRs
                prs = await self.github_tools.get_merged_prs(owner, repo, max_prs)
            
            if not prs:
                add_warning(
                    state,
                    f"No merged PRs found in {owner}/{repo}"
                )
            else:
                logger.info(f"Fetched {len(prs)} PRs")
            
        except Exception as e:
            if should_log_errors(self.config):
                logger.error(f"Error fetching PRs: {e}")
            add_error(state, str(e), "fetch_prs", self.config)
            
            # Re-raise if not configured to continue on error
            if not should_continue_on_error(self.config):
                raise
        
        return {"pr_list": prs}
    
    async def select_next_pr(self, state: AgentState) -> Dict[str, Any]:
        """Select the next PR to process."""
        pr_list = state.get("pr_list", [])
        current_index = state.get("current_pr_index", 0)
        
        if current_index < len(pr_list):
            # Reset PR-specific context (side effect on state)
            reset_pr_context(state)
            
            # Select current PR
            current_pr = pr_list[current_index]
            logger.info(
                f"Processing PR {current_index + 1}/{len(pr_list)}: "
                f"#{current_pr.number}"
            )
            return {"current_pr": current_pr}
        else:
            # All PRs processed
            logger.info("All PRs processed")
            return {"current_pr": None, "processing_completed": datetime.now()}
    
    async def extract_references(self, state: AgentState) -> Dict[str, Any]:
        """Extract Jira IDs, Figma URLs, and Confluence URLs from PR."""
        logger.info("Extracting references from PR")
        
        current_pr = state.get("current_pr")
        if not current_pr:
            return {}
        
        # Get extraction config
        extraction_config = self.config.get("extraction", {})
        jira_config = extraction_config.get("jira", {})
        figma_config = extraction_config.get("figma", {})
        
        # Extract Jira IDs with configured pattern
        jira_pattern = jira_config.get("pattern")
        commit_messages = [commit.message for commit in current_pr.commits]
        jira_ids = extract_jira_ids_from_pr(
            current_pr.title,
            current_pr.body or "",
            commit_messages,
            pattern=jira_pattern
        )
        logger.info(f"Found Jira IDs: {jira_ids}")
        
        # Extract Figma URLs with configured patterns
        figma_patterns = figma_config.get("patterns")
        pr_text = f"{current_pr.title} {current_pr.body or ''}"
        figma_urls = extract_figma_urls(pr_text, patterns=figma_patterns)
        logger.info(f"Found Figma URLs: {len(figma_urls)}")
        
        # Extract Confluence URLs
        confluence_urls = extract_confluence_urls(pr_text)
        logger.info(f"Found Confluence URLs: {len(confluence_urls)}")
        
        return {"jira_ids": jira_ids, "figma_urls": figma_urls, "confluence_urls": confluence_urls}
    
    async def fetch_jira_context(self, state: AgentState) -> Dict[str, Any]:
        """Fetch Jira ticket details."""
        logger.info("Fetching Jira context")
        
        jira_ids = state.get("jira_ids", [])
        
        if not jira_ids:
            logger.info("No Jira IDs to fetch")
            return {"jira_tickets": []}
        
        tickets = []
        for jira_id in jira_ids:
            ticket = await self.jira_tools.get_issue(jira_id)
            if ticket:
                tickets.append(ticket)
        
        logger.info(f"Fetched {len(tickets)} Jira tickets")
        return {"jira_tickets": tickets}
    
    async def enrich_references_from_jira(self, state: AgentState) -> Dict[str, Any]:
        """Scan fetched Jira ticket descriptions for additional Figma / Confluence URLs.

        Jira tickets often contain links to Figma designs and Confluence pages
        in their description or acceptance-criteria fields.  This node runs
        *after* fetch_jira_context so the ticket data is already in state,
        and *before* fetch_figma_context / fetch_confluence_context so the
        enriched URL lists are used by those nodes.
        """
        logger.info("Enriching references from Jira ticket descriptions")

        tickets = state.get("jira_tickets", [])
        if not tickets:
            return {}

        extraction_config = self.config.get("extraction", {})
        figma_patterns = extraction_config.get("figma", {}).get("patterns")

        existing_figma: set = set(state.get("figma_urls", []))
        existing_confluence: set = set(state.get("confluence_urls", []))
        new_figma_count = 0
        new_confluence_count = 0

        for ticket in tickets:
            # Combine description + acceptance criteria into one text block
            texts = [
                getattr(ticket, "description", None) or "",
                getattr(ticket, "acceptance_criteria", None) or "",
            ]
            jira_text = " ".join(t for t in texts if t)
            if not jira_text.strip():
                continue

            # Figma URLs
            for url in extract_figma_urls(jira_text, patterns=figma_patterns):
                if url not in existing_figma:
                    existing_figma.add(url)
                    new_figma_count += 1

            # Confluence URLs
            for url in extract_confluence_urls(jira_text):
                if url not in existing_confluence:
                    existing_confluence.add(url)
                    new_confluence_count += 1

        figma_urls = list(existing_figma)
        confluence_urls = list(existing_confluence)

        if new_figma_count or new_confluence_count:
            logger.info(
                f"Enriched from Jira: +{new_figma_count} Figma URLs, "
                f"+{new_confluence_count} Confluence URLs"
            )
        else:
            logger.info("No additional Figma/Confluence URLs found in Jira tickets")

        return {"figma_urls": figma_urls, "confluence_urls": confluence_urls}

    async def fetch_figma_context(self, state: AgentState) -> Dict[str, Any]:
        """Fetch Figma file details."""
        logger.info("Fetching Figma context")
        
        figma_urls = state.get("figma_urls", [])
        
        if not figma_urls:
            logger.info("No Figma URLs to fetch")
            return {"figma_files": []}
        
        files = []
        for url in figma_urls:
            file_key = extract_figma_file_key(url)
            if file_key:
                figma_file = await self.figma_tools.get_file(file_key)
                if figma_file:
                    files.append(figma_file)
        
        logger.info(f"Fetched {len(files)} Figma files")
        return {"figma_files": files}
    
    async def fetch_confluence_context(self, state: AgentState) -> Dict[str, Any]:
        """Fetch related Confluence pages.

        Searches Confluence using three signal sources (OR-combined):
          1. Jira ticket IDs   – exact text matches
          2. Free-text phrases – PR title and Jira ticket summaries
          3. Keywords          – individual terms extracted from PR title
        """
        logger.info("Fetching Confluence context")
        
        current_pr = state.get("current_pr")
        jira_ids = state.get("jira_ids", [])
        
        if not current_pr:
            return {"confluence_pages": []}
        
        # Build free-text phrases from PR title + Jira ticket summaries
        free_text_phrases: list[str] = []
        if current_pr.title:
            free_text_phrases.append(current_pr.title)
        for ticket in state.get("jira_tickets", []):
            title = getattr(ticket, "title", None) or ""
            if title:
                free_text_phrases.append(title)

        # Generate keyword fallback from PR title
        keywords = generate_search_keywords(current_pr.title)
        query = format_confluence_search_query(jira_ids, keywords, free_text_phrases)
        
        if not query:
            logger.info("No search query generated")
            return {"confluence_pages": []}
        
        # Search Confluence — fetch extra candidates to allow relevance filtering
        max_pages = self.config.get("extraction", {}).get("confluence", {}).get("max_pages_per_pr", 3)
        fetch_limit = max(max_pages * 3, 10)  # over-fetch so we can filter
        candidates = await self.confluence_tools.search_pages(query, fetch_limit)

        if not candidates:
            logger.info("No Confluence pages found")
            return {"confluence_pages": []}

        # Score each candidate for relevance to this PR
        jira_ticket_titles = [
            getattr(t, "title", "") or ""
            for t in state.get("jira_tickets", [])
        ]
        scored = []
        for page in candidates:
            score = score_confluence_relevance(
                page_title=page.title,
                page_excerpt=page.excerpt,
                jira_ids=jira_ids,
                pr_title=current_pr.title,
                jira_ticket_titles=jira_ticket_titles,
                pr_keywords=keywords,
            )
            scored.append((score, page))

        # Keep only pages above the relevance threshold, sorted by score
        relevance_threshold = 0.15
        scored.sort(key=lambda x: x[0], reverse=True)
        relevant_pages = [page for score, page in scored if score >= relevance_threshold][:max_pages]

        logger.info(
            f"Confluence search: {len(candidates)} candidates, "
            f"{len(relevant_pages)} passed relevance filter (threshold={relevance_threshold})"
        )

        # ── Fetch full page bodies for relevant pages ────────────────
        confluence_config = self.config.get("extraction", {}).get("confluence", {})
        max_body_tokens = confluence_config.get("max_body_tokens", 3000)

        pages_with_body = []
        for page in relevant_pages:
            try:
                body = await self.confluence_tools.get_page(page.page_id)
                if body and body.strip():
                    page.body = body.strip()
                    body_tokens = count_tokens(page.body)
                    logger.info(
                        f"Fetched page '{page.title}': ~{body_tokens} tokens"
                    )

                    # Summarize large pages to keep the final prompt compact
                    if body_tokens > max_body_tokens:
                        page.content_summary = await self._summarize_confluence_page(page)
                        if page.content_summary:
                            logger.info(
                                f"Summarized page '{page.title}': "
                                f"~{body_tokens} → ~{count_tokens(page.content_summary)} tokens"
                            )
                    pages_with_body.append(page)
                else:
                    logger.warning(
                        f"Skipping page '{page.title}' (id={page.page_id}): "
                        f"no body returned (may be a folder or restricted page)"
                    )
            except Exception as e:
                logger.warning(f"Error fetching body for page '{page.title}': {e}")

        if len(pages_with_body) < len(relevant_pages):
            logger.info(
                f"Confluence: {len(pages_with_body)}/{len(relevant_pages)} "
                f"pages had fetchable bodies"
            )

        return {"confluence_pages": pages_with_body}

    async def _summarize_confluence_page(self, page) -> str | None:
        """Summarize a single Confluence page body with the LLM.

        Called for pages whose body exceeds ``max_body_tokens`` so the
        final PR summary prompt stays compact.
        """
        try:
            template = Template(CONFLUENCE_PAGE_SUMMARY_PROMPT)
            prompt = template.render(
                page_title=page.title,
                page_url=page.url,
                page_body=page.body,
            )
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            response = await self.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.warning(f"Error summarizing Confluence page '{page.title}': {e}")
            return None

    async def analyze_files(self, state: AgentState) -> Dict[str, Any]:
        """Analyze and categorize changed files."""
        logger.info("Analyzing files")
        
        current_pr = state.get("current_pr")
        if not current_pr or not current_pr.files:
            return {"file_stats": None, "grouped_files": {}}
        
        # Categorize files
        category_patterns = self.config.get("file_categories", {})
        file_stats = categorize_files(current_pr.files, category_patterns)
        grouped_files = group_files_by_category(current_pr.files, category_patterns)
        
        logger.info(f"Categorized {len(current_pr.files)} files into {len(grouped_files)} groups")
        
        return {"file_stats": file_stats, "grouped_files": grouped_files}
    
    # ── Shared LLM prompt helpers ────────────────────────────────────────

    def _get_token_budget(self) -> int:
        """Return the max tokens available for the user prompt (excluding system)."""
        llm_config = self.config.get("llm", {})
        max_context = llm_config.get("max_context_tokens", 7000)
        return max_context - count_tokens(SYSTEM_PROMPT)

    @staticmethod
    def _trim_review_threads(
        review_threads: list,
        budget_tokens: int,
    ) -> list:
        """Fallback trimming when LLM condensation is unavailable.

        Only used when ``_summarize_review_threads`` fails (e.g. rate limit).
        Strips diff_hunks first, then drops threads until under budget.
        The originals are never mutated — shallow copies are used.
        """
        from copy import copy as _copy

        def _estimate_tokens(threads: list) -> int:
            text = ""
            for t in threads:
                text += f"{t.file_path or ''} {t.line_range or ''}\n"
                if t.diff_hunk:
                    text += t.diff_hunk + "\n"
                for c in t.comments:
                    text += f"{c.author} {c.body}\n"
            return count_tokens(text)

        if _estimate_tokens(review_threads) <= budget_tokens:
            return review_threads

        # Stage 1: strip all diff_hunks
        trimmed = []
        for t in review_threads:
            tc = _copy(t)
            tc.diff_hunk = None
            trimmed.append(tc)

        if _estimate_tokens(trimmed) <= budget_tokens:
            logger.info(
                f"  Trimmed review threads: stripped diff_hunks "
                f"({len(trimmed)} threads kept)"
            )
            return trimmed

        # Stage 2: drop threads from the end until under budget
        while trimmed and _estimate_tokens(trimmed) > budget_tokens:
            trimmed.pop()

        logger.info(
            f"  Trimmed review threads: reduced to {len(trimmed)} "
            f"of {len(review_threads)} threads"
        )
        return trimmed

    async def _summarize_review_threads(
        self,
        review_threads: list,
        budget_tokens: int,
    ) -> str:
        """Use the LLM to condense review threads into a compact text summary.

        Threads are batched so each LLM call fits within the input limit.
        Returns a single string with all threads condensed, suitable for
        embedding in downstream prompts.
        """
        if not review_threads:
            return ""

        # We need headroom for the condensation prompt template overhead
        llm_config = self.config.get("llm", {})
        max_input = llm_config.get("max_context_tokens", 7500)
        system_tokens = count_tokens(SYSTEM_PROMPT)
        # Reserve ~300 tokens for the template framing around the threads
        per_call_budget = max_input - system_tokens - 300

        # Estimate tokens per thread to batch them
        def _thread_tokens(t) -> int:
            text = f"{t.file_path or ''} {t.line_range or ''}\n"
            if t.diff_hunk:
                text += t.diff_hunk + "\n"
            for c in t.comments:
                text += f"{c.author} {c.body}\n"
            return count_tokens(text)

        # Build batches that fit within per_call_budget
        batches: list[list] = []
        current_batch: list = []
        current_tokens = 0
        for t in review_threads:
            t_tokens = _thread_tokens(t)
            if current_batch and current_tokens + t_tokens > per_call_budget:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            current_batch.append(t)
            current_tokens += t_tokens
        if current_batch:
            batches.append(current_batch)

        logger.info(
            f"  Condensing {len(review_threads)} review threads "
            f"in {len(batches)} batch(es)"
        )

        condensed_parts: list[str] = []
        template = Template(REVIEW_THREADS_CONDENSE_PROMPT)

        for batch_idx, batch in enumerate(batches):
            try:
                prompt = template.render(threads=batch)
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ]
                response = await self.llm.ainvoke(messages)
                condensed_parts.append(response.content)
                logger.info(
                    f"    Batch {batch_idx + 1}/{len(batches)}: "
                    f"{len(batch)} threads condensed"
                )
            except Exception as e:
                logger.warning(
                    f"    Batch {batch_idx + 1}/{len(batches)} condensation "
                    f"failed: {e}. Falling back to mechanical trimming."
                )
                # Return None to signal the caller to fall back
                return None

        full_condensed = "\n\n".join(condensed_parts)

        # If the condensed text still exceeds the downstream budget, truncate
        condensed_tokens = count_tokens(full_condensed)
        if condensed_tokens > budget_tokens:
            ratio = budget_tokens / max(condensed_tokens, 1)
            keep = int(len(full_condensed) * ratio * 0.9)
            last_nl = full_condensed[:keep].rfind("\n")
            if last_nl > keep // 3:
                keep = last_nl
            full_condensed = full_condensed[:keep] + "\n...(truncated)"
            logger.info(
                f"  Condensed summary still over budget "
                f"(~{condensed_tokens} > {budget_tokens}), truncated"
            )

        logger.info(
            f"  Condensed {len(review_threads)} threads → "
            f"~{count_tokens(full_condensed)} tokens"
        )
        return full_condensed

    async def _invoke_llm_within_budget(
        self,
        template_str: str,
        template_vars: dict,
        node_name: str,
        precomputed_condensed: str | None = None,
    ) -> str:
        """Render *template_str* with *template_vars*, condense or trim
        review_threads if needed, and call the LLM.

        When the prompt exceeds the token budget and ``review_threads``
        is present:
          1. **Pre-computed condensation** — reuse the cached condensed text
             produced once by ``build_review_threads`` (avoids redundant LLM calls).
          2. **LLM condensation** — batch-summarize threads into compact text
             (only if no pre-computed version is available).
          3. **Mechanical trimming** — fallback if condensation fails; truncates
             diff_hunks progressively, then drops threads.
        """
        template = Template(template_str)
        prompt = template.render(**template_vars)
        budget = self._get_token_budget()
        prompt_tokens = count_tokens(prompt)

        if prompt_tokens > budget and "review_threads" in template_vars:
            threads = template_vars["review_threads"]
            # Allocate ~60% of budget to review thread content
            thread_budget = int(budget * 0.6)

            logger.info(
                f"  [{node_name}] prompt ~{prompt_tokens} tokens exceeds "
                f"budget ~{budget}. Condensing review threads."
            )

            # Stage 1: Use pre-computed condensed summary if available
            condensed = precomputed_condensed
            if condensed is not None:
                logger.info(
                    f"  [{node_name}] Reusing pre-computed condensed review threads"
                )
            else:
                # Stage 2: LLM condensation (only if no cached version)
                logger.info(
                    f"  [{node_name}] No pre-computed condensation available, "
                    f"summarizing via LLM."
                )
                condensed = await self._summarize_review_threads(
                    threads, thread_budget,
                )

            if condensed is not None:
                # Use condensed text instead of raw thread objects
                template_vars["review_threads"] = []
                template_vars["review_threads_summary"] = condensed
                prompt = template.render(**template_vars)
                prompt_tokens = count_tokens(prompt)

            # Stage 3: Mechanical trimming fallback
            if prompt_tokens > budget:
                logger.info(
                    f"  [{node_name}] Still over budget after condensation "
                    f"(~{prompt_tokens}). Applying mechanical trimming."
                )
                # Restore threads if condensation was used, trim mechanically
                if condensed is not None:
                    # Condensation produced text but it's still too big
                    template_vars.pop("review_threads_summary", None)
                    template_vars["review_threads"] = threads
                template_vars["review_threads"] = self._trim_review_threads(
                    template_vars["review_threads"], thread_budget,
                )
                prompt = template.render(**template_vars)
                prompt_tokens = count_tokens(prompt)

        logger.info(f"  [{node_name}] prompt: ~{prompt_tokens} tokens (budget: ~{budget})")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = await self.llm.ainvoke(messages)
        return response.content

    # ── Diff helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _split_patch_into_chunks(patch: str, max_tokens: int) -> list[str]:
        """Split a large patch into newline-aligned chunks of ≤ *max_tokens*.

        Each chunk is cut at the last newline that keeps it under budget so
        we never break a diff line in the middle.
        """
        total_tokens = count_tokens(patch)
        if total_tokens <= max_tokens:
            return [patch]

        chunks: list[str] = []
        remaining = patch
        while remaining:
            if count_tokens(remaining) <= max_tokens:
                chunks.append(remaining)
                break
            # Estimate character count for the budget
            ratio = max_tokens / max(count_tokens(remaining), 1)
            cut = int(len(remaining) * ratio * 0.85)  # 15% safety margin
            cut = max(cut, 200)  # never go below a reasonable minimum
            # Snap to newline
            last_nl = remaining[:cut].rfind("\n")
            if last_nl > cut // 3:
                cut = last_nl + 1  # include the newline in this chunk
            chunks.append(remaining[:cut])
            remaining = remaining[cut:]

        logger.info(
            f"    Split oversized patch (~{total_tokens} tokens) into "
            f"{len(chunks)} chunk(s)"
        )
        return chunks

    @staticmethod
    def _is_token_limit_error(exc: Exception) -> bool:
        """Return True if the exception looks like a 413 / token-limit error."""
        msg = str(exc).lower()
        return "413" in msg or "too large" in msg or "tokens_limit_reached" in msg

    async def _summarize_batch(
        self,
        category: str,
        batch_diffs: list,
        previous_summary: str | None,
        max_tokens_per_batch: int,
    ) -> str | None:
        """Send one diff batch to the LLM.  On 413, split and retry."""
        template = Template(DIFF_BATCH_SUMMARY_PROMPT)
        prompt = template.render(
            category=category,
            previous_summary=previous_summary,
            diffs=batch_diffs,
        )

        prompt_tokens = count_tokens(prompt)
        system_tokens = count_tokens(SYSTEM_PROMPT)
        logger.info(
            f"  Batch ({len(batch_diffs)} files): "
            f"~{prompt_tokens}+{system_tokens} tokens"
            f"{' (chained)' if previous_summary else ''}"
        )

        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            response = await self.llm.ainvoke(messages)
            return response.content

        except Exception as e:
            if not self._is_token_limit_error(e):
                raise  # non-retriable, let the caller handle

            # ── 413 retry: split batch in half ──────────────────────
            if len(batch_diffs) == 1:
                # Single file — split its patch into chunks and chain-summarize
                f = batch_diffs[0]
                logger.warning(
                    f"  Single file {f.path} too large, splitting patch into chunks"
                )
                chunks = self._split_patch_into_chunks(
                    f.patch, max_tokens_per_batch
                )
                chunk_summary = previous_summary
                original_patch = f.patch
                try:
                    for ci, chunk in enumerate(chunks):
                        f.patch = chunk
                        chunk_prompt = template.render(
                            category=category,
                            previous_summary=chunk_summary,
                            diffs=batch_diffs,
                        )
                        logger.info(
                            f"    Chunk {ci + 1}/{len(chunks)} of {f.path}: "
                            f"~{count_tokens(chunk_prompt)} tokens"
                        )
                        messages = [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": chunk_prompt},
                        ]
                        response = await self.llm.ainvoke(messages)
                        chunk_summary = response.content
                    return chunk_summary
                except Exception as retry_exc:
                    logger.error(
                        f"  Chunk retry failed on {f.path}: {retry_exc}"
                    )
                    return chunk_summary or previous_summary
                finally:
                    f.patch = original_patch  # restore original
            else:
                # Multiple files — split in half and chain
                mid = len(batch_diffs) // 2
                logger.warning(
                    f"  413 on {len(batch_diffs)} files, splitting "
                    f"into {mid} + {len(batch_diffs) - mid}"
                )
                result = await self._summarize_batch(
                    category, batch_diffs[:mid],
                    previous_summary, max_tokens_per_batch,
                )
                result = await self._summarize_batch(
                    category, batch_diffs[mid:],
                    result, max_tokens_per_batch,
                )
                return result

    # ── Main diff summarization node ────────────────────────────────────

    async def summarize_diffs(self, state: AgentState) -> Dict[str, Any]:
        """Summarize file diffs via map-reduce batching per category.

        For each file category (frontend, backend, tests, …):
        1. Collect files that have a non-empty patch and aren't in the skip list.
        2. Split into token-budgeted batches.
        3. Summarize each batch with the LLM, chaining the previous batch's
           summary as rolling context so the final output is cumulative.
        """
        logger.info("Summarizing diffs (map-reduce)")

        diff_config = self.config.get("diff_analysis", {})
        if not diff_config.get("enabled", True):
            logger.info("Diff analysis disabled in config")
            return {"diff_summaries": {}}

        grouped_files = state.get("grouped_files", {})
        if not grouped_files:
            return {"diff_summaries": {}}

        max_tokens_per_batch = diff_config.get("max_tokens_per_batch", 4_000)
        skip_patterns = diff_config.get("skip_patterns", [])

        diff_summaries: Dict[str, str] = {}
        skipped_files: list[str] = []

        for category, files in grouped_files.items():
            # ── Filter: keep files with patches, skip noise ──────────
            analysable = []
            for f in files:
                if not f.patch:
                    continue
                if any(fnmatch(f.path, pat) for pat in skip_patterns):
                    skipped_files.append(f.path)
                    continue
                analysable.append(f)

            if not analysable:
                continue

            # ── Build per-file text blobs for batching ───────────────
            file_texts = []
            for f in analysable:
                blob = (
                    f"### {f.path} ({f.status}, +{f.additions}/-{f.deletions})\n"
                    f"```diff\n{f.patch}\n```\n"
                )
                file_texts.append(blob)

            batches = batch_texts_by_tokens(file_texts, max_tokens_per_batch)
            logger.info(
                f"Category '{category}': {len(analysable)} files → "
                f"{len(batches)} batch(es)"
            )

            # ── Chain-summarize batches ──────────────────────────────
            previous_summary: str | None = None
            for batch_idx, batch_texts_list in enumerate(batches):
                # Reconstruct diff data for the prompt template
                batch_diffs = []
                text_cursor = 0
                for f in analysable:
                    blob = (
                        f"### {f.path} ({f.status}, +{f.additions}/-{f.deletions})\n"
                        f"```diff\n{f.patch}\n```\n"
                    )
                    if text_cursor < len(batch_texts_list) and blob == batch_texts_list[text_cursor]:
                        batch_diffs.append(f)
                        text_cursor += 1
                    if text_cursor >= len(batch_texts_list):
                        break

                logger.info(
                    f"  [{category}] Batch {batch_idx + 1}/{len(batches)}"
                )

                try:
                    result = await self._summarize_batch(
                        category, batch_diffs,
                        previous_summary, max_tokens_per_batch,
                    )
                    if result:
                        previous_summary = result
                except Exception as e:
                    logger.error(
                        f"Error summarizing diffs for {category} "
                        f"batch {batch_idx + 1}: {e}"
                    )
                    # Keep whatever summary we had from the previous batch
                    break

            if previous_summary:
                diff_summaries[category] = previous_summary

        total_files_summarized = sum(
            len([f for f in files if f.patch and not any(fnmatch(f.path, p) for p in skip_patterns)])
            for files in grouped_files.values()
        )
        logger.info(
            f"Diff summarization complete: {len(diff_summaries)} categories, "
            f"{total_files_summarized} files analysed"
        )

        return {"diff_summaries": diff_summaries}

    async def generate_summary(self, state: AgentState) -> Dict[str, Any]:
        """Generate AI summary of the PR using all available knowledge sources.

        If the full prompt exceeds the model's context budget, sections are
        progressively trimmed (largest first) and the prompt is re-rendered
        until it fits.  This guarantees a summary is always produced.
        """
        logger.info("Generating PR summary")
        
        current_pr = state.get("current_pr")
        if not current_pr:
            return {}
        
        try:
            # ── Gather all knowledge sources ─────────────────────────
            jira_context = list(state.get("jira_tickets", []))
            confluence_pages = list(state.get("confluence_pages", []))
            figma_files = state.get("figma_files", [])
            diff_summaries = dict(state.get("diff_summaries", {}))

            # File change list (fallback when diff_summaries is empty)
            file_changes = [
                {"path": f.path, "additions": f.additions, "deletions": f.deletions}
                for f in current_pr.files[:30]
            ]

            # Skipped files (those without patches or in skip list)
            diff_config = self.config.get("diff_analysis", {})
            skip_patterns = diff_config.get("skip_patterns", [])
            skipped_files = [
                f.path for f in current_pr.files
                if not f.patch or any(fnmatch(f.path, pat) for pat in skip_patterns)
            ]

            # ── Token budget ─────────────────────────────────────────
            llm_config = self.config.get("llm", {})
            max_context = llm_config.get("max_context_tokens", 7000)
            system_tokens = count_tokens(SYSTEM_PROMPT)
            budget = max_context - system_tokens  # tokens available for user prompt

            pr_description = current_pr.body or ""

            def _render() -> str:
                template = Template(PR_SUMMARY_PROMPT)
                return template.render(
                    pr_title=current_pr.title,
                    pr_description=pr_description,
                    jira_context=jira_context,
                    confluence_pages=confluence_pages,
                    figma_files=figma_files,
                    diff_summaries=diff_summaries,
                    file_changes=file_changes,
                    skipped_files=skipped_files,
                )

            prompt = _render()
            prompt_tokens = count_tokens(prompt)

            # ── Progressive trimming if over budget ──────────────────
            if prompt_tokens > budget:
                logger.warning(
                    f"Summary prompt ~{prompt_tokens} tokens exceeds budget "
                    f"~{budget}. Trimming sections."
                )

                # 1. Drop full Confluence bodies (summaries remain)
                for page in confluence_pages:
                    if hasattr(page, "content_summary") and page.content_summary:
                        page.body = None  # template prefers content_summary
                prompt = _render()
                prompt_tokens = count_tokens(prompt)
                if prompt_tokens <= budget:
                    logger.info(f"  After dropping Confluence bodies: ~{prompt_tokens}")

                # 2. Trim Jira descriptions to first 500 chars
                if prompt_tokens > budget:
                    for ticket in jira_context:
                        if hasattr(ticket, "description") and ticket.description and len(ticket.description) > 500:
                            ticket.description = ticket.description[:500] + "..."
                        if hasattr(ticket, "acceptance_criteria") and ticket.acceptance_criteria and len(ticket.acceptance_criteria) > 500:
                            ticket.acceptance_criteria = ticket.acceptance_criteria[:500] + "..."
                    prompt = _render()
                    prompt_tokens = count_tokens(prompt)
                    if prompt_tokens <= budget:
                        logger.info(f"  After trimming Jira text: ~{prompt_tokens}")

                # 3. Trim diff summaries to ~300 tokens each
                if prompt_tokens > budget:
                    for cat in list(diff_summaries):
                        summary_text = diff_summaries[cat]
                        if count_tokens(summary_text) > 300:
                            # Keep first ~300 tokens worth of characters
                            ratio = 300 / max(count_tokens(summary_text), 1)
                            keep = int(len(summary_text) * ratio * 0.9)
                            last_nl = summary_text[:keep].rfind("\n")
                            if last_nl > keep // 3:
                                keep = last_nl
                            diff_summaries[cat] = summary_text[:keep] + "..."
                    prompt = _render()
                    prompt_tokens = count_tokens(prompt)
                    if prompt_tokens <= budget:
                        logger.info(f"  After trimming diff summaries: ~{prompt_tokens}")

                # 4. Trim PR description
                if prompt_tokens > budget and count_tokens(pr_description) > 300:
                    ratio = 300 / max(count_tokens(pr_description), 1)
                    keep = int(len(pr_description) * ratio * 0.9)
                    last_nl = pr_description[:keep].rfind("\n")
                    if last_nl > keep // 3:
                        keep = last_nl
                    pr_description = pr_description[:keep] + "..."
                    prompt = _render()
                    prompt_tokens = count_tokens(prompt)
                    if prompt_tokens <= budget:
                        logger.info(f"  After trimming PR description: ~{prompt_tokens}")

                # 5. Drop Confluence pages entirely
                if prompt_tokens > budget:
                    confluence_pages = []
                    prompt = _render()
                    prompt_tokens = count_tokens(prompt)
                    logger.info(f"  After dropping Confluence: ~{prompt_tokens}")

                # 6. Reduce file change list
                if prompt_tokens > budget:
                    file_changes = file_changes[:10]
                    skipped_files = skipped_files[:5]
                    prompt = _render()
                    prompt_tokens = count_tokens(prompt)
                    logger.info(f"  After reducing file lists: ~{prompt_tokens}")

            logger.info(f"Summary prompt: ~{prompt_tokens} tokens (budget: ~{budget})")
            
            # Generate summary
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            
            response = await self.llm.ainvoke(messages)
            logger.info("Generated AI summary")
            return {"ai_summary": response.content}
        
        except Exception as e:
            if should_log_errors(self.config):
                logger.error(f"Error generating summary: {e}")
            add_error(state, str(e), "generate_summary", self.config)
            
            # Re-raise if not configured to continue on error
            if not should_continue_on_error(self.config):
                raise
        
        return {"ai_summary": "Error generating summary."}
    
    async def build_review_threads(self, state: AgentState) -> Dict[str, Any]:
        """Convert flat review comments into threaded conversations.

        Groups comments by reply chains (in_reply_to_id), preserves
        diff_hunk code context, and sorts chronologically.  Runs once;
        downstream nodes read review_threads from state.
        """
        logger.info("Building review threads")

        current_pr = state.get("current_pr")
        if not current_pr or not current_pr.review_comments:
            return {"review_threads": []}

        threads = build_review_threads(current_pr.review_comments)

        # Write review threads to file for debugging/inspection
        import json as _json
        from pathlib import Path as _Path
        output_dir = _Path(self.config.get("output", {}).get("directory", "outputs"))
        output_dir.mkdir(parents=True, exist_ok=True)
        rc_path = output_dir / f"PR-{current_pr.number}-review-comments.json"
        thread_data = [
            {
                "file_path": t.file_path,
                "line_range": t.line_range,
                "is_resolved": t.is_resolved,
                "comments": [{"author": c.author, "body": c.body, "created_at": c.created_at} for c in t.comments],
            }
            for t in threads
        ]
        with open(rc_path, "w") as _f:
            _json.dump(thread_data, _f, indent=2, default=str)
        logger.info(
            f"Built {len(threads)} review threads from "
            f"{len(current_pr.review_comments)} comments → {rc_path}"
        )

        # Pre-compute condensed review threads once so downstream nodes
        # (coding_standards, architectural_patterns, review_summary) can
        # reuse it instead of re-summarizing each time.
        condensed = None
        budget = self._get_token_budget()
        thread_budget = int(budget * 0.6)
        # Only condense if the raw threads are large enough to exceed budget
        from src.utils.tokens import count_tokens as _count_tokens

        def _estimate_raw_tokens(threads_list) -> int:
            total = 0
            for t in threads_list:
                text = f"{t.file_path or ''} {t.line_range or ''}\n"
                if t.diff_hunk:
                    text += t.diff_hunk + "\n"
                for c in t.comments:
                    text += f"{c.author} {c.body}\n"
                total += _count_tokens(text)
            return total

        raw_tokens = _estimate_raw_tokens(threads)
        if raw_tokens > thread_budget:
            logger.info(
                f"  Pre-condensing review threads (~{raw_tokens} tokens > "
                f"budget ~{thread_budget}) for downstream reuse"
            )
            condensed = await self._summarize_review_threads(
                threads, thread_budget,
            )
            if condensed is not None:
                logger.info(
                    f"  Pre-condensed review threads: "
                    f"~{_count_tokens(condensed)} tokens (reusable)"
                )
            else:
                logger.info("  Pre-condensation failed; downstream nodes will trim mechanically")

        return {"review_threads": threads, "review_threads_condensed": condensed}

    async def identify_coding_standards(self, state: AgentState) -> Dict[str, Any]:
        """Identify coding standards and patterns from reviews."""
        logger.info("Identifying coding standards")
        
        current_pr = state.get("current_pr")
        
        if not current_pr:
            return {}
        
        review_threads = list(state.get("review_threads", []))
        if not review_threads:
            logger.info("No review threads — skipping coding standards")
            return {"coding_standards": None}
        
        try:
            file_changes = [
                {"path": f.path, "additions": f.additions, "deletions": f.deletions}
                for f in current_pr.files
            ]
            
            coding_standards = await self._invoke_llm_within_budget(
                CODING_STANDARDS_PROMPT,
                {
                    "pr_title": current_pr.title,
                    "review_threads": review_threads,
                    "file_changes": file_changes,
                },
                "identify_coding_standards",
                precomputed_condensed=state.get("review_threads_condensed"),
            )
            
            # Only set if actual standards are identified
            if "no explicit coding standards" not in coding_standards.lower():
                logger.info("Identified coding standards")
                return {"coding_standards": coding_standards}
            
            logger.info("No explicit coding standards found")
            return {"coding_standards": None}
            
        except Exception as e:
            if should_log_errors(self.config):
                logger.error(f"Error identifying coding standards: {e}")
            
            # Re-raise if not configured to continue on error
            if not should_continue_on_error(self.config):
                raise
        
        return {"coding_standards": None}
    
    async def identify_architectural_patterns(self, state: AgentState) -> Dict[str, Any]:
        """Identify architectural patterns and design principles."""
        logger.info("Identifying architectural patterns")
        
        current_pr = state.get("current_pr")
        file_stats = state.get("file_stats")
        
        if not current_pr:
            return {}
        
        review_threads = list(state.get("review_threads", []))
        if not review_threads:
            logger.info("No review threads — skipping architectural patterns")
            return {"architectural_patterns": None}
        
        try:
            
            architectural_patterns = await self._invoke_llm_within_budget(
                ARCHITECTURAL_PATTERNS_PROMPT,
                {
                    "pr_title": current_pr.title,
                    "file_stats": file_stats.dict() if file_stats else {},
                    "grouped_files": state.get("grouped_files", {}),
                    "review_threads": review_threads,
                    "jira_context": state.get("jira_tickets", []),
                },
                "identify_architectural_patterns",
                precomputed_condensed=state.get("review_threads_condensed"),
            )
            
            # Only set if actual patterns are identified
            if "no distinctive architectural patterns" not in architectural_patterns.lower():
                logger.info("Identified architectural patterns")
                return {"architectural_patterns": architectural_patterns}
            
            logger.info("No distinctive architectural patterns found")
            return {"architectural_patterns": None}
            
        except Exception as e:
            if should_log_errors(self.config):
                logger.error(f"Error identifying architectural patterns: {e}")
            
            # Re-raise if not configured to continue on error
            if not should_continue_on_error(self.config):
                raise
        
        return {"architectural_patterns": None}
    
    async def generate_review_summary(self, state: AgentState) -> Dict[str, Any]:
        """Generate summary of review comments."""
        logger.info("Generating review summary")
        
        current_pr = state.get("current_pr")
        
        if not current_pr:
            return {}
        
        review_threads = list(state.get("review_threads", []))
        if not review_threads:
            logger.info("No review threads — skipping review summary")
            return {"review_summary": None}
        
        try:

            content = await self._invoke_llm_within_budget(
                REVIEW_SUMMARY_PROMPT,
                {"review_threads": review_threads},
                "generate_review_summary",
                precomputed_condensed=state.get("review_threads_condensed"),
            )
            
            logger.info("Generated review summary")
            return {"review_summary": content}
            
        except Exception as e:
            if should_log_errors(self.config):
                logger.error(f"Error generating review summary: {e}")
            
            # Re-raise if not configured to continue on error
            if not should_continue_on_error(self.config):
                raise
        
        return {"review_summary": None}
    
    async def identify_breaking_changes(self, state: AgentState) -> Dict[str, Any]:
        """Identify breaking changes."""
        logger.info("Identifying breaking changes")
        
        current_pr = state.get("current_pr")
        if not current_pr:
            return {}
        
        try:
            file_changes = [f.path for f in current_pr.files]
            
            breaking_changes = await self._invoke_llm_within_budget(
                BREAKING_CHANGES_PROMPT,
                {
                    "pr_title": current_pr.title,
                    "pr_description": current_pr.body or "",
                    "file_changes": file_changes,
                },
                "identify_breaking_changes",
            )
            
            # Only set if actual breaking changes found
            if "none detected" not in breaking_changes.lower():
                return {"breaking_changes": breaking_changes}
            
            return {"breaking_changes": None}
            
        except Exception as e:
            if should_log_errors(self.config):
                logger.error(f"Error identifying breaking changes: {e}")
            
            # Re-raise if not configured to continue on error
            if not should_continue_on_error(self.config):
                raise
        
        return {"breaking_changes": None}
    
    async def save_summary(self, state: AgentState) -> Dict[str, Any]:
        """Save the generated summary to a file."""
        logger.info("Saving PR summary")
        
        current_pr = state.get("current_pr")
        if not current_pr:
            return {}
        
        try:
            # Use appropriate template
            from pathlib import Path
            import os
            
            template_dir = Path(self.config.get("templates", {}).get("directory", "templates"))
            
            # Check if we have rich context or if partial summaries are disabled
            has_context = (
                state.get("jira_tickets") or
                state.get("figma_files") or
                state.get("confluence_pages")
            )
            
            # Use fallback template if:
            # 1. No rich context available AND
            # 2. Partial summary generation is enabled (otherwise skip this PR)
            use_fallback = not has_context
            
            if use_fallback and not should_generate_partial_summaries(self.config):
                # Skip generating summary for this PR if partial summaries are disabled
                logger.info(f"Skipping PR {current_pr.number} - no rich context and partial summaries disabled")
                new_index = state.get("current_pr_index", 0) + 1
                state["current_pr_index"] = new_index
                return {"current_pr_index": new_index}
            
            if has_context:
                template_file = template_dir / "pr_summary_template.md"
            else:
                template_file = template_dir / "pr_summary_fallback.md"
            
            with open(template_file, "r") as f:
                template_content = f.read()
            
            template = Template(template_content)
            
            # Prepare data for template
            total_stats = get_total_stats(state.get("file_stats"))

            # Build per-file diff URLs for the PR (GitHub anchor = sha256 of path)
            file_diff_urls = {}
            for category_files in state.get("grouped_files", {}).values():
                for f in category_files:
                    anchor = hashlib.sha256(f.path.encode()).hexdigest()
                    file_diff_urls[f.path] = f"{current_pr.url}/files#diff-{anchor}"
            
            summary_content = template.render(
                pr_number=current_pr.number,
                pr_title=current_pr.title,
                pr_author=current_pr.author,
                merge_date=current_pr.merged_at.strftime("%Y-%m-%d %H:%M:%S"),
                source_branch=current_pr.source_branch,
                target_branch=current_pr.target_branch,
                pr_url=current_pr.url,
                pr_description=current_pr.body or "",
                ai_summary=state.get("ai_summary", ""),
                jira_tickets=state.get("jira_tickets", []),
                figma_files=state.get("figma_files", []),
                confluence_pages=state.get("confluence_pages", []),
                file_stats=state.get("file_stats"),
                grouped_files=state.get("grouped_files", {}),
                file_diff_urls=file_diff_urls,
                total_files=total_stats.get("total_files", 0),
                total_additions=total_stats.get("total_additions", 0),
                total_deletions=total_stats.get("total_deletions", 0),
                coding_standards=state.get("coding_standards", ""),
                architectural_patterns=state.get("architectural_patterns", ""),
                review_summary=state.get("review_summary", ""),
                breaking_changes=state.get("breaking_changes"),
                reviewers=list(dict.fromkeys(r.reviewer for r in current_pr.reviews)),
                approvals_count=len([r for r in current_pr.reviews if r.state == "APPROVED"]),
                review_comments_count=len(current_pr.review_comments),
                generation_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            
            # Append error information if configured
            if should_include_errors_in_summary(self.config) and state.get("errors"):
                error_section = "\n\n---\n\n## ⚠️ Processing Errors\n\n"
                error_section += "The following errors occurred while processing this PR:\n\n"
                for error in state.get("errors", []):
                    error_section += f"- **{error.get('context', 'Unknown')}**: {error.get('message', '')}\n"
                    error_section += f"  *Timestamp: {error.get('timestamp', '')}*\n\n"
                summary_content += error_section
            
            # Save to file
            output_config = self.config.get("output", {})
            output_dir = Path(output_config.get("directory", "outputs"))
            output_dir.mkdir(parents=True, exist_ok=True)
            
            repo_name = state.get("repo_name", "unknown")
            
            # Use filename pattern from config
            filename_pattern = output_config.get("filename_pattern", "PR-{number}-{repo_name}-summary.md")
            filename = filename_pattern.format(
                number=current_pr.number,
                repo_name=repo_name
            )
            output_path = output_dir / filename
            
            # Check if file exists and respect overwrite_existing setting
            overwrite_existing = output_config.get("overwrite_existing", True)
            if output_path.exists() and not overwrite_existing:
                logger.warning(f"File {output_path} already exists and overwrite_existing=false, skipping")
                state["output_files"].append(str(output_path))
                new_index = state.get("current_pr_index", 0) + 1
                state["current_pr_index"] = new_index
                return {
                    "output_files": state["output_files"],
                    "current_pr_index": new_index,
                }
            
            # Add metadata if configured
            include_metadata = output_config.get("include_metadata", False)
            if include_metadata:
                metadata = f"---\n"
                metadata += f"pr_number: {current_pr.number}\n"
                metadata += f"repo: {repo_name}\n"
                metadata += f"title: {current_pr.title}\n"
                metadata += f"author: {current_pr.author}\n"
                metadata += f"merged_at: {current_pr.merged_at}\n"
                metadata += f"generated_at: {state.get('errors', [{}])[-1].get('timestamp', '') if state.get('errors') else ''}\n"
                metadata += f"---\n\n"
                summary_content = metadata + summary_content
            
            with open(output_path, "w") as f:
                f.write(summary_content)
            
            # Mutate state lists in-place (side effects)
            state["output_files"].append(str(output_path))
            
            summary_record = PRSummary(
                pr_number=current_pr.number,
                summary_text=state.get("ai_summary", ""),
                coding_standards=state.get("coding_standards"),
                architectural_patterns=state.get("architectural_patterns"),
                review_summary=state.get("review_summary"),
                breaking_changes=state.get("breaking_changes"),
            )
            state["summaries"].append(summary_record)
            
            new_index = state.get("current_pr_index", 0) + 1
            state["current_pr_index"] = new_index
            
            logger.info(f"Saved summary to: {output_path}")
            
            return {
                "output_files": state["output_files"],
                "summaries": state["summaries"],
                "current_pr_index": new_index,
            }
        
        except Exception as e:
            if should_log_errors(self.config):
                import traceback
                logger.error(f"Error saving summary: {e}")
                logger.error(f"Full traceback:\n{traceback.format_exc()}")
            add_error(state, str(e), "save_summary", self.config)
            
            # Re-raise if not configured to continue on error
            if not should_continue_on_error(self.config):
                raise
        
        return {}
