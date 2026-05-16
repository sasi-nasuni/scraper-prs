#!/usr/bin/env python3
"""
Test script to verify Atlassian MCP server and fetch a Jira issue.
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mcp.client import MCPClientManager
from src.mcp.config import get_config_loader
from src.utils.logger import setup_logging
from dotenv import load_dotenv
import os


async def test_jira_fetch(issue_key: str):
    """Test fetching a Jira issue via Atlassian MCP."""
    
    # Explicitly load .env from project root
    env_path = project_root / ".env"
    load_dotenv(env_path, override=True)
    
    # Check if required variables are set
    print("Checking environment variables...")
    required_vars = ["ATLASSIAN_CLOUD_ID", "JIRA_EMAIL", "JIRA_API_TOKEN", "FIGMA_API_TOKEN"]
    for var in required_vars:
        value = os.getenv(var, "NOT SET")
        masked = value[:10] + "..." if value != "NOT SET" and len(value) > 10 else value
        print(f"  {var}: {masked}")
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"\n✗ Missing environment variables: {', '.join(missing_vars)}")
        print(f"  Please uncomment them in: {env_path}")
        return 1
    
    print("✓ All required variables are set\n")
    
    # Setup logging
    setup_logging(level="INFO", enable_file=False)
    logger = logging.getLogger(__name__)
    
    print(f"\n{'='*60}")
    print(f"Testing Atlassian MCP - Fetching Jira Issue: {issue_key}")
    print(f"{'='*60}\n")
    
    # Load config
    config_loader = get_config_loader()
    mcp_config = config_loader.load_mcp_config()
    
    # Initialize MCP manager
    mcp_manager = MCPClientManager(mcp_config)
    
    try:
        # Connect to all MCP servers
        print("Connecting to MCP servers...")
        await mcp_manager.connect_all()
        
        if "atlassian" not in mcp_manager.clients:
            print("✗ Atlassian MCP server not connected")
            return 1
        
        print("✓ Connected to Atlassian MCP\n")
        
        # List Jira-related tools
        print("Available Jira tools:")
        client = mcp_manager.clients["atlassian"]
        if hasattr(client, '_available_tools'):
            jira_tools = [t for t in client._available_tools if 'jira' in t.name.lower() or 'issue' in t.name.lower()]
            for tool in jira_tools[:15]:
                print(f"  - {tool.name}")
            
            print("\nAvailable Confluence tools:")
            conf_tools = [t for t in client._available_tools if 'confluence' in t.name.lower()]
            for tool in conf_tools[:10]:
                print(f"  - {tool.name}")
        print()
        
        # Fetch the Jira issue
        print(f"Fetching issue {issue_key}...")
        cloud_id = os.getenv("ATLASSIAN_CLOUD_ID")
        result = await mcp_manager.call_tool(
            "atlassian",
            "getJiraIssue",
            {
                "cloudId": cloud_id,
                "issueIdOrKey": issue_key
            }
        )
        
        if not result:
            print(f"✗ No result returned for {issue_key}")
            return
        
        # Extract data from MCP response
        data = None
        if hasattr(result, 'content') and result.content:
            first_content = result.content[0]
            # Try text first
            if hasattr(first_content, 'text') and first_content.text:
                try:
                    data = json.loads(first_content.text)
                except json.JSONDecodeError:
                    print(f"Debug: text content = {first_content.text[:200]}")
            # Try data attribute
            elif hasattr(first_content, 'data'):
                data = first_content.data
            else:
                print(f"Debug: first_content attributes = {dir(first_content)}")
                print(f"Debug: first_content = {first_content}")
        
        if not data:
            print(f"✗ No data in response for {issue_key}")
            print(f"Debug: result = {result}")
            return
        
        # Display issue details
        print(f"\n{'='*60}")
        print(f"✓ Successfully fetched {issue_key}")
        print(f"{'='*60}\n")
        
        if isinstance(data, dict):
            print(f"Key:         {data.get('key', 'N/A')}")
            print(f"Summary:     {data.get('fields', {}).get('summary', 'N/A')}")
            print(f"Status:      {data.get('fields', {}).get('status', {}).get('name', 'N/A')}")
            print(f"Issue Type:  {data.get('fields', {}).get('issuetype', {}).get('name', 'N/A')}")
            print(f"Assignee:    {data.get('fields', {}).get('assignee', {}).get('displayName', 'Unassigned')}")
            print(f"Reporter:    {data.get('fields', {}).get('reporter', {}).get('displayName', 'N/A')}")
            print(f"Created:     {data.get('fields', {}).get('created', 'N/A')}")
            print(f"Updated:     {data.get('fields', {}).get('updated', 'N/A')}")
            
            description = data.get('fields', {}).get('description')
            if description:
                desc_text = description if isinstance(description, str) else str(description)[:200]
                print(f"\nDescription: {desc_text}")
            
            # Save full JSON
            output_file = project_root / "outputs" / f"jira_{issue_key}.json"
            output_file.parent.mkdir(exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"\n✓ Full JSON saved to: {output_file}")
        else:
            print(f"Unexpected data format: {type(data)}")
            print(json.dumps(data, indent=2)[:500])
        
    except Exception as e:
        logger.error(f"Error testing Jira fetch: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")
        return 1
    
    finally:
        # Cleanup
        await mcp_manager.disconnect_all()
        print("\n✓ Disconnected from MCP servers")
    
    return 0


def main():
    parser = argparse.ArgumentParser(description="Test Atlassian MCP by fetching a Jira issue")
    parser.add_argument(
        "issue_key",
        help="Jira issue key (e.g., PORTAL-1687)"
    )
    
    args = parser.parse_args()
    
    exit_code = asyncio.run(test_jira_fetch(args.issue_key))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
