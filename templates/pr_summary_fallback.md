# PR Summary: {{ pr_title }}

**PR Number:** #{{ pr_number }}  
**Author:** {{ pr_author }}  
**Merged:** {{ merge_date }}  
**Branch:** `{{ source_branch }}` → `{{ target_branch }}`

---

## 📋 Summary

{{ ai_summary }}

---

## 📝 Changes Overview

### Files Modified

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

---

## 🔗 Links

- [View Pull Request on GitHub]({{ pr_url }})

---

## 📊 Technical Details

**PR Description:**

{{ pr_description }}

---

_Generated on {{ generation_date }} by PR Summary Agent_

_Note: Limited context available - no Jira tickets, Figma designs, or Confluence pages were found for this PR._
