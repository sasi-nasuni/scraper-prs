"""
Simple test to check Atlassian Jira tool response format.
Run with: python -m test_jira_simple
"""
import asyncio
import json
import os
from pathlib import Path

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent))


async def test_jira():
    from src.mcp.client import get_mcp_manager
    from src.mcp.config import get_config_loader
    
    config_loader = get_config_loader()
    config = config_loader.load_mcp_config()
    manager = await get_mcp_manager(config)
    
    print("Testing Jira tool: getJiraIssue")
    print("=" * 60)
    
    result = await manager.call_tool(
        "atlassian",
        "getJiraIssue",
        {
            "cloudId": "7e649dcd-2342-4352-afe0-3ec45d6ea0f8",
            "issueIdOrKey": "PORTAL-1763"
        }
    )
    
    print(f"\nResult type: {type(result)}")
    
    if hasattr(result, 'content') and result.content:
        print(f"\nParsing JSON from content...")
        data_str = result.content[0].text
        data = json.loads(data_str)
        
        print("\n✓ Successfully retrieved Jira issue\n")
        print("Issue Details:")
        print(f"  Key: {data.get('key')}")
        print(f"  Summary: {data.get('fields', {}).get('summary')}")
        print(f"  Status: {data.get('fields', {}).get('status', {}).get('name')}")
        print(f"  Priority: {data.get('fields', {}).get('priority', {}).get('name')}")
        
        assignee = data.get('fields', {}).get('assignee')
        if assignee:
            print(f"  Assignee: {assignee.get('displayName')} ({assignee.get('emailAddress')})")
        
        description = data.get('fields', {}).get('description', '')
        if description:
            print(f"\nDescription:\n{description[:300]}...")
        
        parent = data.get('fields', {}).get('parent')
        if parent:
            print(f"\nParent Epic: {parent.get('key')} - {parent.get('fields', {}).get('summary')}")
    else:
        print(f"Unexpected result format: {result}")
    
    # Disconnect - ignore cleanup warnings
    try:
        await manager.disconnect_all()
    except Exception:
        pass  # Suppress any cleanup errors


if __name__ == "__main__":
    # Suppress async generator warnings
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    
    # Custom exception handler that suppresses anyio cancel scope errors
    def custom_exception_handler(loop, context):
        """Suppress anyio cancel scope errors during cleanup."""
        exception = context.get('exception')
        if exception and 'cancel scope' in str(exception).lower():
            return  # Silently ignore
        
        # For other exceptions, use default behavior
        if 'message' in context:
            msg = context['message']
        else:
            msg = 'Unhandled exception in async code'
        
        # Only print if it's not an async generator cleanup issue
        if 'async_generator' not in str(exception):
            print(f"Event loop error: {msg}", file=sys.stderr)
    
    # Get or create event loop and set custom exception handler
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(custom_exception_handler)
    
    try:
        loop.run_until_complete(test_jira())
    finally:
        # Clean shutdown with suppressed warnings
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except Exception:
            pass  # Suppress any cleanup errors
