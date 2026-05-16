# PR Summary: {{ pr_title }}

**PR Number:** #{{ pr_number }}  
**Author:** {{ pr_author }}  
**Merged:** {{ merge_date }}  
**Branch:** `{{ source_branch }}` → `{{ target_branch }}`

---

## 📋 Summary

{{ ai_summary }}

---

## 🎫 Jira Context

{% if jira_tickets %}
{% for ticket in jira_tickets %}
### {{ ticket.key }}: {{ ticket.title }}

- **Status:** {{ ticket.status }}
- **Priority:** {{ ticket.priority }}
- **Type:** {{ ticket.ticket_type }}
{% if ticket.epic %}
- **Epic:** {{ ticket.epic }}
{% endif %}
{% if ticket.assignee %}
- **Assignee:** {{ ticket.assignee }}
{% endif %}

**Description:**
{{ ticket.description  | truncate(500) if ticket.description else "No description provided" }}

🔗 [View in Jira]({{ ticket.url }})

{% endfor %}
{% else %}
_No Jira tickets found for this PR._
{% endif %}

---

## 📝 Changes Overview

### Files Modified

{% if file_stats %}
| Category | Files Changed | Lines Added | Lines Deleted |
|----------|--------------|-------------|---------------|
| Backend | {{ file_stats.backend.count }} | +{{ file_stats.backend.additions }} | -{{ file_stats.backend.deletions }} |
| Frontend | {{ file_stats.frontend.count }} | +{{ file_stats.frontend.additions }} | -{{ file_stats.frontend.deletions }} |
| Tests | {{ file_stats.tests.count }} | +{{ file_stats.tests.additions }} | -{{ file_stats.tests.deletions }} |
| Config | {{ file_stats.config.count }} | +{{ file_stats.config.additions }} | -{{ file_stats.config.deletions }} |
| Documentation | {{ file_stats.docs.count }} | +{{ file_stats.docs.additions }} | -{{ file_stats.docs.deletions }} |
| Other | {{ file_stats.other.count }} | +{{ file_stats.other.additions }} | -{{ file_stats.other.deletions }} |
{% endif %}

**Total:** {{ total_files }} files changed, +{{ total_additions }} / -{{ total_deletions }} lines

{% if grouped_files %}
### Files Changed
{% for category, files in grouped_files.items() %}

#### {{ category | capitalize }} ({{ files | length }} files)

| File | Status | Lines |
|------|--------|-------|
{% for file in files %}
| [{{ file.path }}]({{ file_diff_urls[file.path] }}) | {{ file.status }} | +{{ file.additions }} / -{{ file.deletions }} |
{% endfor %}
{% endfor %}
{% endif %}

{% if breaking_changes %}
### ⚠️ Breaking Changes

{{ breaking_changes }}
{% endif %}

---

## 🎨 Figma Designs

{% if figma_files %}
{% for figma in figma_files %}
### {{ figma.name }}

{% if figma.thumbnail_url %}
![Design Preview]({{ figma.thumbnail_url }})
{% endif %}

🔗 [Open in Figma]({{ figma.url }})

{% if figma.last_modified %}
_Last modified: {{ figma.last_modified }}_
{% endif %}

{% endfor %}
{% else %}
_No Figma designs linked to this PR._
{% endif %}

---

## 📚 Confluence Documentation

{% if confluence_pages %}
{% for page in confluence_pages %}
### {{ page.title }}

{{ page.excerpt | truncate(200) }}

🔗 [Read more]({{ page.url }})

{% endfor %}
{% else %}
_No related Confluence pages found._
{% endif %}

---

## 👥 Code Review & Standards

- **Reviewers:** {{ reviewers | join(", ") }}
- **Approvals:** {{ approvals_count }}
- **Review Comments:** {{ review_comments_count }}

{% if coding_standards %}
### Coding Standards & Patterns Identified

{{ coding_standards }}
{% endif %}

{% if review_summary %}
### Key Review Insights

{{ review_summary }}
{% endif %}

{% if architectural_patterns %}
### Architectural Patterns

{{ architectural_patterns }}
{% endif %}

---

## 🔗 Links

- [View Pull Request on GitHub]({{ pr_url }})
{% if jira_tickets %}
{% for ticket in jira_tickets %}
- [{{ ticket.key }} - {{ ticket.title }}]({{ ticket.url }})
{% endfor %}
{% endif %}
{% if confluence_pages %}
{% for page in confluence_pages %}
- [{{ page.title }} (Confluence)]({{ page.url }})
{% endfor %}
{% endif %}
{% if figma_files %}
{% for figma in figma_files %}
- [{{ figma.name }} (Figma)]({{ figma.url }})
{% endfor %}
{% endif %}

---

_Generated on {{ generation_date }} by PR Summary Agent_
