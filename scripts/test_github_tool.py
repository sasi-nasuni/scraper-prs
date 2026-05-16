import asyncio
import json
import sys
sys.path.insert(0, '/Users/sbhushan/Documents/workspace/scraper-prs')

from src.mcp.client import MCPManager
from src.utils.config import load_mcp_config

async def test():
    config = load_mcp_config()
    manager = await MCPManager.create(config)
    
    # Check what tools are available
    tools = manager.clients['github'].list_tools()
    
    # Find PR-related tools
    pr_tools = [t for t in tools if 'pull' in t.name.lower()]
    
    print("Available PR tools:")
    for tool in pr_tools:
        print(f"\n{tool.name}:")
        print(f"  {tool.description}")
        if hasattr(tool, 'inputSchema'):
            print(f"  Parameters: {json.dumps(tool.inputSchema, indent=4)}")
    
    await manager.disconnect_all()

asyncio.run(test())
