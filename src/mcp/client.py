"""
MCP Client Manager for handling MCP server connections and tool calls.
"""
import asyncio
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPClient:
    """Manages connection to a single MCP server."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self.read_stream = None
        self.write_stream = None
        self.process: Optional[subprocess.Popen] = None
        self._available_tools: List[Dict[str, Any]] = []
    
    async def connect(self) -> None:
        """Connect to the MCP server."""
        try:
            server_params = StdioServerParameters(
                command=self.config["command"],
                args=self.config.get("args", []),
                env=self.config.get("env", {}),
                cwd=self.config.get("cwd"),
            )
            
            logger.info(f"Connecting to MCP server: {self.name}")
            
            # Create stdio client - KEEP THE CONNECTION OPEN
            # Store the context managers to maintain the connection
            stdio_context = stdio_client(server_params)
            self.read_stream, self.write_stream = await stdio_context.__aenter__()
            
            # Create and store the session
            session_context = ClientSession(self.read_stream, self.write_stream)
            self.session = await session_context.__aenter__()
            
            # Store context managers for cleanup
            self._stdio_context = stdio_context
            self._session_context = session_context
            
            # Initialize the session
            await self.session.initialize()
            
            # List available tools
            tools_response = await self.session.list_tools()
            self._available_tools = tools_response.tools
            
            logger.info(
                f"Connected to {self.name}. "
                f"Available tools: {len(self._available_tools)}"
            )
        
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.name}: {e}")
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server."""
        if not self.session:
            raise RuntimeError(f"MCP server {self.name} not connected")
        
        try:
            logger.debug(f"Calling tool {tool_name} on {self.name} with args: {arguments}")
            
            result = await self.session.call_tool(tool_name, arguments)
            
            logger.debug(f"Tool {tool_name} returned: {result}")
            return result
        
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on {self.name}: {e}")
            return None
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return [tool.name for tool in self._available_tools]
    
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self.session:
            try:
                # Properly close the session and stdio contexts
                if hasattr(self, '_session_context'):
                    await self._session_context.__aexit__(None, None, None)
                if hasattr(self, '_stdio_context'):
                    await self._stdio_context.__aexit__(None, None, None)
            except RuntimeError as e:
                # Suppress known anyio/asyncio cleanup errors during shutdown
                # These are harmless and occur due to task cleanup ordering
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in [
                    "cancel scope",
                    "different task",
                    "task was entered"
                ]):
                    logger.debug(f"Ignoring async cleanup warning for {self.name}: {e}")
                else:
                    logger.warning(f"Runtime error closing MCP server {self.name}: {e}")
            except (asyncio.CancelledError, GeneratorExit):
                # Suppress cancellation errors during shutdown
                logger.debug(f"Async cancellation during {self.name} disconnect (normal during shutdown)")
            except Exception as e:
                logger.warning(f"Error closing MCP server {self.name}: {e}")
            finally:
                self.session = None
                self.read_stream = None
                self.write_stream = None
        
        logger.info(f"Disconnected from MCP server: {self.name}")


class MCPClientManager:
    """Manages multiple MCP server connections."""

    def __init__(self, mcp_config: Dict[str, Any]):
        self.mcp_config = mcp_config
        self.clients: Dict[str, MCPClient] = {}
        self._connected = False
    
    async def connect_all(self) -> None:
        """Connect to all configured MCP servers."""
        servers = self.mcp_config.get("mcpServers", {})
        
        logger.info(f"Connecting to {len(servers)} MCP servers...")
        
        # Create clients
        for name, config in servers.items():
            self.clients[name] = MCPClient(name, config)
        
        # Connect to all servers concurrently
        connection_tasks = [
            client.connect() for client in self.clients.values()
        ]
        
        # Use gather with return_exceptions to continue even if some fail
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        # Check which connections succeeded
        successful = []
        failed = []
        
        for name, result in zip(self.clients.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Failed to connect to {name}: {result}")
                failed.append(name)
            else:
                successful.append(name)
        
        # Remove failed clients
        for name in failed:
            del self.clients[name]
        
        self._connected = True
        
        logger.info(
            f"Successfully connected to {len(successful)} MCP servers: {successful}"
        )
        
        if failed:
            logger.warning(f"Failed to connect to: {failed}")
    
    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        logger.info("Disconnecting from all MCP servers...")
        
        disconnect_tasks = [
            client.disconnect() for client in self.clients.values()
        ]
        
        await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        
        self.clients.clear()
        self._connected = False
        
        logger.info("Disconnected from all MCP servers")
    
    def get_client(self, name: str) -> Optional[MCPClient]:
        """Get a specific MCP client."""
        return self.clients.get(name)
    
    def is_connected(self, name: str) -> bool:
        """Check if a specific MCP server is connected."""
        return name in self.clients
    
    def get_all_tools(self) -> Dict[str, List[str]]:
        """Get all available tools from all servers."""
        return {
            name: client.get_available_tools()
            for name, client in self.clients.items()
        }
    
    async def call_tool(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any]
    ) -> Any:
        """Call a tool on a specific MCP server."""
        client = self.get_client(server_name)
        
        if not client:
            logger.error(f"MCP server not connected: {server_name}")
            return None
        
        return await client.call_tool(tool_name, arguments)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        asyncio.run(self.disconnect_all())


# Singleton instance
_mcp_manager: Optional[MCPClientManager] = None


async def get_mcp_manager(mcp_config: Dict[str, Any]) -> MCPClientManager:
    """Get or create MCPClientManager singleton."""
    global _mcp_manager
    
    if _mcp_manager is None or not _mcp_manager._connected:
        _mcp_manager = MCPClientManager(mcp_config)
        await _mcp_manager.connect_all()
    
    return _mcp_manager
