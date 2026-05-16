#!/usr/bin/env python3
"""
Test script to verify Jira/Atlassian MCP tool integration.
Fetches a specific Jira issue to verify connectivity and data retrieval.
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mcp.client import MCPClientManager
from src.mcp.config import get_config_loader
from src.agent.tools import JiraTools
from src.utils.logger import setup_logging


async def test_jira_issue(issue_key: str):
    """Test fetching a Jira issue."""
    print(f"\n{'='*60}")
    print(f"Testing Jira Issue Fetch: {issue_key}")
    print(f"{'='*60}\n")
    
    # Setup logging
    setup_logging(level="INFO")
    logger = logging.getLogger(__name__)
    
    # Load configuration
    config_loader = get_config_loader("config")
    mcp_config = config_loader.load_mcp_config()
    agent_config = config_loader.load_agent_config()
    
    # Initialize MCP manager
    print("Connecting to Atlassian MCP server...")
    mcp_manager = await MCPClientManager.create(mcp_config)
    
    # Check if atlassian server is connected
    if "atlassian" not in mcp_manager.clients:
        print("❌ Atlassian MCP server not connected!")
        print(f"Available servers: {list(mcp_manager.clients.keys())}")
        await mcp_manager.disconnect_all()
        return
    
    print(f"✓ Connected to Atlassian MCP server\n")
    
    # Get Jira configuration
    jira_url = os.getenv("JIRA_URL", "https://nasuni.atlassian.net")
    cloud_id = os.getenv("ATLASSIAN_CLOUD_ID", "")
    
    if not cloud_id:
        print("❌ ATLASSIAN_CLOUD_ID not set in environment!")
        await mcp_manager.disconnect_all()
        return
    
    print(f"Jira URL: {jira_url}")
    print(f"Cloud ID: {cloud_id}\n")
    
    # Initialize Jira tools
    jira_tools = JiraTools(
        mcp_manager=mcp_manager,
        jira_base_url=jira_url,
        cloud_id=cloud_id,
        config=agent_config
    )
    
    # Fetch the issue
    print(f"Fetching issue {issue_key}...")
    try:
        ticket = await jira_tools.get_issue(issue_key)
        
        if ticket:
            print(f"\n✓ Successfully fetched issue {issue_key}\n")
            print(f"{'─'*60}")
            print(f"Key:         {ticket.key}")
            print(f"Title:       {ticket.title}")
            print(f"Status:      {ticket.status}")
            print(f"Type:        {ticket.issue_type}")
            print(f"Priority:    {ticket.priority}")
            print(f"Created:     {ticket.created_at}")
            print(f"Updated:     {ticket.updated_at}")
            print(f"Reporter:    {ticket.reporter}")
            print(f"Assignee:    {ticket.assignee}")
            print(f"Labels:      {', '.join(ticket.labels) if ticket.labels else 'None'}")
            print(f"Components:  {', '.join(ticket.components) if ticket.components else 'None'}")
            print(f"{'─'*60}")
            
            if ticket.description:
                print(f"\nDescription:")
                print(f"{'─'*60}")
                desc_preview = ticket.description[:500]
                if len(ticket.description) > 500:
                    desc_preview += "..."
                print(desc_preview)
                print(f"{'─'*60}")
            
            print(f"\n✓ Jira integration is working correctly!")
        else:
            print(f"\n❌ Failed to fetch issue {issue_key}")
            print("Check:")
            print("  1. Issue key is correct")
            print("  2. ATLASSIAN_CLOUD_ID is correct")
            print("  3. JIRA_EMAIL and JIRA_API_TOKEN are valid")
            print("  4. You have permission to access this issue")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        print(f"\nDisconnecting from MCP servers...")
        await mcp_manager.disconnect_all()
        print("✓ Disconnected")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Jira MCP integration")
    parser.add_argument(
        "issue_key",
        nargs="?",
        default="PORTAL-1687",
        help="Jira issue key (e.g., PORTAL-1687)"
    )
    
    args = parser.parse_args()
    
    asyncio.run(test_jira_issue(args.issue_key))
