"""
Markdown formatting utilities.
"""
from typing import List


def escape_markdown(text: str) -> str:
    """
    Escape special markdown characters in text.
    
    Args:
        text: Text to escape
    
    Returns:
        Escaped text
    """
    if not text:
        return ""
    
    # Characters that need escaping in markdown
    special_chars = ['\\', '`', '*', '_', '{', '}', '[', ']', '(', ')', '#', '+', '-', '.', '!', '|']
    
    for char in special_chars:
        text = text.replace(char, '\\' + char)
    
    return text


def format_file_list(files: List[str], max_files: int = 20) -> str:
    """
    Format a list of file paths as markdown list.
    
    Args:
        files: List of file paths
        max_files: Maximum files to show
    
    Returns:
        Formatted markdown string
    """
    if not files:
        return "_No files_"
    
    lines = []
    for i, file in enumerate(files[:max_files]):
        lines.append(f"- `{file}`")
    
    if len(files) > max_files:
        lines.append(f"- _... and {len(files) - max_files} more files_")
    
    return "\n".join(lines)


def format_jira_link(jira_id: str, jira_base_url: str, title: str = "") -> str:
    """
    Format a Jira ticket as markdown link.
    
    Args:
        jira_id: Jira ticket ID
        jira_base_url: Base Jira URL
        title: Optional title for the link
    
    Returns:
        Markdown link
    """
    url = f"{jira_base_url.rstrip('/')}/browse/{jira_id}"
    
    if title:
        return f"[{jira_id}: {title}]({url})"
    else:
        return f"[{jira_id}]({url})"


def format_confluence_link(page_title: str, page_url: str) -> str:
    """
    Format a Confluence page as markdown link.
    
    Args:
        page_title: Page title
        page_url: Page URL
    
    Returns:
        Markdown link
    """
    return f"[{page_title}]({page_url})"


def format_code_block(code: str, language: str = "") -> str:
    """
    Format code as markdown code block.
    
    Args:
        code: Code to format
        language: Optional language identifier
    
    Returns:
        Markdown code block
    """
    return f"```{language}\n{code}\n```"


def format_table_row(columns: List[str]) -> str:
    """
    Format a markdown table row.
    
    Args:
        columns: List of column values
    
    Returns:
        Markdown table row
    """
    return "| " + " | ".join(columns) + " |"


def create_markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    """
    Create a markdown table.
    
    Args:
        headers: List of header column names
        rows: List of rows (each row is a list of column values)
    
    Returns:
        Complete markdown table
    """
    if not headers or not rows:
        return ""
    
    lines = []
    
    # Header row
    lines.append(format_table_row(headers))
    
    # Separator row
    separators = ["-" * max(3, len(h)) for h in headers]
    lines.append(format_table_row(separators))
    
    # Data rows
    for row in rows:
        lines.append(format_table_row(row))
    
    return "\n".join(lines)


def format_badge(label: str, value: str, color: str = "blue") -> str:
    """
    Format a badge (using shields.io style).
    
    Args:
        label: Badge label
        value: Badge value
        color: Badge color
    
    Returns:
        Markdown badge
    """
    url = f"https://img.shields.io/badge/{label}-{value}-{color}"
    return f"![{label}]({url})"


def format_collapsible_section(title: str, content: str) -> str:
    """
    Format a collapsible section (GitHub markdown).
    
    Args:
        title: Section title
        content: Section content
    
    Returns:
        Collapsible markdown section
    """
    return f"""<details>
<summary>{title}</summary>

{content}

</details>"""


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
    
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def format_datetime(dt, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime as string.
    
    Args:
        dt: datetime object
        format_str: Format string
    
    Returns:
        Formatted datetime string
    """
    if dt is None:
        return "N/A"
    
    return dt.strftime(format_str)
