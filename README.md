# PR Summary Agent

A LangGraph-based agent that automatically generates comprehensive summaries for GitHub Pull Requests by enriching them with context from Jira, Confluence, and Figma using MCP (Model Context Protocol) servers.

## Features

- 🔍 **Automated PR Discovery**: Fetches the 5 most recent merged PRs from any GitHub repository
- 📋 **Multi-Source Context**: Enriches PR summaries with:
  - Jira ticket details (status, description, acceptance criteria)
  - Confluence documentation pages
  - Figma design files
  - GitHub PR metadata, commits, reviews, and file changes
- 🤖 **AI-Powered Summaries**: Uses LLMs (OpenAI/Anthropic) to generate intelligent summaries
- 📊 **Impact Analysis**: Automatically analyzes file changes and identifies potential breaking changes
- 📝 **Template-Driven**: Customizable Jinja2 templates for consistent documentation
- 🔄 **LangGraph Workflow**: Robust stateful agent with error handling and retry logic
- 🎯 **Individual Summaries**: Generates separate markdown files for each PR

## Architecture

```
┌─────────────────┐
│  GitHub Repo    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              PR Summary Agent (LangGraph)               │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  GitHub  │  │   Jira   │  │Confluence│  │ Figma  │ │
│  │   MCP    │  │   MCP    │  │   MCP    │  │  MCP   │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
│       │             │             │             │      │
│       └─────────────┴─────────────┴─────────────┘      │
│                        │                               │
│                        ▼                               │
│            ┌──────────────────────┐                    │
│            │  Context Aggregation │                    │
│            └──────────────────────┘                    │
│                        │                               │
│                        ▼                               │
│            ┌──────────────────────┐                    │
│            │   LLM Summarization  │                    │
│            └──────────────────────┘                    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
           ┌────────────────────┐
           │  Markdown Summaries│
           │  (outputs/*.md)    │
           └────────────────────┘
```

## Installation

### Prerequisites

- Python 3.11 or higher
- Node.js (for MCP servers)
- API tokens for:
  - GitHub Personal Access Token
  - Jira API Token
  - Confluence API Token
  - Figma API Token

### Setup

1. **Clone the repository**:
   ```bash
   cd scraper-prs
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -e .
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your API tokens:
   ```bash
   # LLM Configuration
   OPENAI_API_KEY=sk-...
   LLM_MODEL=gpt-4o
   
   # GitHub
   GITHUB_TOKEN=ghp_...
   
   # Jira
   JIRA_URL=https://your-company.atlassian.net
   JIRA_EMAIL=your.email@example.com
   JIRA_API_TOKEN=...
   
   # Confluence
   CONFLUENCE_URL=https://your-company.atlassian.net/wiki
   CONFLUENCE_EMAIL=your.email@example.com
   CONFLUENCE_API_TOKEN=...
   
   # Figma
   FIGMA_API_TOKEN=...
   ```

5. **Install MCP servers** (optional, will be auto-installed on first run):
   ```bash
   npm install -g @modelcontextprotocol/server-github
   npm install -g @joshuajaco/mcp-server-atlassian
   ```

## Usage

### Basic Usage

Generate summaries for the 5 most recent merged PRs:

```bash
python src/main.py generate https://github.com/owner/repo
```

### Advanced Options

```bash
# Process only 3 PRs
python src/main.py generate https://github.com/owner/repo --max-prs 3

# Custom output directory
python src/main.py generate https://github.com/owner/repo --output ./my-summaries

# Verbose logging
python src/main.py generate https://github.com/owner/repo --verbose

# Custom config directory
python src/main.py generate https://github.com/owner/repo --config ./my-config
```

### Test MCP Connections

Before running the agent, test that all MCP servers are configured correctly:

```bash
python src/main.py test-connections
```

### Show Version

```bash
python src/main.py version
```

## Configuration

### Agent Configuration (`config/agent_config.yaml`)

```yaml
# LLM Settings
llm:
  provider: openai  # or anthropic
  model: gpt-4o
  temperature: 0.7
  max_tokens: 4096

# Processing Settings
processing:
  max_prs: 5
  enable_parallel: true
  parallel_workers: 3

# File Categorization
file_categories:
  backend:
    - '**/*.py'
    - '**/*.java'
  frontend:
    - '**/*.js'
    - '**/*.tsx'
  # ... more categories
```

### MCP Server Configuration (`config/mcp_servers.json`)

The MCP servers are configured with their commands and environment variables. The configuration supports variable substitution from `.env` file.

## Output

The agent generates individual markdown files for each PR in the `outputs/` directory:

```
outputs/
├── PR-123-repo-name-summary.md
├── PR-124-repo-name-summary.md
└── PR-125-repo-name-summary.md
```

### Summary Template Structure

Each summary includes:

1. **PR Metadata**: Number, title, author, merge date, branches
2. **AI Summary**: High-level overview of changes
3. **Jira Context**: Related tickets with descriptions and status
4. **Changes Overview**: File statistics categorized by type
5. **Figma Designs**: Linked design files
6. **Confluence Documentation**: Related pages
7. **Testing Notes**: Test files and QA information
8. **Review Summary**: Reviewers and key decisions
9. **Impact Analysis**: Affected components and risk assessment
10. **Links**: All related resources

## Customization

### Custom Templates

You can customize the summary templates by editing:

- `templates/pr_summary_template.md` - Main template with full context
- `templates/pr_summary_fallback.md` - Fallback for PRs with minimal context
- `templates/prompts.py` - LLM prompts for summarization

Templates use Jinja2 syntax:

```jinja2
## Summary

{{ ai_summary }}

{% if jira_tickets %}
### Related Jira Tickets
{% for ticket in jira_tickets %}
- {{ ticket.key }}: {{ ticket.title }}
{% endfor %}
{% endif %}
```

### Custom File Categories

Edit `config/agent_config.yaml` to add custom file categorization patterns:

```yaml
file_categories:
  my_category:
    - '**/*.custom'
    - 'my-folder/**'
```

## Development

### Project Structure

```
scraper-prs/
├── src/
│   ├── agent/
│   │   ├── graph.py          # LangGraph workflow definition
│   │   ├── nodes.py          # Node implementations
│   │   ├── state.py          # State schema
│   │   └── tools.py          # MCP tool wrappers
│   ├── extractors/
│   │   ├── jira.py           # Jira ID extraction
│   │   ├── figma.py          # Figma URL extraction
│   │   ├── confluence.py     # Confluence search
│   │   └── files.py          # File categorization
│   ├── mcp/
│   │   ├── client.py         # MCP client manager
│   │   └── config.py         # Config loader
│   ├── utils/
│   │   ├── markdown.py       # Markdown utilities
│   │   └── logger.py         # Logging setup
│   └── main.py               # CLI entry point
├── templates/
│   ├── pr_summary_template.md
│   ├── pr_summary_fallback.md
│   └── prompts.py
├── config/
│   ├── mcp_servers.json
│   └── agent_config.yaml
├── tests/
├── outputs/
└── pyproject.toml
```

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

## Troubleshooting

### MCP Server Connection Issues

If MCP servers fail to connect:

1. **Check environment variables**: Ensure all required tokens are set in `.env`
2. **Test connections**: Run `python src/main.py test-connections`
3. **Check Node.js**: Verify Node.js is installed: `node --version`
4. **Manual MCP server test**: Try running MCP servers manually:
   ```bash
   npx -y @modelcontextprotocol/server-github
   ```

### GitHub Rate Limiting

If you hit GitHub API rate limits:

- The agent is configured to respect rate limits with retry logic
- Authenticated requests get 5,000 requests/hour
- Reduce `max_prs` to process fewer PRs

### Missing Context

If Jira/Confluence/Figma context is missing:

- **Jira IDs not found**: Ensure PR titles/descriptions follow format like "PROJ-123: Description"
- **Confluence pages not found**: Agent searches by Jira IDs and keywords - verify pages exist
- **Figma files not found**: Ensure Figma URLs are in PR description

### LLM Errors

If LLM summarization fails:

- Check API key is valid
- Verify sufficient credits/quota
- Try reducing `max_tokens` in config
- Check for large PRs exceeding context window

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- Uses [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- Powered by OpenAI/Anthropic LLMs

## Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/your-org/scraper-prs/issues)
- Documentation: See this README and inline code documentation

---

**Note**: This agent requires valid API tokens for GitHub, Jira, Confluence, and Figma. Ensure you have appropriate access and follow your organization's API usage policies.
