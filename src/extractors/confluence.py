"""
Confluence URL extraction and search utilities.
"""
import re
from typing import List, Set
from urllib.parse import urlparse


# Regex pattern for Confluence URLs
CONFLUENCE_URL_PATTERN = re.compile(
    r'https?://[^/]+/(?:wiki/)?'
    r'(?:spaces/[^/]+/pages/\d+|display/[^/]+/[^?\s]+)'
)


def extract_confluence_urls(text: str) -> List[str]:
    """
    Extract Confluence page URLs from text.
    
    Args:
        text: Text to search for Confluence URLs
    
    Returns:
        List of unique Confluence URLs found
    """
    if not text:
        return []
    
    matches = CONFLUENCE_URL_PATTERN.findall(text)
    # Return unique URLs
    return list(set(matches))


def extract_confluence_page_id(confluence_url: str) -> str:
    """
    Extract the page ID from a Confluence URL.
    
    Args:
        confluence_url: Full Confluence URL
    
    Returns:
        Confluence page ID or empty string if not found
    """
    # Pattern for page ID in URL like /pages/123456
    page_id_pattern = re.compile(r'/pages/(\d+)')
    match = page_id_pattern.search(confluence_url)
    
    if match:
        return match.group(1)
    
    return ""


def validate_confluence_url(url: str) -> bool:
    """
    Validate that a URL is a valid Confluence URL.
    
    Args:
        url: URL to validate
    
    Returns:
        True if valid Confluence URL
    """
    return bool(CONFLUENCE_URL_PATTERN.match(url))


def generate_search_keywords(pr_title: str, max_keywords: int = 5) -> List[str]:
    """
    Generate search keywords from PR title for Confluence search.
    
    Args:
        pr_title: PR title
        max_keywords: Maximum number of keywords to return
    
    Returns:
        List of search keywords
    """
    if not pr_title:
        return []
    
    # Remove common prefixes
    title = pr_title
    for prefix in ['feat:', 'fix:', 'docs:', 'style:', 'refactor:', 'test:', 'chore:']:
        title = title.replace(prefix, '')
    
    # Remove special characters and split into words
    words = re.findall(r'\b[a-zA-Z]{3,}\b', title.lower())
    
    # Filter out common words
    stop_words = {
        'the', 'and', 'for', 'with', 'from', 'this', 'that',
        'add', 'update', 'fix', 'fixes', 'fixed', 'remove', 'delete',
        'create', 'implement', 'change', 'modify'
    }
    
    keywords = [word for word in words if word not in stop_words]
    
    # Return up to max_keywords
    return keywords[:max_keywords]


def format_confluence_search_query(
    jira_ids: List[str],
    keywords: List[str],
    free_text_phrases: List[str] | None = None,
) -> str:
    """
    Format a Confluence CQL (Confluence Query Language) search query.

    Builds an OR-combined query from three signal sources:
      1. Jira ticket IDs  – exact text matches (highest-signal)
      2. Free-text phrases – PR title and/or Jira ticket summaries
         searched as quoted phrases for relevance
      3. Keywords          – individual terms AND-ed together (fallback)

    Args:
        jira_ids: List of Jira ticket IDs to search for
        keywords: List of keywords to search for
        free_text_phrases: Optional list of short phrases (e.g. PR title,
            Jira ticket summary) to use as free-text queries.

    Returns:
        CQL query string
    """
    conditions = []

    # 1. Jira ID conditions – best signal
    if jira_ids:
        jira_conditions = ' OR '.join([f'text ~ "{jira_id}"' for jira_id in jira_ids])
        conditions.append(f'({jira_conditions})')

    # 2. Free-text phrase conditions – broad relevance
    if free_text_phrases:
        for phrase in free_text_phrases:
            clean = _sanitize_cql_phrase(phrase)
            if clean:
                conditions.append(f'(text ~ "{clean}")')

    # 3. Keyword conditions – narrowest fallback
    if keywords:
        keyword_conditions = ' AND '.join([f'text ~ "{keyword}"' for keyword in keywords])
        conditions.append(f'({keyword_conditions})')

    # Combine with OR so any signal source can contribute results
    if conditions:
        return ' OR '.join(conditions)

    return ""


def _sanitize_cql_phrase(text: str) -> str:
    """Sanitize a phrase for use inside a CQL ``text ~ "..."`` clause.

    Removes characters that break CQL syntax.
    """
    if not text:
        return ""
    # Strip leading conventional-commit prefixes
    cleaned = re.sub(r'^(?:feat|fix|docs|style|refactor|test|chore)\s*[:(]\s*', '', text, flags=re.IGNORECASE)
    # Remove characters that are problematic in CQL quoted strings
    cleaned = re.sub(r'["\\\n\r\t]+', ' ', cleaned)
    # Collapse whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def score_confluence_relevance(
    page_title: str,
    page_excerpt: str | None,
    jira_ids: List[str],
    pr_title: str,
    jira_ticket_titles: List[str],
    pr_keywords: List[str],
) -> float:
    """Score how relevant a Confluence page is to the current PR.

    Returns a score between 0.0 and 1.0.  Pages that score below a
    caller-chosen threshold should be dropped.

    Scoring signals (cumulative, capped at 1.0):
      - Jira ID appears in page title or excerpt  → +0.40 per match
      - Significant word overlap between page title
        and PR title / Jira ticket titles           → +0.30
      - PR keyword found in page title or excerpt  → +0.05 per keyword (max 0.30)
    """
    score = 0.0
    haystack = f"{page_title} {page_excerpt or ''}".lower()

    # 1. Jira ID match — strongest signal
    for jid in jira_ids:
        if jid.lower() in haystack:
            score += 0.40

    # 2. Title word overlap — compare meaningful words
    page_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', page_title.lower()))
    reference_titles = [pr_title] + jira_ticket_titles
    for ref_title in reference_titles:
        ref_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', ref_title.lower()))
        if ref_words:
            overlap = page_words & ref_words
            ratio = len(overlap) / min(len(page_words), len(ref_words)) if page_words else 0
            if ratio >= 0.3:  # at least 30% word overlap
                score += 0.30 * ratio

    # 3. Keyword hits in page content
    for kw in pr_keywords:
        if kw.lower() in haystack:
            score += 0.05

    return min(score, 1.0)
