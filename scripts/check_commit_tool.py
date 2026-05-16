#!/usr/bin/env python3
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mcp.client import MCPClientManager
from src.mcp.config import get_config_loader

async def check_tool():
    config_loader = get_config_loader('config')
    mcp_config = config_loader.load_mcp_config()
    mcp_manager = MCPClientManager(mcp_config)
    await mcp_manager.connect_all()
    
    github_client = mcp_manager.clients.get('github')
    if github_client:
        tools_list = github_client.client.list_tools()
        async for response in tools_list:
            for tool in response.tools:
                if 'commit' in tool.name.lower():
                    print(f'\n{tool.name}:')
                    print(f'  Description: {tool.description}')
                    if hasattr(tool, 'inputSchema'):
                        schema = tool.inputSchema
                        if isinstance(schema, dict):
                            print(f'  Input Schema:')
                            print(json.dumps(schema, indent=4))
    
    await mcp_manager.disconnect_all()

asyncio.run(check_tool())
