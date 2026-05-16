"""Tests for src/utils/tokens.py — token counting and batch splitting."""
import pytest
from src.utils.tokens import count_tokens, batch_texts_by_tokens


def test_count_tokens_empty():
    assert count_tokens("") == 0
    assert count_tokens(None) == 0


def test_count_tokens_basic():
    # "hello world" should be a small positive number
    tokens = count_tokens("hello world")
    assert 1 <= tokens <= 5


def test_count_tokens_longer_text():
    text = "The quick brown fox jumps over the lazy dog. " * 10
    tokens = count_tokens(text)
    assert tokens > 50


def test_batch_texts_single_batch():
    """All texts fit in one batch."""
    texts = ["short", "also short", "yep"]
    batches = batch_texts_by_tokens(texts, max_tokens_per_batch=1000)
    assert len(batches) == 1
    assert batches[0] == texts


def test_batch_texts_each_exceeds_budget():
    """Each text exceeds the budget — each gets its own batch."""
    big = "word " * 200  # ~200 tokens
    texts = [big, big, big]
    batches = batch_texts_by_tokens(texts, max_tokens_per_batch=50)
    assert len(batches) == 3
    for batch in batches:
        assert len(batch) == 1


def test_batch_texts_mixed_sizes():
    """Mix of small and large texts — small ones are grouped together."""
    small = "hi"
    big = "word " * 300  # ~300 tokens
    texts = [small, small, small, big, small, small]
    batches = batch_texts_by_tokens(texts, max_tokens_per_batch=100)
    # First 3 "hi" fit in one batch (<100 tokens), big gets its own,
    # last 2 "hi" fit in one batch
    assert len(batches) == 3
    assert len(batches[0]) == 3  # three "hi"s
    assert len(batches[1]) == 1  # the big text
    assert len(batches[2]) == 2  # two "hi"s


def test_batch_texts_empty_input():
    batches = batch_texts_by_tokens([], max_tokens_per_batch=1000)
    assert batches == []


def test_batch_texts_preserves_order():
    texts = [f"text_{i}" for i in range(10)]
    batches = batch_texts_by_tokens(texts, max_tokens_per_batch=10000)
    flattened = [t for batch in batches for t in batch]
    assert flattened == texts
