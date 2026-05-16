# Atlassian MCP Server Integration

This document explains how the Atlassian MCP (Model Context Protocol) server is integrated into the PR Summary Agent to fetch Jira tickets and Confluence pages.

---

## Architecture Overview

```
Agent Nodes  →  JiraTools / ConfluenceTools  →  MCPClientManager  →  Atlassian MCP Server (subprocess)
```

The agent communicates with Atlassian (Jira + Confluence) through the **official Atlassian Rovo MCP endpoint**, using the MCP protocol over stdio.

---

## 1. Server Configuration

**File:** `config/mcp_servers.json`

```json
"atlassian": {
  "command": "npx",
  "args": ["-y", "mcp-remote@latest", "https://mcp.atlassian.com/v1/mcp"],
  "env": {
    "ATLASSIAN_CLOUD_ID": "${ATLASSIAN_CLOUD_ID}",
    "ATLASSIAN_EMAIL": "${JIRA_EMAIL}",
    "ATLASSIAN_API_TOKEN": "${JIRA_API_TOKEN}"
  },
  "description": "Official Atlassian Rovo MCP Server (OAuth auth - authenticate once via browser)"
}
```

### How it works:
- Uses [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) as a bridge/proxy
- Connects to the official Atlassian MCP endpoint at `https://mcp.atlassian.com/v1/mcp`
- Authentication is OAuth-based — first run requires browser-based auth, then tokens are cached

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `ATLASSIAN_CLOUD_ID` | Your Atlassian Cloud instance ID (found in admin settings) |
| `JIRA_EMAIL` | Atlassian account email |
| `JIRA_API_TOKEN` | Atlassian API token ([generate here](https://id.atlassian.com/manage-profile/security/api-tokens)) |

---

## 2. Connection Layer

**File:** `src/mcp/client.py`

The `MCPClientManager` handles spawning and managing the MCP server process:

1. **Spawns the process** — runs `npx mcp-remote@latest https://mcp.atlassian.com/v1/mcp` as a child process
2. **Communicates via stdio** — stdin/stdout streams using the MCP protocol
3. **Creates a `ClientSession`** — the MCP SDK session that handles request/response framing
4. **Discovers available tools** — calls `session.list_tools()` to enumerate what the server exposes

```python
# Connection flow (simplified)
server_params = StdioServerParameters(
    command="npx",
    args=["-y", "mcp-remote@latest", "https://mcp.atlassian.com/v1/mcp"],
    env={"ATLASSIAN_CLOUD_ID": "...", ...}
)
read_stream, write_stream = await stdio_client(server_params)
session = ClientSession(read_stream, write_stream)
await session.initialize()
tools = await session.list_tools()
```

All MCP servers (GitHub, Atlassian, Figma) are connected concurrently at startup.

---

## 3. Tool Wrappers

**File:** `src/agent/tools.py`

Two classes wrap the raw MCP calls with retry logic, rate limiting, and response parsing:

### JiraTools

Uses the MCP tool `"getJiraIssue"`:

```python
class JiraTools:
    server_name = "atlassian"

    async def get_issue(self, issue_key: str) -> Optional[JiraTicket]:
        result = await self.mcp_manager.call_tool(
            "atlassian",
            "getJiraIssue",
            {
                "cloudId": self.cloud_id,
                "issueIdOrKey": issue_key,
                "responseContentFormat": "markdown",
            }
        )
        # Parses JSON response into JiraTicket dataclass
```

### ConfluenceTools

Uses the MCP tools `"searchConfluenceUsingCql"` and `"getConfluencePage"`:

```python
class ConfluenceTools:
    server_name = "atlassian"

    async def search_pages(self, query: str, max_results: int) -> List[ConfluencePage]:
        result = await self.mcp_manager.call_tool(
            "atlassian",
            "searchConfluenceUsingCql",
            {
                "cloudId": self.cloud_id,
                "cql": query,
                "limit": max_results,
            }
        )

    async def get_page(self, page_id: str) -> Optional[str]:
        result = await self.mcp_manager.call_tool(
            "atlassian",
            "getConfluencePage",
            {
                "cloudId": self.cloud_id,
                "pageId": page_id,
                "contentFormat": "markdown",
            }
        )
```

### Built-in resilience:
- **Retry** — exponential backoff (configurable max attempts, delays)
- **Rate limiting** — per-service rate limiters to avoid API throttling
- **Error handling** — graceful fallback on failures (continues processing other PRs)

---

## 4. Usage in the Agent Graph

**File:** `src/agent/nodes.py`

The LangGraph agent nodes use these tools in sequence:

### Initialization
```python
self.jira_tools = JiraTools(mcp_manager, jira_url, cloud_id, config)
self.confluence_tools = ConfluenceTools(mcp_manager, cloud_id, config)
```

### Data Flow (per PR)

| Step | Node | Action |
|------|------|--------|
| 1 | `extract_references` | Extracts Jira IDs (e.g., `PROJ-123`) from PR title, body, and commit messages |
| 2 | `fetch_jira_context` | Calls `JiraTools.get_issue()` for each Jira ID |
| 3 | `enrich_references_from_jira` | Scans Jira ticket descriptions for Confluence/Figma URLs |
| 4 | `fetch_confluence_context` | Searches Confluence using CQL, scores relevance, fetches full page bodies |
| 5 | `generate_summary` | Includes all Jira + Confluence context in the LLM prompt |

---

## 5. Available Atlassian MCP Tools

The Atlassian MCP server exposes these tools (among others):

| Tool Name | Purpose |
|-----------|---------|
| `getJiraIssue` | Fetch a single Jira issue by key |
| `searchConfluenceUsingCql` | Search Confluence pages using CQL queries |
| `getConfluencePage` | Fetch the full body of a Confluence page |
| `getConfluenceSpaces` | List available Confluence spaces |
| `getVisibleJiraProjects` | List accessible Jira projects |

---

## 6. Setup Instructions

### Prerequisites
- Node.js (for `npx`)
- An Atlassian Cloud account with API access

### Steps

1. **Get your Cloud ID:**
   - Go to `https://your-domain.atlassian.net/_edge/tenant_info`
   - Copy the `cloudId` value

2. **Generate an API token:**
   - Visit https://id.atlassian.com/manage-profile/security/api-tokens
   - Create a new token

3. **Configure environment variables** in your `.env` file:
   ```bash
   ATLASSIAN_CLOUD_ID=your-cloud-id-here
   JIRA_EMAIL=your.email@company.com
   JIRA_API_TOKEN=your-api-token-here
   JIRA_URL=https://your-domain.atlassian.net
   ```

4. **First run — OAuth authentication:**
   - On first connection, `mcp-remote` will open a browser for OAuth consent
   - Authorize the app — tokens are cached for subsequent runs

5. **Verify connection:**
   ```bash
   python -m src.mcp.client  # or run the agent — logs will show "Connected to atlassian"
   ```

---

## 7. Troubleshooting

| Issue | Solution |
|-------|----------|
| `Failed to connect to MCP server atlassian` | Check that `npx` is available and env vars are set |
| `Jira issue not found` | Verify the Cloud ID matches your Atlassian instance |
| Empty Confluence search results | Check that the account has read access to the target spaces |
| OAuth token expired | Delete cached tokens and re-authenticate via browser |
| Rate limiting errors | Adjust `retry` and `rate_limit` settings in `config/agent_config.yaml` |

---

## Configuration Reference

In `config/agent_config.yaml`:

```yaml
# Jira extraction settings
extraction:
  jira:
    pattern: "[A-Z]+-\\d+"  # Regex for Jira ticket IDs
    acceptance_criteria_field: "customfield_10001"  # Optional custom field
  confluence:
    max_pages_per_pr: 3
    max_body_tokens: 3000

# Retry and rate limiting
retry:
  max_attempts: 3
  initial_delay: 1
  max_delay: 30
  exponential_base: 2

rate_limits:
  jira:
    requests_per_second: 2
  confluence:
    requests_per_second: 2
```
