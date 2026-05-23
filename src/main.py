"""
Main entry point for the PR Summary Agent.
"""
import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.agent.graph import run_pr_summary_agent
from src.mcp.client import get_mcp_manager
from src.mcp.config import get_config_loader
from src.utils.logger import setup_logging

# Initialize CLI app
app = typer.Typer(
    help="PR Summary Agent - Generate comprehensive PR summaries using MCP servers",
    add_completion=False,
)

console = Console()


@app.command()
def generate(
    repo_url: str = typer.Argument(
        "",
        help="GitHub repository URL (e.g., https://github.com/owner/repo). Not required when using --pr-url.",
    ),
    config_dir: str = typer.Option(
        "config",
        "--config",
        "-c",
        help="Path to configuration directory",
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for summaries (overrides config)",
    ),
    max_prs: Optional[int] = typer.Option(
        None,
        "--max-prs",
        "-n",
        help="Maximum number of PRs to process (overrides config)",
    ),
    pr_number: Optional[int] = typer.Option(
        None,
        "--pr-number",
        "-p",
        help="Process a specific PR number only",
    ),
    label: Optional[str] = typer.Option(
        None,
        "--label",
        "-l",
        help="Filter PRs by label (e.g., 'bug', 'feature')",
    ),
    pr_urls: Optional[List[str]] = typer.Option(
        None,
        "--pr-url",
        "-u",
        help="GitHub PR URLs to process (can be specified multiple times)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
) -> None:
    """
    Generate summaries for merged PRs in a GitHub repository.
    
    Example:
        scraper-prs generate https://github.com/microsoft/vscode --max-prs 3
        scraper-prs generate https://github.com/owner/repo --pr-number 1449
        scraper-prs generate https://github.com/owner/repo --label bug --max-prs 5
        scraper-prs generate --pr-url https://github.com/owner/repo/pull/123 --pr-url https://github.com/owner/repo/pull/456
    """
    try:
        # Derive repo_url from pr_urls if not provided directly
        if not repo_url and pr_urls:
            import re
            first_url = pr_urls[0].strip().rstrip("/")
            match = re.search(r'(https://github\.com/[^/]+/[^/]+)/pull/\d+', first_url)
            repo_url = match.group(1) if match else "multiple repositories"

        console.print(
            Panel.fit(
                "[bold blue]PR Summary Agent[/bold blue]\n"
                f"Repository: {repo_url}",
                border_style="blue",
            )
        )
        
        # Load configuration
        console.print("\n[yellow]Loading configuration...[/yellow]")
        config_loader = get_config_loader(config_dir)
        
        try:
            mcp_config = config_loader.load_mcp_config()
            agent_config = config_loader.load_agent_config()
            
            # Validate configs
            config_loader.validate_mcp_config(mcp_config)
            config_loader.validate_agent_config(agent_config)
            
            console.print("[green]✓ Configuration loaded successfully[/green]")
        
        except Exception as e:
            console.print(f"[red]✗ Configuration error: {e}[/red]")
            raise typer.Exit(code=1)
        
        # Setup logging with config from YAML (CLI --verbose flag overrides level)
        logging_config = agent_config.get("logging", {})
        log_level = "DEBUG" if verbose else logging_config.get("level", "INFO")
        setup_logging(
            level=log_level,
            log_file=logging_config.get("file_path", "scraper-prs.log"),
            max_bytes=logging_config.get("max_bytes", 10485760),
            backup_count=logging_config.get("backup_count", 5),
            enable_console=logging_config.get("console", True),
            enable_file=logging_config.get("file", True),
            log_format=logging_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        )
        
        logger = logging.getLogger(__name__)
        
        # Override config with CLI options
        if output_dir:
            agent_config["output"]["directory"] = output_dir
        
        if max_prs:
            agent_config["processing"]["max_prs"] = max_prs
        
        if pr_number:
            agent_config["processing"]["pr_number"] = pr_number
            agent_config["processing"]["max_prs"] = 1  # Process only this PR

        if label:
            agent_config["processing"]["label"] = label
        
        if pr_urls:
            agent_config["processing"]["pr_urls"] = list(pr_urls)
        
        # Add Jira URL and Atlassian cloud ID to config for tools (from environment variable)
        import os
        agent_config["jira_url"] = os.getenv("JIRA_URL", "https://nasuni.atlassian.net")
        agent_config["atlassian_cloud_id"] = os.getenv("ATLASSIAN_CLOUD_ID", "")
        
        # Run async agent
        console.print("\n[yellow]Initializing agent...[/yellow]")
        
        async def run_agent():
            # Initialize MCP manager
            mcp_manager = await get_mcp_manager(mcp_config)
            
            # Show connected servers
            connected_servers = list(mcp_manager.clients.keys())
            console.print(
                f"[green]✓ Connected to {len(connected_servers)} MCP servers: "
                f"{', '.join(connected_servers)}[/green]"
            )
            
            # Run agent
            console.print("\n[yellow]Processing PRs...[/yellow]\n")
            
            final_state = await run_pr_summary_agent(
                repo_url,
                mcp_manager,
                agent_config
            )
            
            # Cleanup
            await mcp_manager.disconnect_all()
            
            return final_state
        
        # Run the agent
        final_state = asyncio.run(run_agent())
        
        # Display results
        console.print("\n[bold green]✓ Processing complete![/bold green]\n")
        
        # Summary table
        summaries = final_state.get("summaries", [])
        output_files = final_state.get("output_files", [])
        errors = final_state.get("errors", [])
        warnings = final_state.get("warnings", [])
        
        # Results table
        table = Table(title="Summary Results", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("PRs Processed", str(len(summaries)))
        table.add_row("Summaries Generated", str(len(output_files)))
        table.add_row("Errors", str(len(errors)), style="red" if errors else "green")
        table.add_row("Warnings", str(len(warnings)), style="yellow" if warnings else "green")
        
        console.print(table)
        
        # Output files
        if output_files:
            console.print("\n[bold]Generated summaries:[/bold]")
            for file_path in output_files:
                console.print(f"  • {file_path}")
        
        # Show errors if any
        if errors:
            console.print("\n[bold red]Errors encountered:[/bold red]")
            for error in errors[:5]:  # Show first 5 errors
                console.print(f"  • {error.get('context', 'Unknown')}: {error.get('message', '')}")
            
            if len(errors) > 5:
                console.print(f"  ... and {len(errors) - 5} more errors")
        
        # Show warnings if any
        if warnings:
            console.print("\n[bold yellow]Warnings:[/bold yellow]")
            for warning in warnings[:5]:
                console.print(f"  • {warning}")
        
        console.print(
            f"\n[green]Output directory: {agent_config['output']['directory']}[/green]"
        )
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Process interrupted by user[/yellow]")
        raise typer.Exit(code=130)
    
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@app.command()
def test_connections(
    config_dir: str = typer.Option(
        "config",
        "--config",
        "-c",
        help="Path to configuration directory",
    ),
) -> None:
    """
    Test connections to MCP servers.
    """
    try:
        console.print("[yellow]Testing MCP server connections...[/yellow]\n")
        
        # Load configuration
        config_loader = get_config_loader(config_dir)
        mcp_config = config_loader.load_mcp_config()
        
        async def test_connections_async():
            mcp_manager = await get_mcp_manager(mcp_config)
            
            # Show connected servers
            table = Table(title="MCP Server Connections", show_header=True, header_style="bold cyan")
            table.add_column("Server", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Tools Available")
            
            for server_name, server_config in mcp_config["mcpServers"].items():
                if mcp_manager.is_connected(server_name):
                    client = mcp_manager.get_client(server_name)
                    tools = client.get_available_tools() if client else []
                    table.add_row(
                        server_name,
                        "[green]✓ Connected[/green]",
                        str(len(tools))
                    )
                else:
                    table.add_row(
                        server_name,
                        "[red]✗ Failed[/red]",
                        "0"
                    )
            
            console.print(table)
            
            # Cleanup
            await mcp_manager.disconnect_all()
        
        asyncio.run(test_connections_async())
        
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show version information."""
    console.print("[bold blue]PR Summary Agent[/bold blue]")
    console.print("Version: 0.1.0")
    console.print("Python: " + sys.version.split()[0])


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
