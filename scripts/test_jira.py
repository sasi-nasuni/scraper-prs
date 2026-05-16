import asyncio
import json

from src.mcp.client import get_mcp_manager
from src.utils.config import load_mcp_config

async def test_jira():
    config = load_mcp_config()
    manager = await get_mcp_manager(config)
    
    # Test calling Jira tool
    print("Testing Jira tool: atl_getJiraIssue")
    print("=" * 60)
    
    result = await manager.call_tool(
        "atlassian",
        "atl_getJiraIssue",
        {
            "issueKey": "PORTAL-1763"
        }
    )
    
    print(f"\nResult type: {type(result)}")
    print(f"Result: {result}")
    
    if hasattr(result, '__dict__'):
        print(f"\nResult attributes: {result.__dict__}")
    
    if hasattr(result, 'content'):
        print(f"\nContent: {result.content}")
        if result.content:
            print(f"First content type: {type(result.content[0])}")
            print(f"First content: {result.content[0]}")
            if hasattr(result.content[0], '__dict__'):
                print(f"First content attributes: {result.content[0].__dict__}")
    
    await manager.disconnect_all()

asyncio.run(test_jira())
