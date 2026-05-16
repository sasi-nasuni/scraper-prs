#!/usr/bin/env python3
"""Analyze comment threading patterns in PR review comments."""
import json
from collections import defaultdict
from pathlib import Path

# Load comments
output_dir = Path(__file__).parent.parent / "outputs" / "pr_1449_responses"
with open(output_dir / "get_pull_request_comments.json") as f:
    comments = json.load(f)

print("=== Comment Threading Analysis ===\n")
print(f"Total comments: {len(comments)}\n")

# Group by review
by_review = defaultdict(list)
for c in comments:
    by_review[c['pull_request_review_id']].append(c)

print(f"Number of reviews with comments: {len(by_review)}\n")

# Group by file and position
by_location = defaultdict(list)
for c in comments:
    if c.get('position'):
        key = (c['path'], c['position'])
        by_location[key].append(c)

print(f"Number of unique code locations with comments: {len(by_location)}\n")

# Find locations with multiple comments (likely conversations)
conversations = {k: v for k, v in by_location.items() if len(v) > 1}
print(f"Code locations with multiple comments (conversations): {len(conversations)}\n")

if conversations:
    print("=== Sample Conversation Threads ===\n")
    for i, ((path, pos), thread) in enumerate(list(conversations.items())[:3], 1):
        print(f"{i}. {path.split('/')[-1]} (position {pos}) - {len(thread)} comments:")
        for c in sorted(thread, key=lambda x: x['created_at']):
            author = c['user']['login']
            timestamp = c['created_at']
            body_preview = c['body'][:100].replace('\n', ' ')
            print(f"   [{timestamp}] {author}: {body_preview}...")
        print()

# Group by review to show review conversations
print("=== Comments by Review ===\n")
for review_id, review_comments in sorted(by_review.items(), key=lambda x: len(x[1]), reverse=True)[:3]:
    print(f"Review {review_id}: {len(review_comments)} comments")
    for c in review_comments[:2]:
        author = c['user']['login']
        body_preview = c['body'][:80].replace('\n', ' ')
        print(f"  - {author}: {body_preview}...")
    if len(review_comments) > 2:
        print(f"  ... and {len(review_comments) - 2} more")
    print()

# Show available fields
print("\n=== Available Fields ===")
print(f"Fields: {', '.join(comments[0].keys())}")
print("\n=== Key fields for threading ===")
print("  • pull_request_review_id: Groups comments from same review")
print("  • path + position: Groups comments on same line of code")  
print("  • created_at: Temporal ordering for conversations")
print("  • user: Identify comment authors")
print("  • body: Comment text content")
print("\n⚠️  Limitation: GitHub REST API doesn't expose direct reply relationships.")
print("    Comments shown here are grouped by location/review, not true threaded replies.")
print("    To get actual reply chains, would need:")
print("      - GraphQL API (has reply_to field)")
print("      - Or individual GET /repos/.../pulls/comments/{id} calls")
