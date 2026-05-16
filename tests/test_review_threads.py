"""Quick smoke test for threaded review templates and build_review_threads."""
from datetime import datetime, timezone
from jinja2 import Template
from src.agent.state import PRReviewComment, ReviewThread
from src.extractors.review_threads import build_review_threads
from templates.prompts import (
    CODING_STANDARDS_PROMPT,
    ARCHITECTURAL_PATTERNS_PROMPT,
    REVIEW_SUMMARY_PROMPT,
)

# ── Test build_review_threads ────────────────────────────────────────────
comments = [
    PRReviewComment(
        id=1, in_reply_to_id=None,
        author="alice", body="Should we add error handling here?",
        path="src/api/handler.ts", line=42, start_line=40,
        diff_hunk="@@ -38,6 +38,8 @@\n+  const result = await fetch(url);",
        subject_type="line", pull_request_review_id=100,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    ),
    PRReviewComment(
        id=2, in_reply_to_id=1,
        author="bob", body="Good point, fixed.",
        path="src/api/handler.ts", line=42,
        diff_hunk="@@ -38,6 +38,8 @@\n+  const result = await fetch(url);",
        subject_type="line", pull_request_review_id=101,
        created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    ),
    PRReviewComment(
        id=3, in_reply_to_id=None,
        author="charlie", body="Overall LGTM",
        path=None, line=None,
        diff_hunk=None, subject_type=None, pull_request_review_id=102,
        created_at=datetime(2024, 1, 3, tzinfo=timezone.utc),
    ),
    PRReviewComment(
        id=4, in_reply_to_id=None,
        author="alice", body="Consider using a constant here",
        path="src/config.ts", line=10,
        diff_hunk="@@ -8,4 +8,6 @@\n+const TIMEOUT = 5000;",
        subject_type="line", pull_request_review_id=103,
        created_at=datetime(2024, 1, 4, tzinfo=timezone.utc),
    ),
]

threads = build_review_threads(comments)
print(f"Built {len(threads)} threads from {len(comments)} comments")
for t in threads:
    resolved_tag = " [RESOLVED]" if t.is_resolved else ""
    loc = f"{t.file_path} L{t.line_range}" if t.file_path else "General"
    print(f"  Thread: {loc}{resolved_tag} ({len(t.comments)} comments)")
    for c in t.comments:
        print(f"    - {c.author}: {c.body[:50]}")

assert len(threads) == 3, f"Expected 3 threads, got {len(threads)}"
# Thread 1: alice+bob on handler.ts (resolved because "fixed")
assert threads[0].file_path == "src/api/handler.ts"
assert threads[0].is_resolved is True
assert len(threads[0].comments) == 2
# Thread 2: alice on config.ts
assert threads[1].file_path == "src/config.ts"
# Thread 3: charlie general
assert threads[2].file_path is None

# ── Test template rendering ──────────────────────────────────────────────
for name, tmpl_str in [
    ("CODING_STANDARDS", CODING_STANDARDS_PROMPT),
    ("ARCHITECTURAL", ARCHITECTURAL_PATTERNS_PROMPT),
    ("REVIEW_SUMMARY", REVIEW_SUMMARY_PROMPT),
]:
    t = Template(tmpl_str)
    rendered = t.render(
        pr_title="Test PR",
        review_threads=threads,
        file_changes=[{"path": "a.ts", "additions": 5, "deletions": 2}],
        file_stats={},
        grouped_files={},
        jira_context=[],
    )
    assert "src/api/handler.ts" in rendered, f"{name}: missing file path"
    assert "alice" in rendered, f"{name}: missing author"
    assert "diff" in rendered, f"{name}: missing diff hunk"
    print(f"{name} template: OK ({len(rendered)} chars)")

print("\nAll checks passed!")
