"""
LangGraph workflow definition for PR summary agent.
"""
import logging
from typing import Any, Dict, Literal

from langgraph.graph import END, START, StateGraph

from src.agent.nodes import PRSummaryNodes
from src.agent.state import (
    AgentState,
    create_initial_state,
    should_continue_on_error,
    should_log_errors,
)
from src.mcp.client import MCPClientManager

logger = logging.getLogger(__name__)


def should_continue_processing(state: AgentState) -> Literal["process_pr", "end"]:
    """
    Conditional edge function to determine if more PRs need processing.
    
    Args:
        state: Current agent state
    
    Returns:
        "process_pr" if more PRs to process, "end" if done
    """
    pr_list = state.get("pr_list", [])
    current_index = state.get("current_pr_index", 0)
    
    if current_index < len(pr_list):
        return "process_pr"
    else:
        return "end"


def create_pr_summary_graph(
    mcp_manager: MCPClientManager,
    config: Dict[str, Any]
) -> StateGraph:
    """
    Create the LangGraph workflow for PR summary generation.
    
    Args:
        mcp_manager: MCP client manager
        config: Agent configuration
    
    Returns:
        Compiled StateGraph
    """
    logger.info("Creating PR summary graph")
    
    # Initialize nodes
    nodes = PRSummaryNodes(mcp_manager, config)
    
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("parse_repo_url", nodes.parse_repo_url)
    workflow.add_node("fetch_prs", nodes.fetch_prs)
    workflow.add_node("select_next_pr", nodes.select_next_pr)
    workflow.add_node("extract_references", nodes.extract_references)
    workflow.add_node("fetch_jira_context", nodes.fetch_jira_context)
    workflow.add_node("enrich_references_from_jira", nodes.enrich_references_from_jira)
    workflow.add_node("fetch_figma_context", nodes.fetch_figma_context)
    workflow.add_node("fetch_confluence_context", nodes.fetch_confluence_context)
    workflow.add_node("analyze_files", nodes.analyze_files)
    workflow.add_node("summarize_diffs", nodes.summarize_diffs)
    workflow.add_node("generate_summary", nodes.generate_summary)
    workflow.add_node("build_review_threads", nodes.build_review_threads)
    workflow.add_node("identify_coding_standards", nodes.identify_coding_standards)
    workflow.add_node("identify_architectural_patterns", nodes.identify_architectural_patterns)
    workflow.add_node("generate_review_summary", nodes.generate_review_summary)
    workflow.add_node("identify_breaking_changes", nodes.identify_breaking_changes)
    workflow.add_node("save_summary", nodes.save_summary)
    
    # Define workflow edges
    
    # Initial setup flow
    workflow.add_edge(START, "parse_repo_url")
    workflow.add_edge("parse_repo_url", "fetch_prs")
    workflow.add_edge("fetch_prs", "select_next_pr")
    
    # Conditional branching: continue processing or end
    workflow.add_conditional_edges(
        "select_next_pr",
        should_continue_processing,
        {
            "process_pr": "extract_references",
            "end": END,
        }
    )
    
    # Context fetching setup
    # Step 1 (parallel): Fetch Jira context + analyze files (independent of each other)
    workflow.add_edge("extract_references", "fetch_jira_context")
    workflow.add_edge("extract_references", "analyze_files")
    
    # Step 2: Enrich references from Jira ticket descriptions.
    # Jira tickets often contain Figma and Confluence URLs in their description
    # / acceptance-criteria fields, so we scan those *after* Jira is fetched.
    workflow.add_edge("fetch_jira_context", "enrich_references_from_jira")
    
    # Step 3 (parallel): Fetch Figma & Confluence with the enriched URL lists
    workflow.add_edge("enrich_references_from_jira", "fetch_figma_context")
    workflow.add_edge("enrich_references_from_jira", "fetch_confluence_context")
    
    # All context paths converge into summary generation
    workflow.add_edge("fetch_figma_context", "generate_summary")
    workflow.add_edge("fetch_confluence_context", "generate_summary")
    workflow.add_edge("analyze_files", "summarize_diffs")
    workflow.add_edge("summarize_diffs", "generate_summary")
    
    # Summary generation flow
    workflow.add_edge("generate_summary", "build_review_threads")
    workflow.add_edge("build_review_threads", "identify_coding_standards")
    workflow.add_edge("identify_coding_standards", "identify_architectural_patterns")
    workflow.add_edge("identify_architectural_patterns", "generate_review_summary")
    workflow.add_edge("generate_review_summary", "identify_breaking_changes")
    workflow.add_edge("identify_breaking_changes", "save_summary")
    
    # Loop back to select next PR
    workflow.add_edge("save_summary", "select_next_pr")
    
    # Compile the graph
    compiled_graph = workflow.compile()
    
    logger.info("PR summary graph created successfully")
    
    return compiled_graph


async def run_pr_summary_agent(
    repo_url: str,
    mcp_manager: MCPClientManager,
    config: Dict[str, Any],
    on_state_change: Any = None,
) -> AgentState:
    """
    Run the PR summary agent on a repository.
    
    Args:
        repo_url: GitHub repository URL
        mcp_manager: MCP client manager
        config: Agent configuration
        on_state_change: Optional async callback(state) called after each graph step
    
    Returns:
        Final agent state
    """
    logger.info(f"Starting PR summary agent for: {repo_url}")
    
    # Create initial state
    initial_state = create_initial_state(repo_url)
    
    # Create graph
    graph = create_pr_summary_graph(mcp_manager, config)
    
    # Run the graph
    try:
        if on_state_change:
            # Use stream_mode="updates" to get node names for progress,
            # but track full state by merging updates into initial_state.
            final_state = dict(initial_state)
            async for state_update in graph.astream(initial_state, stream_mode="updates"):
                # stream_mode="updates" yields {node_name: state_delta} dicts
                for node_name, node_output in state_update.items():
                    # Merge node output into our running full state
                    if isinstance(node_output, dict):
                        final_state.update(node_output)
                    try:
                        await on_state_change(node_name, final_state)
                    except Exception as cb_err:
                        logger.debug(f"Progress callback error: {cb_err}")
        else:
            final_state = await graph.ainvoke(initial_state)
        
        logger.info(
            f"Agent completed. Processed {len(final_state.get('summaries', []))} PRs"
        )
        
        return final_state
    
    except Exception as e:
        if should_log_errors(config):
            logger.error(f"Error running agent: {e}")
        
        # Re-raise if not configured to continue on error
        if not should_continue_on_error(config):
            raise
        
        # Return partial state even on error if continue_on_error is true
        return create_initial_state(repo_url)


def visualize_graph(
    mcp_manager: MCPClientManager,
    config: Dict[str, Any],
    output_path: str = "graph.png"
) -> None:
    """
    Visualize the LangGraph workflow.
    
    Args:
        mcp_manager: MCP client manager
        config: Agent configuration
        output_path: Path to save the visualization
    """
    try:
        graph = create_pr_summary_graph(mcp_manager, config)
        
        # Generate visualization
        from IPython.display import Image
        
        viz = graph.get_graph().draw_mermaid_png()
        
        with open(output_path, "wb") as f:
            f.write(viz)
        
        logger.info(f"Graph visualization saved to: {output_path}")
    
    except Exception as e:
        logger.warning(f"Could not visualize graph: {e}")
