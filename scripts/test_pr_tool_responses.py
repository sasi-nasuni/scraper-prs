#!/usr/bin/env python3
"""
Test script to inspect raw responses from GitHub MCP tools for a given PR.
This helps debug what data is actually being returned from each tool call.

Usage:
    python scripts/test_pr_tool_responses.py --repo owner/repo --pr 123
    python scripts/test_pr_tool_responses.py --repo nasuni/portal --pr 1448
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mcp.client import MCPClientManager
from src.mcp.config import get_config_loader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress asyncio cleanup errors during shutdown (known MCP client library issue)
class AsyncioCleanupFilter(logging.Filter):
    """Filter out harmless asyncio cleanup errors during shutdown."""
    def filter(self, record):
        if record.name == 'asyncio' and record.levelno == logging.ERROR:
            msg = record.getMessage().lower()
            # Suppress known harmless errors
            if any(keyword in msg for keyword in [
                'cancel scope',
                'different task',
                'unhandled exception during asyncio.run() shutdown',
                'cancelledaerror',
                'generatorexit'
            ]):
                return False
        return True

# Apply the filter to asyncio logger
logging.getLogger('asyncio').addFilter(AsyncioCleanupFilter())


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def print_response(tool_name: str, response, output_dir: Path):
    """Print tool response in a readable format and save full JSON to file."""
    print(f"\n--- {tool_name} ---\n")
    
    if not response:
        print("❌ No response (None)")
        return
    
    # Try to extract content
    if hasattr(response, 'content'):
        print(f"Content type: {type(response.content)}")
        print(f"Content length: {len(response.content) if response.content else 0}")
        
        if response.content:
            first_content = response.content[0]
            
            # Extract text/data
            if hasattr(first_content, 'text'):
                print(f"✅ Has 'text' attribute")
                try:
                    data = json.loads(first_content.text)
                    print(f"\nParsed JSON structure:")
                    print(f"  Type: {type(data)}")
                    
                    if isinstance(data, list):
                        print(f"  Length: {len(data)} items")
                        if len(data) > 0:
                            print(f"  First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'N/A'}")
                    elif isinstance(data, dict):
                        print(f"  Keys: {list(data.keys())}")
                    
                    # Write full JSON to file
                    output_file = output_dir / f"{tool_name}.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
                    print(f"✅ Full JSON written to: {output_file}")
                    
                except json.JSONDecodeError as e:
                    print(f"\n❌ Failed to parse text as JSON: {e}")
                    print(f"Raw text (first 500 chars): {first_content.text[:500]}")
            
            elif hasattr(first_content, 'data'):
                print(f"✅ Has 'data' attribute")
                print(f"Data type: {type(first_content.data)}")
                
                # Write full JSON to file
                output_file = output_dir / f"{tool_name}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(first_content.data, f, indent=2, default=str, ensure_ascii=False)
                print(f"✅ Full JSON written to: {output_file}")
            else:
                print(f"❌ No 'text' or 'data' attribute found")
    
    if hasattr(response, 'isError'):
        print(f"isError: {response.isError}")
    
    print("-"*80)


async def test_pr_tools(owner: str, repo: str, pr_number: int):
    """Test all GitHub PR tools and display raw responses."""
    
    print_section(f"Testing GitHub MCP Tools for PR #{pr_number}")
    print(f"Repository: {owner}/{repo}")
    print(f"PR Number: {pr_number}")
    
    # Create output directory for JSON files
    output_dir = Path(__file__).parent.parent / "outputs" / f"pr_{pr_number}_responses"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Output directory: {output_dir}\n")
    
    # Load MCP config using ConfigLoader
    config_dir = Path(__file__).parent.parent / "config"
    config_loader = get_config_loader(str(config_dir))
    mcp_config = config_loader.load_mcp_config()
    
    # Initialize MCP manager
    mcp_manager = MCPClientManager(mcp_config)
    
    try:
        # Connect to GitHub MCP server
        print("Connecting to GitHub MCP server...")
        await mcp_manager.connect_all()
        print("✅ Connected successfully!\n")
        
        # Test 1: Get Pull Request
        print_section("1. get_pull_request")
        pr_response = await mcp_manager.call_tool(
            "github",
            "get_pull_request",
            {
                "owner": owner,
                "repo": repo,
                "pull_number": pr_number,
            }
        )
        print_response("get_pull_request", pr_response, output_dir)
        
        # Test 2: Get Pull Request Files
        print_section("2. get_pull_request_files")
        files_response = await mcp_manager.call_tool(
            "github",
            "get_pull_request_files",
            {
                "owner": owner,
                "repo": repo,
                "pull_number": pr_number,
            }
        )
        print_response("get_pull_request_files", files_response, output_dir)
        
        # Test 3: Get Pull Request Reviews
        print_section("3. get_pull_request_reviews")
        reviews_response = await mcp_manager.call_tool(
            "github",
            "get_pull_request_reviews",
            {
                "owner": owner,
                "repo": repo,
                "pull_number": pr_number,
            }
        )
        print_response("get_pull_request_reviews", reviews_response, output_dir)
        
        # Test 4: Get Pull Request Comments
        print_section("4. get_pull_request_comments")
        review_comments_response = await mcp_manager.call_tool(
            "github",
            "get_pull_request_comments",
            {
                "owner": owner,
                "repo": repo,
                "pull_number": pr_number,
            }
        )
        print_response("get_pull_request_comments", review_comments_response, output_dir)
        
        print_section("Summary")
        print(f"✅ All tool calls completed for PR #{pr_number}")
        print(f"\n📁 Full JSON responses saved to: {output_dir}")
        print(f"\nFiles created:")
        for json_file in sorted(output_dir.glob("*.json")):
            size_kb = json_file.stat().st_size / 1024
            print(f"  - {json_file.name} ({size_kb:.1f} KB)")
        print(f"\n⚠️  Note: Commits are not fetched - list_commits returns all repo commits,")
        print(f"      not PR-specific ones. File changes provide sufficient context.")
        
    except Exception as e:
        logger.error(f"Error during testing: {e}", exc_info=True)
        return 1
    
    finally:
        # Cleanup
        print("\n\nDisconnecting from MCP servers...")
        await mcp_manager.disconnect_all()
        print("✅ Disconnected")
    
    return 0


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test GitHub MCP tools and inspect raw responses for a PR"
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Repository in format 'owner/repo' (e.g., 'nasuni/portal')"
    )
    parser.add_argument(
        "--pr",
        type=int,
        required=True,
        help="Pull request number (e.g., 1448)"
    )
    
    args = parser.parse_args()
    
    # Parse repo
    if "/" not in args.repo:
        print(f"❌ Error: Repository must be in format 'owner/repo', got: {args.repo}")
        return 1
    
    owner, repo = args.repo.split("/", 1)
    
    # Run async test
    exit_code = asyncio.run(test_pr_tools(owner, repo, args.pr))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
