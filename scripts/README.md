# Debug & Testing Scripts

This directory contains utility scripts for testing and debugging MCP integrations.

## Scripts

### MCP Testing

- **`check_tools.py`** - Verify MCP server connections and list available tools
- **`list_atlassian_tools.py`** - Enumerate all Atlassian MCP tools (Jira, Confluence)
- **`test_github_tool.py`** - Test GitHub MCP tool functionality
- **`test_jira.py`** - Test Jira MCP integration (basic)
- **`test_jira_simple.py`** - Test Jira MCP integration with detailed output and clean error handling

## Usage

Run from the project root:

```bash
# Test MCP connections
python3 -m scripts.check_tools

# List Atlassian tools
python3 -m scripts.list_atlassian_tools

# Test Jira integration
python3 -m scripts.test_jira_simple
```

## Note

These are debugging utilities, not unit tests. For unit tests, see the `tests/` directory.
