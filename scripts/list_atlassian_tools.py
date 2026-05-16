"""
List all available Atlassian MCP tools.
"""
import asyncio

async def list_tools():
    from src.mcp.client import get_mcp_manager
    from src.mcp.config import get_config_loader
    
    config_loader = get_config_loader()
    config = config_loader.load_mcp_config()
    manager = await get_mcp_manager(config)
    
    print("Atlassian MCP Tools:")
    print("=" * 60)
    
    atlassian_client = manager.get_client('atlassian')
    if atlassian_client:
        tools = atlassian_client._available_tools
        print(f"\nTotal tools: {len(tools)}\n")
        
        # Filter Jira tools
        jira_tools = [t for t in tools if 'jira' in t.name.lower()]
        print(f"JIRA Tools ({len(jira_tools)}):")
        for tool in jira_tools:
            print(f"  - {tool.name}")
            if hasattr(tool, 'description'):
                print(f"    {tool.description}")
        
        # Filter Confluence tools
        print(f"\nCONFLUENCE Tools:")
        conf_tools = [t for t in tools if 'confluence' in t.name.lower()]
        for tool in conf_tools:
            print(f"  - {tool.name}")
            if hasattr(tool, 'description'):
                print(f"    {tool.description}")
    
    await manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(list_tools())
