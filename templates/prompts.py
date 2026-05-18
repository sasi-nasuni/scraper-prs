"""
LLM prompt templates for PR summarization.
These prompts guide the LLM in generating structured summaries.
"""

# System prompt for the PR summarization agent
SYSTEM_PROMPT = """You are a technical documentation expert specializing in software engineering.
Your task is to analyze pull request data and generate clear, concise summaries that help developers 
and stakeholders understand the changes, context, and impact of code modifications.

Focus on:
- High-level overview of what changed and why
- Business value and technical impact
- Important technical details that reviewers and future maintainers should know
- Potential risks or areas requiring attention

Be concise but thorough. Use technical terminology appropriately. Highlight breaking changes prominently."""


# ── Diff batch summarization prompt ──────────────────────────────────────────

DIFF_BATCH_SUMMARY_PROMPT = """You are summarizing code diffs for the **{{ category }}** area of a pull request.

{% if previous_summary %}
**Summary of changes analysed so far:**
{{ previous_summary }}

The following are ADDITIONAL diffs in the same category that have not yet been summarised.
Incorporate the previous summary and the new diffs below into a single, cohesive summary.
{% else %}
This is the first batch of diffs for this category.
{% endif %}

**Files in this batch:**
{% for diff in diffs %}
---
**{{ diff.path }}** ({{ diff.status }}, +{{ diff.additions }}/-{{ diff.deletions }})
```diff
{{ diff.patch }}
```
{% endfor %}

Produce a concise technical summary (2-4 paragraphs) of what these changes accomplish.
Focus on:
- What is being changed at a functional / logical level (not line-by-line narration)
- New components, functions, types, APIs, or hooks introduced
- Refactoring patterns (renames, extractions, consolidations)
- Configuration or dependency changes and their purpose
- Anything that looks like a bug fix, migration, or behaviour change

Do NOT list files one-by-one.  Synthesize across files to describe the overall intent.

Summary:"""


# ── Confluence page summarization prompt ─────────────────────────────────────

CONFLUENCE_PAGE_SUMMARY_PROMPT = """Summarize the following Confluence page content.
Focus on information that would help a developer understand requirements, design decisions,
or context for a code change.

**Page Title:** {{ page_title }}
{% if page_url %}**URL:** {{ page_url }}{% endif %}

**Page Content:**
{{ page_body }}

Produce a concise summary (2-4 paragraphs) highlighting:
- Key requirements or acceptance criteria
- Design decisions, architectural context, or technical constraints
- Process or workflow information relevant to implementation
- Any diagrams, mockups, or specifications described

Omit boilerplate, navigation text, page metadata, and formatting artifacts.

Summary:"""


# ── Main PR summary prompt (multi-source fusion) ────────────────────────────

PR_SUMMARY_PROMPT = """Based on ALL the following knowledge sources, generate a comprehensive summary
of the changes in this pull request. Synthesize information across sources — do not just repeat
each source verbatim.

## 1. PR Metadata

**PR Title:** {{ pr_title }}

**PR Description:**
{{ pr_description }}

## 2. Business Context

{% if jira_context %}
**Related Jira Ticket(s):**
{% for ticket in jira_context %}
- **{{ ticket.key }}**: {{ ticket.title }} ({{ ticket.ticket_type }} · {{ ticket.status }})
{% if ticket.description %}
  Description: {{ ticket.description }}
{% endif %}
{% if ticket.acceptance_criteria %}
  Acceptance Criteria: {{ ticket.acceptance_criteria }}
{% endif %}
{% endfor %}
{% else %}
No linked Jira tickets.
{% endif %}

## 3. Design & Documentation Context

{% if confluence_pages %}
**Related Confluence Pages:**
{% for page in confluence_pages %}
### [{{ page.title }}]({{ page.url }}){% if page.space_name %} ({{ page.space_name }}){% endif %}

{% if page.content_summary %}
{{ page.content_summary }}
{% elif page.body %}
{{ page.body }}
{% elif page.excerpt %}
{{ page.excerpt }}
{% endif %}

{% endfor %}
{% endif %}

{% if figma_files %}
**Related Figma Designs:**
{% for file in figma_files %}
- [{{ file.name }}]({{ file.url }})
{% endfor %}
{% endif %}

{% if not confluence_pages and not figma_files %}
No related design or documentation pages found.
{% endif %}

## 4. Code Changes

{% if diff_summaries %}
{% for category, summary in diff_summaries.items() %}
**{{ category | capitalize }} changes:**
{{ summary }}

{% endfor %}
{% else %}
**Files Changed ({{ file_changes | length }} files):**
{% for file in file_changes %}
- {{ file.path }}: +{{ file.additions }}/-{{ file.deletions }}
{% endfor %}
{% endif %}

{% if skipped_files %}
**Also touched (diffs not analysed):** {{ skipped_files | join(', ') }}
{% endif %}

---

Generate a 3-5 paragraph summary that:
1. Explains what this PR accomplishes (the "what" and "why"), grounding in business context when available
2. Highlights the key technical changes — reference specific components, APIs, or patterns
3. Notes any design/documentation context that informed the changes
4. Calls out important considerations, breaking changes, or impacts
5. Mentions testing approach if evident from the diffs

Summary:"""


# ── Review thread condensation prompt ────────────────────────────────────────

REVIEW_THREADS_CONDENSE_PROMPT = """Condense the following PR review conversations into concise summaries.
For each conversation, preserve:
- **Who** said what (reviewer/author attribution)
- **Where** (file path and line numbers)
- **What code** was being discussed (the essence, not the full diff)
- **What was suggested** and the **outcome** (accepted, rejected, deferred)

{% for thread in threads %}
---
{% if thread.file_path %}📁 **{{ thread.file_path }}**{% if thread.line_range %} (L{{ thread.line_range }}){% endif %}{% else %}💬 **General Discussion**{% endif %}
{% if thread.diff_hunk %}
```diff
{{ thread.diff_hunk }}
```
{% endif %}
{% for comment in thread.comments %}
> **{{ comment.author }}** ({{ comment.created_at.strftime('%Y-%m-%d') }}):
> {{ comment.body }}
{% endfor %}
{% endfor %}

Produce a numbered list — one entry per conversation thread. Each entry should be 1-3 sentences capturing the file, reviewer, what was discussed, and the outcome. Keep technical detail but remove verbosity.

Condensed Review Threads:"""


# Prompt for identifying coding standards and patterns from reviews
CODING_STANDARDS_PROMPT = """Analyze the review comments and code changes to extract **general, reusable coding standards** that apply to any future work in this repository — not just this PR.

IMPORTANT: Do NOT describe what this PR does or what was changed in it. Instead, derive universal rules and guidelines that a new developer should follow when writing code in this codebase. Write each guideline as a timeless directive (e.g. "Always ...", "Never ...", "Prefer ...", "Use ... when ...").

**PR Title:** {{ pr_title }}

{% if review_threads_summary %}
**Review Conversations (condensed):**
{{ review_threads_summary }}
{% elif review_threads %}
**Review Conversations:**
{% for thread in review_threads %}
---
{% if thread.file_path %}📁 **{{ thread.file_path }}**{% if thread.line_range %} (L{{ thread.line_range }}){% endif %}{% else %}💬 **General Discussion**{% endif %}
{% if thread.diff_hunk %}
```diff
{{ thread.diff_hunk }}
```
{% endif %}
{% for comment in thread.comments %}
> **{{ comment.author }}** ({{ comment.created_at.strftime('%Y-%m-%d') }}):
> {{ comment.body }}
{% endfor %}
{% endfor %}
{% endif %}

{% if file_changes %}
**Modified Files:**
{% for file in file_changes[:15] %}
- {{ file.path }}: +{{ file.additions }}/-{{ file.deletions }}
{% endfor %}
{% endif %}

Extract coding standards as **generic, reusable rules** for this repository. For each standard:
1. **Category**: Classify by area (Frontend, Backend, Testing, ESLint/Linting Rules, Database, Infrastructure, Documentation, General)
2. **Guideline**: A clear, imperative directive that applies broadly (not just to this PR)
3. **Enforced by**: Who raised this standard
4. **Rationale**: Why this matters (one sentence)

Organize your response by category:

**Frontend Coding Guidelines:**
- [Imperative guideline] — enforced by [Reviewer]: [Rationale]

**Backend Coding Guidelines:**
- [Imperative guideline] — enforced by [Reviewer]: [Rationale]

**Testing Standards:**
- [Imperative guideline] — enforced by [Reviewer]: [Rationale]

**ESLint/Linting Rules:**
- [Imperative guideline] — enforced by [Reviewer]: [Rationale]

**General Best Practices:**
- [Imperative guideline] — enforced by [Reviewer]: [Rationale]

Rules for writing guidelines:
- Write each as a generic, reusable rule ("Always use ...", "Never commit ...", "Prefer X over Y")
- Do NOT mention specific PR files, variable names, or implementation details from this PR
- Do NOT summarize what was done in this PR — only extract the underlying standard
- If a reviewer says "rename this to X", the guideline is the naming convention, not the specific rename
- Only include categories where standards were actually discussed

If no generalizable standards are evident, respond with "No explicit coding standards discussed in review."

Coding Standards:"""


# Prompt for identifying breaking changes
BREAKING_CHANGES_PROMPT = """Review the following PR information and identify any breaking changes.

**PR Title:** {{ pr_title }}
**PR Description:** {{ pr_description }}

{% if file_changes %}
**Modified Files:**
{% for file in file_changes %}
- {{ file.path }}
{% endfor %}
{% endif %}

Look for:
- API changes (endpoint modifications, parameter changes, response format changes)
- Database schema changes
- Removed or renamed functions/classes
- Configuration changes requiring updates
- Dependency version bumps with breaking changes

If breaking changes are found, list them clearly with migration guidance.
If no breaking changes are detected, respond with "None detected."

Breaking Changes:"""


# Prompt for identifying architectural patterns
ARCHITECTURAL_PATTERNS_PROMPT = """From this pull request's code and review discussions, extract **general architectural guidelines and design principles** that apply to the entire repository — not just this PR.

IMPORTANT: Do NOT describe what this specific PR implements. Instead, derive reusable architectural rules that any developer should follow when building features in this codebase. Write each as a prescriptive guideline (e.g. "Use the Repository pattern for ...", "Separate concerns by ...", "New services should ...").

**PR Title:** {{ pr_title }}

**Files Changed:**
{% for category, stats in file_stats.items() %}
- {{ category }}: {{ stats.count }} files ({{ stats.additions }} additions, {{ stats.deletions }} deletions)
{% endfor %}

{% if grouped_files %}
**All Files by Category:**
{% for category, files in grouped_files.items() %}
*{{ category | capitalize }}:*
{% for file in files %}
- {{ file.path }} (+{{ file.additions }}/-{{ file.deletions }})
{% endfor %}
{% endfor %}
{% endif %}

{% if review_threads_summary %}
**Review Conversations (condensed):**
{{ review_threads_summary }}
{% elif review_threads %}
**Review Conversations:**
{% for thread in review_threads %}
---
{% if thread.file_path %}📁 **{{ thread.file_path }}**{% if thread.line_range %} (L{{ thread.line_range }}){% endif %}{% else %}💬 **General Discussion**{% endif %}
{% if thread.diff_hunk %}
```diff
{{ thread.diff_hunk }}
```
{% endif %}
{% for comment in thread.comments %}
> **{{ comment.author }}** ({{ comment.created_at.strftime('%Y-%m-%d') }}):
> {{ comment.body }}
{% endfor %}
{% endfor %}
{% endif %}

{% if jira_context %}
**Jira Context:**
{% for ticket in jira_context %}
- {{ ticket.key }}: {{ ticket.title }}
{% endfor %}
{% endif %}

Extract architectural guidelines as **generic, reusable principles** for this repository, organized by layer:

**Frontend Architecture Guidelines:**
- Component structure, state management, routing conventions to follow

**Backend Architecture Guidelines:**
- API design conventions, service layer patterns, error handling approaches

**Testing Architecture Guidelines:**
- Test organization rules, mocking strategies, coverage expectations

**Infrastructure/DevOps Guidelines:**
- Deployment conventions, configuration management rules

**Data Layer Guidelines:**
- Database access patterns, migration conventions, data modeling rules

**Integration Guidelines:**
- Service communication patterns (REST, events, queues), contract conventions

For each guideline:
- Write as a prescriptive rule for future development ("Always ...", "Use ... for ...", "New X should ...")
- Note the design pattern if applicable (Repository, Factory, Observer, Strategy, MVC, etc.)
- Attribute to the reviewer who enforced it, if applicable

Rules for writing guidelines:
- Write each as a generic, reusable directive — not a description of this PR
- Do NOT mention specific features, tickets, or implementations from this PR
- Focus on the underlying principle, not the specific instance
- Only include categories where clear architectural conventions are evident

If no clear architectural guidelines are evident, respond with "No distinctive architectural guidelines observed."

Architectural Guidelines:"""


# Prompt for summarizing review comments with focus on standards and patterns
REVIEW_SUMMARY_PROMPT = """Summarize the key points and decisions from these PR review comments, with emphasis on coding standards and patterns. Attribute each point to the reviewer who raised it.

{% if review_threads_summary %}
{{ review_threads_summary }}
{% elif review_threads %}
{% for thread in review_threads %}
---
{% if thread.file_path %}📁 **{{ thread.file_path }}**{% if thread.line_range %} (L{{ thread.line_range }}){% endif %}{% else %}💬 **General Discussion**{% endif %}
{% if thread.diff_hunk %}
```diff
{{ thread.diff_hunk }}
```
{% endif %}
{% for comment in thread.comments %}
> **{{ comment.author }}** ({{ comment.created_at.strftime('%Y-%m-%d') }}):
> {{ comment.body }}
{% endfor %}
{% endfor %}
{% else %}
No review comments available.
{% endif %}

Organize feedback by category, attributing each point to the reviewer:

**Coding Standards Enforced:**
- [Standard/practice] - emphasized by [Reviewer]: [Brief context]

**Technical Decisions:**
- [Decision] - discussed by [Reviewer(s)]: [Outcome/rationale]

**Patterns & Best Practices:**
- [Pattern/practice] - recommended by [Reviewer]: [Why/context]

**Concerns & Resolutions:**
- [Concern] - raised by [Reviewer]: [How resolved or status]

**Follow-up Actions:**
- [Action item] - suggested by [Reviewer]: [Details]

For each category:
- Group related feedback together
- Show consensus when multiple reviewers emphasized the same point
- Note specific files/areas when mentioned
- Identify whether issues were resolved during review

Focus on technical substance and team learning opportunities. Omit:
- Minor formatting/typo corrections
- Simple "LGTM" without context
- Repetitive comments

If there were no significant discussions, respond with "Straightforward approval with no major discussions."

Review Summary:"""
