"""
Token counting utilities for LLM prompt budgeting.
Uses tiktoken for accurate OpenAI-compatible token counts.
"""
import logging
from typing import List

import tiktoken

logger = logging.getLogger(__name__)

# Cache the encoder — loading it is expensive (~100ms)
_encoder: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    """Return a cached cl100k_base encoder (used by GPT-4/4o/4.1)."""
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    """Count the number of tokens in *text* using cl100k_base encoding.

    This is a good approximation for GPT-4, GPT-4o, GPT-4.1, and
    Claude models (within ~5-10 %).
    """
    if not text:
        return 0
    return len(_get_encoder().encode(text))


def batch_texts_by_tokens(
    texts: List[str],
    max_tokens_per_batch: int,
) -> List[List[str]]:
    """Split *texts* into batches where each batch fits within *max_tokens_per_batch*.

    Each text is kept intact (never split mid-text).  If a single text
    exceeds the budget it gets its own batch.

    Args:
        texts: Ordered list of text chunks (e.g., file diffs).
        max_tokens_per_batch: Token budget per batch.

    Returns:
        List of batches, where each batch is a list of texts.
    """
    batches: List[List[str]] = []
    current_batch: List[str] = []
    current_tokens = 0

    for text in texts:
        text_tokens = count_tokens(text)

        if current_batch and current_tokens + text_tokens > max_tokens_per_batch:
            # Flush current batch
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(text)
        current_tokens += text_tokens

    if current_batch:
        batches.append(current_batch)

    return batches
