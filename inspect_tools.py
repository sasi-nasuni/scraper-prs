import asyncio
import json
from src.mcp.config import ConfigLoader
from src.mcp.client import MCPClientManager

async def inspect_tools():
    # Load config
    config_loader = ConfigLoader('config')
    mcp_config = config_loader.load_mcp_config()
    
    # Connect to MCP servers
    manager = MCPClientManager(mcp_config)
    await manager.connect_all()
    
    # Get GitHub client
    github_client = manager.get_client('github')
    
    if github_client:
        print('📋 Available GitHub Tools:\n')
        tools = github_client._available_tools
        
        # Find list_pull_requests specifically
        for tool in tools:
            if 'list_pull_requests' in tool.name:
                print(f'🔧 Tool: {tool.name}')
                print(f'   Description: {tool.description}')
                print(f'\n   Input Schema:')
                print(json.dumps(tool.inputSchema, indent=6))
                print('\n' + '='*70 + '\n')
        
        # Also show get_pull_request
        for tool in tools:
            if tool.name == 'get_pull_request':
                print(f'🔧 Tool: {tool.name}')
                print(f'   Description: {tool.description}')
                print(f'\n   Input Schema:')
                print(json.dumps(tool.inputSchema, indent=6))
                break
    
    await manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(inspect_tools())
