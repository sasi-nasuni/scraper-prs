import asyncio
import sys
sys.path.insert(0, '/Users/sbhushan/Documents/workspace/scraper-prs')

from src.mcp.client import get_mcp_manager
from src.utils.config import load_mcp_config

async def main():
    config = load_mcp_config()
    manager = await get_mcp_manager(config)
    
    # Get GitHub tools
    github_client = manager.get_client('github')
    if github_client:
        tools = github_client._available_tools
        
        # Filter PR tools
        pr_tools = [t for t in tools if 'pull' in t.name.lower() or 'pr' in t.name.lower()]
        print("PR-Related Tools:")
        print("=" * 60)
        for tool in pr_tools:
            print(f"\n{tool.name}")
            print(f"  {tool.description}")
    
    await manager.disconnect_all()

asyncio.run(main())
