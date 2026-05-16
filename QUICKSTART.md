# Quick Start Guide

This guide will help you get the PR Summary Agent up and running quickly.

## Prerequisites

Before you begin, ensure you have:

- Python 3.11+
- Node.js 18+
- Git

## Installation Steps

### 1. Set up the project

```bash
# Navigate to the project directory
cd scraper-prs

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 2. Configure API tokens

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` and add your tokens:

```env
# Required: Choose your LLM provider
OPENAI_API_KEY=sk-...
# OR
# ANTHROPIC_API_KEY=sk-ant-...

# Required: GitHub token
GITHUB_TOKEN=ghp_...

# Required: Jira credentials
JIRA_URL=https://your-company.atlassian.net
JIRA_EMAIL=your.email@example.com
JIRA_API_TOKEN=...

# Required: Confluence (usually same as Jira)
CONFLUENCE_URL=https://your-company.atlassian.net/wiki
CONFLUENCE_EMAIL=your.email@example.com
CONFLUENCE_API_TOKEN=...

# Optional: Figma token (if you need Figma integration)
FIGMA_API_TOKEN=...
```

### 3. Get API Tokens

#### GitHub Token
1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Select scopes: `repo`, `read:org`
4. Copy the token to `.env`

#### Jira/Confluence Token
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Copy the token to `.env`

#### Figma Token
1. Go to https://www.figma.com/settings
2. Scroll to "Personal access tokens"
3. Click "Create new token"
4. Copy the token to `.env`

### 4. Test the setup

Test that all MCP servers can connect:

```bash
python src/main.py test-connections
```

You should see:
```
✓ Connected to github
✓ Connected to atlassian
✓ Connected to figma
```

## Your First PR Summary

Run the agent on a sample repository:

```bash
# Process the latest 3 PRs from a public repo
python src/main.py generate https://github.com/langchain-ai/langgraph --max-prs 3
```

Check the `outputs/` directory for generated summaries!

## Next Steps

### Customize Templates

Edit the templates to match your organization's needs:

```bash
# Edit the main template
nano templates/pr_summary_template.md

# Edit the LLM prompts
nano templates/prompts.py
```

### Adjust Configuration

Modify agent behavior:

```bash
# Edit agent settings
nano config/agent_config.yaml
```

Common adjustments:
- Change LLM model
- Adjust file categorization patterns
- Modify processing settings

### Run on Your Repository

```bash
python src/main.py generate https://github.com/your-org/your-repo
```

## Troubleshooting

### "Environment variable not set" error

Make sure your `.env` file has all required variables and you're in the project directory.

### "Failed to connect to MCP server"

1. Check that Node.js is installed: `node --version`
2. Verify API tokens are correct
3. Check network/firewall settings

### "No PRs found"

- Ensure the repository has merged PRs
- Check that your GitHub token has access to the repository

### Rate limiting

If you hit GitHub rate limits:
- Use `--max-prs 3` to process fewer PRs
- Wait an hour for limits to reset
- Ensure you're using an authenticated token

## Tips

- **Start small**: Use `--max-prs 1` for your first run
- **Verbose mode**: Add `--verbose` to see detailed logs
- **Custom output**: Use `--output ./my-summaries` for custom location
- **Review templates**: Check `outputs/` after first run and adjust templates as needed

## Getting Help

- Check the main [README.md](README.md) for full documentation
- Review logs in `scraper-prs.log`
- Use `--verbose` flag for detailed debugging

Happy summarizing! 🚀
