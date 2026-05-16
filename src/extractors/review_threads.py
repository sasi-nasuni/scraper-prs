"""
Utility for converting flat PR review comments into threaded conversations.

Groups comments by their reply chains (using in_reply_to_id), preserves the
full diff_hunk code context from the root comment, and sorts each thread
chronologically.
"""
import logging
from collections import defaultdict
from typing import Dict, List, Optional

from src.agent.state import PRReviewComment, ReviewThread

logger = logging.getLogger(__name__)


def build_review_threads(comments: List[PRReviewComment]) -> List[ReviewThread]:
    """Convert a flat list of review comments into threaded conversations.

    Algorithm:
    1. Index all comments by their ``id``.
    2. Group comments into chains using ``in_reply_to_id``:
       - Comments without ``in_reply_to_id`` are potential roots.
       - Replies are attached to their root comment (walking up the chain).
    3. For each group, build a ``ReviewThread`` with:
       - ``file_path`` / ``line_range`` / ``diff_hunk`` from the root comment
       - ``comments`` sorted by ``created_at``
       - ``is_resolved`` inferred from the last comment body

    Comments that lack an ``id`` (e.g. issue comments mixed in) are collected
    into a single "General Discussion" thread.

    Args:
        comments: Flat list of ``PRReviewComment`` objects.

    Returns:
        List of ``ReviewThread`` objects, sorted by file path then line number.
    """
    if not comments:
        return []

    # ── Index comments by id ─────────────────────────────────────────
    by_id: Dict[int, PRReviewComment] = {}
    no_id: List[PRReviewComment] = []

    for c in comments:
        if c.id is not None:
            by_id[c.id] = c
        else:
            no_id.append(c)

    # ── Find root id for every comment ───────────────────────────────
    root_cache: Dict[int, int] = {}

    def _find_root(comment_id: int) -> int:
        """Walk up the reply chain to find the root comment id."""
        if comment_id in root_cache:
            return root_cache[comment_id]

        visited = []
        current = comment_id
        while True:
            visited.append(current)
            c = by_id.get(current)
            if c is None or c.in_reply_to_id is None:
                # current is the root (or the chain is broken)
                break
            if c.in_reply_to_id in root_cache:
                current = root_cache[c.in_reply_to_id]
                break
            current = c.in_reply_to_id

        # Cache the root for every node we visited
        for v in visited:
            root_cache[v] = current
        return current

    # ── Group comments by root ───────────────────────────────────────
    groups: Dict[int, List[PRReviewComment]] = defaultdict(list)
    for c in comments:
        if c.id is None:
            continue
        root_id = _find_root(c.id)
        groups[root_id].append(c)

    # ── Build ReviewThread objects ───────────────────────────────────
    threads: List[ReviewThread] = []

    for root_id, group_comments in groups.items():
        # Sort chronologically
        group_comments.sort(key=lambda c: c.created_at)

        root = by_id.get(root_id, group_comments[0])

        # Determine line range from root comment
        line_range: Optional[str] = None
        if root.line is not None:
            if root.start_line is not None and root.start_line != root.line:
                line_range = f"{root.start_line}-{root.line}"
            else:
                line_range = str(root.line)

        # Detect resolution from the last comment body
        is_resolved = _detect_resolution(group_comments[-1].body) if group_comments else False

        threads.append(ReviewThread(
            file_path=root.path,
            line_range=line_range,
            diff_hunk=root.diff_hunk,
            comments=group_comments,
            is_resolved=is_resolved,
        ))

    # ── Handle orphan comments without ids (general discussion) ──────
    if no_id:
        no_id.sort(key=lambda c: c.created_at)
        threads.append(ReviewThread(
            file_path=None,
            line_range=None,
            diff_hunk=None,
            comments=no_id,
            is_resolved=False,
        ))

    # ── Sort threads: by file path, then line number ─────────────────
    def _sort_key(t: ReviewThread):
        path = t.file_path or "\xff"  # General discussion threads sort last
        try:
            first_line = int((t.line_range or "0").split("-")[0])
        except ValueError:
            first_line = 0
        return (path, first_line)

    threads.sort(key=_sort_key)

    logger.info(
        f"Built {len(threads)} review threads from {len(comments)} comments"
    )
    return threads


def _detect_resolution(body: str) -> bool:
    """Heuristic: check if a comment body indicates the thread was resolved.

    Looks for common resolution signals in the last comment of a thread.
    """
    if not body:
        return False
    lower = body.lower().strip()
    resolution_signals = [
        "done",
        "fixed",
        "resolved",
        "addressed",
        "updated",
        "applied",
        "good catch",
        "thanks, fixed",
        "will do",
        "pushed a fix",
    ]
    # Short comment that is a resolution signal
    if len(lower) < 80:
        for signal in resolution_signals:
            if signal in lower:
                return True
    return False
