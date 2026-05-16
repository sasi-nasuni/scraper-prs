"""
Step-by-step pipeline execution engine.

Provides interactive, node-by-node execution of the PR summary pipeline.
Instead of running the compiled LangGraph all at once, this module calls
each node method directly in topological order.  Each node returns a
partial dict of only the keys it produced, which is merged into state
and forwarded to the UI as the node's output.
"""
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.agent.nodes import PRSummaryNodes
from src.agent.state import AgentState, create_initial_state
from src.mcp.client import MCPClientManager
from src.mcp.config import get_config_loader

logger = logging.getLogger(__name__)

# ── Execution order ─────────────────────────────────────────────────────────
# Topological sort that respects all graph edges.  Parallel nodes in the graph
# (e.g. fetch_jira_context / analyze_files) are simply run sequentially here –
# the UI groups them visually but step execution is serial.

EXECUTION_ORDER: List[str] = [
    "parse_repo_url",
    "fetch_prs",
    "select_next_pr",
    "extract_references",
    "fetch_jira_context",
    "analyze_files",
    "enrich_references_from_jira",
    "summarize_diffs",
    "fetch_figma_context",
    "fetch_confluence_context",
    "generate_summary",
    "build_review_threads",
    "identify_coding_standards",
    "identify_architectural_patterns",
    "generate_review_summary",
    "identify_breaking_changes",
    "save_summary",
]


# ── Serialization helpers ───────────────────────────────────────────────────

def _serialize_value(val: Any) -> Any:
    """Convert a state value to a JSON-safe representation."""
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, BaseModel):
        return val.model_dump(mode="json")
    if isinstance(val, list):
        return [_serialize_value(item) for item in val]
    if isinstance(val, dict):
        return {str(k): _serialize_value(v) for k, v in val.items()}
    return str(val)


# ── Session ─────────────────────────────────────────────────────────────────

class PipelineSession:
    """Holds state for one interactive pipeline execution."""

    def __init__(self, session_id: str, repo_url: str, pr_number: int):
        self.session_id = session_id
        self.repo_url = repo_url
        self.pr_number = pr_number
        self.created_at = datetime.now()

        # Internals (set during initialize)
        self.state: Optional[AgentState] = None
        self.nodes: Optional[PRSummaryNodes] = None
        self.mcp_manager: Optional[MCPClientManager] = None

        # Progress tracking
        self.executed_nodes: List[str] = []
        self.node_outputs: Dict[str, Dict[str, Any]] = {}
        self.node_durations: Dict[str, float] = {}
        self.node_errors: Dict[str, str] = {}
        self.is_initialized = False
        self.is_running = False

    # ── Lifecycle ───────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Connect MCP servers, build nodes, create initial state."""
        config_loader = get_config_loader("config")
        mcp_config = config_loader.load_mcp_config()
        agent_config = config_loader.load_agent_config()

        # Apply overrides
        agent_config["processing"]["pr_number"] = self.pr_number
        agent_config["processing"]["max_prs"] = 1
        agent_config["jira_url"] = os.getenv("JIRA_URL", "https://nasuni.atlassian.net")
        agent_config["atlassian_cloud_id"] = os.getenv("ATLASSIAN_CLOUD_ID", "")

        self.mcp_manager = MCPClientManager(mcp_config)
        await self.mcp_manager.connect_all()

        self.nodes = PRSummaryNodes(self.mcp_manager, agent_config)
        self.state = create_initial_state(self.repo_url)
        self.is_initialized = True

        logger.info(
            f"[{self.session_id}] Pipeline session initialized for "
            f"{self.repo_url} PR#{self.pr_number}"
        )

    async def cleanup(self) -> None:
        """Disconnect MCP clients."""
        if self.mcp_manager:
            try:
                await self.mcp_manager.disconnect_all()
            except Exception as exc:
                logger.debug(f"[{self.session_id}] cleanup error: {exc}")

    # ── Execution helpers ───────────────────────────────────────────────

    def next_index(self) -> int:
        return len(self.executed_nodes)

    def nodes_to_execute(self, target_node: Optional[str]) -> List[str]:
        """Return the slice of EXECUTION_ORDER still to run, up to *target_node*."""
        start = self.next_index()
        if target_node is None or target_node == "__all__":
            return EXECUTION_ORDER[start:]
        if target_node not in EXECUTION_ORDER:
            raise ValueError(f"Unknown node: {target_node}")
        end = EXECUTION_ORDER.index(target_node) + 1
        if end <= start:
            return []
        return EXECUTION_ORDER[start:end]

    async def execute_node(self, node_name: str) -> Dict[str, Any]:
        """Run one node, return its output (serialized partial dict).

        Every node returns a partial dict of only the keys it produced.
        That dict is merged into state and serialized for the UI.
        """
        if not self.is_initialized or self.state is None or self.nodes is None:
            raise RuntimeError("Session not initialized")

        method = getattr(self.nodes, node_name, None)
        if method is None:
            raise ValueError(f"No method for node: {node_name}")

        start = time.time()

        try:
            result = await method(self.state)
        except Exception as exc:
            duration = round((time.time() - start) * 1000, 1)
            self.node_errors[node_name] = str(exc)
            self.node_durations[node_name] = duration
            logger.error(f"[{self.session_id}] {node_name} failed ({duration}ms): {exc}")
            raise

        duration = round((time.time() - start) * 1000, 1)

        # Merge partial return into accumulated state
        self.state.update(result)

        # Serialize the node's explicit return for UI display
        output = {k: _serialize_value(v) for k, v in result.items()}

        self.executed_nodes.append(node_name)
        self.node_outputs[node_name] = output
        self.node_durations[node_name] = duration

        logger.info(
            f"[{self.session_id}] {node_name} completed ({duration}ms), "
            f"output keys: {list(output.keys())}"
        )
        return output

    async def retry_node(self, node_name: str) -> Dict[str, Any]:
        """Re-run a single previously-executed (or errored) node.

        Clears old output/error for *node_name*, re-executes it against the
        current accumulated state, and merges the fresh result back in.
        Returns the serialised output dict (same shape as ``execute_node``).
        """
        if not self.is_initialized or self.state is None or self.nodes is None:
            raise RuntimeError("Session not initialized")

        if node_name not in EXECUTION_ORDER:
            raise ValueError(f"Unknown node: {node_name}")

        was_executed = node_name in self.executed_nodes
        was_errored = node_name in self.node_errors

        if not was_executed and not was_errored:
            raise ValueError(
                f"Node '{node_name}' has not been executed yet – "
                f"use the normal execute endpoint instead"
            )

        # Clear previous tracking for this node
        if node_name in self.executed_nodes:
            self.executed_nodes.remove(node_name)
        self.node_outputs.pop(node_name, None)
        self.node_durations.pop(node_name, None)
        self.node_errors.pop(node_name, None)

        logger.info(f"[{self.session_id}] Retrying node: {node_name}")

        # Re-run via the normal execute_node path
        return await self.execute_node(node_name)

    # ── Serialization ───────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "repo_url": self.repo_url,
            "pr_number": self.pr_number,
            "created_at": self.created_at.isoformat(),
            "is_initialized": self.is_initialized,
            "is_running": self.is_running,
            "executed_nodes": self.executed_nodes,
            "total_nodes": len(EXECUTION_ORDER),
            "execution_order": EXECUTION_ORDER,
            "node_outputs": self.node_outputs,
            "node_durations": self.node_durations,
            "node_errors": self.node_errors,
        }


# ── Session manager (singleton) ────────────────────────────────────────────

class PipelineSessionManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, PipelineSession] = {}

    def create(self, repo_url: str, pr_number: int) -> PipelineSession:
        sid = str(uuid.uuid4())[:8]
        session = PipelineSession(sid, repo_url, pr_number)
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Optional[PipelineSession]:
        return self._sessions.get(session_id)

    def list_all(self) -> List[PipelineSession]:
        return sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)

    async def delete(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session:
            await session.cleanup()
            return True
        return False


_manager: Optional[PipelineSessionManager] = None


def get_pipeline_manager() -> PipelineSessionManager:
    global _manager
    if _manager is None:
        _manager = PipelineSessionManager()
    return _manager
