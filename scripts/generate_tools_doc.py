"""
Generate a markdown document listing all available MCP tools
from GitHub and Atlassian servers.
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.mcp.client import get_mcp_manager
from src.mcp.config import get_config_loader


def format_tool_params(tool) -> str:
    """Extract parameter info from a tool's input schema."""
    schema = getattr(tool, 'inputSchema', None) or getattr(tool, 'input_schema', None)
    if not schema:
        return ""

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    if not properties:
        return ""

    lines = []
    for name, prop in properties.items():
        ptype = prop.get("type", "any")
        desc = prop.get("description", "")
        req = " **(required)**" if name in required else " *(optional)*"
        desc_text = f" — {desc}" if desc else ""
        lines.append(f"  - `{name}` ({ptype}){req}{desc_text}")
    return "\n".join(lines)


def format_server_tools(server_name: str, tools: list) -> str:
    """Format tools from a single server into markdown."""
    lines = [
        f"## {server_name} MCP Server",
        f"",
        f"**Total tools: {len(tools)}**",
        "",
    ]

    # Group tools by category (heuristic based on name)
    categories = {}
    for tool in sorted(tools, key=lambda t: t.name):
        name_lower = tool.name.lower()
        if "pull_request" in name_lower or "pull" in name_lower:
            cat = "Pull Requests"
        elif "issue" in name_lower:
            cat = "Issues"
        elif "branch" in name_lower or "commit" in name_lower or "tag" in name_lower:
            cat = "Branches / Commits / Tags"
        elif "repo" in name_lower:
            cat = "Repositories"
        elif "release" in name_lower:
            cat = "Releases"
        elif "user" in name_lower or "me" in name_lower:
            cat = "Users"
        elif "file" in name_lower or "content" in name_lower:
            cat = "Files & Content"
        elif "jira" in name_lower:
            cat = "Jira"
        elif "confluence" in name_lower:
            cat = "Confluence"
        elif "compass" in name_lower:
            cat = "Compass"
        elif "search" in name_lower:
            cat = "Search"
        elif "code" in name_lower:
            cat = "Code"
        elif "label" in name_lower:
            cat = "Labels"
        elif "team" in name_lower:
            cat = "Teams"
        elif "notification" in name_lower:
            cat = "Notifications"
        elif "copilot" in name_lower:
            cat = "Copilot"
        elif "secret" in name_lower:
            cat = "Security"
        else:
            cat = "Other"

        categories.setdefault(cat, []).append(tool)

    for cat, cat_tools in sorted(categories.items()):
        lines.append(f"### {cat} ({len(cat_tools)})")
        lines.append("")
        for tool in cat_tools:
            desc = getattr(tool, 'description', '') or ''
            # Truncate very long descriptions
            if len(desc) > 200:
                desc = desc[:200].rsplit(' ', 1)[0] + "..."
            lines.append(f"#### `{tool.name}`")
            if desc:
                lines.append(f"> {desc}")
            params = format_tool_params(tool)
            if params:
                lines.append(f"\n**Parameters:**\n{params}")
            lines.append("")

    return "\n".join(lines)


async def main():
    config_loader = get_config_loader()
    config = config_loader.load_mcp_config()
    manager = await get_mcp_manager(config)

    doc_lines = [
        "# MCP Server Tools Reference",
        "",
        f"*Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "This document lists all tools available from the configured MCP servers.",
        "",
        "---",
        "",
    ]

    servers = [
        ("GitHub", "github"),
        ("Atlassian", "atlassian"),
    ]

    for display_name, server_key in servers:
        client = manager.get_client(server_key)
        if client:
            tools = client._available_tools
            print(f"{display_name}: {len(tools)} tools found")
            doc_lines.append(format_server_tools(display_name, tools))
            doc_lines.append("---\n")
        else:
            print(f"{display_name}: server not connected")
            doc_lines.append(f"## {display_name} MCP Server\n")
            doc_lines.append(f"*Server not connected or not configured.*\n")
            doc_lines.append("---\n")

    output_path = Path(__file__).resolve().parent.parent / "MCP_TOOLS.md"
    output_path.write_text("\n".join(doc_lines))
    print(f"\nWritten to {output_path}")

    await manager.disconnect_all()


if __name__ == "__main__":
    asyncio.run(main())
