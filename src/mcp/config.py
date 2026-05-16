"""
MCP Server Configuration Loader
"""
import json
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


class ConfigLoader:
    """Loads and validates configuration files."""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        load_dotenv()  # Load environment variables from .env file
    
    def load_mcp_config(self) -> Dict[str, Any]:
        """Load MCP server configuration."""
        config_path = self.config_dir / "mcp_servers.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"MCP config not found: {config_path}")
        
        with open(config_path, "r") as f:
            config = json.load(f)
        
        # Substitute environment variables
        config = self._substitute_env_vars(config)
        
        return config
    
    def load_agent_config(self) -> Dict[str, Any]:
        """Load agent configuration."""
        config_path = self.config_dir / "agent_config.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Agent config not found: {config_path}")
        
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        # Override with environment variables if present
        config = self._override_with_env(config)
        
        return config
    
    def _substitute_env_vars(self, obj: Any) -> Any:
        """Recursively substitute ${VAR} patterns with environment variables."""
        if isinstance(obj, dict):
            return {k: self._substitute_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env_vars(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            env_var = obj[2:-1]
            value = os.getenv(env_var)
            if value is None:
                raise ValueError(f"Environment variable not set: {env_var}")
            return value
        return obj
    
    def _override_with_env(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Override config values with environment variables."""
        # LLM settings
        if os.getenv("LLM_PROVIDER"):
            config["llm"]["provider"] = os.getenv("LLM_PROVIDER")
        if os.getenv("LLM_MODEL"):
            config["llm"]["model"] = os.getenv("LLM_MODEL")
        if os.getenv("LLM_TEMPERATURE"):
            config["llm"]["temperature"] = float(os.getenv("LLM_TEMPERATURE"))
        if os.getenv("LLM_MAX_TOKENS"):
            config["llm"]["max_tokens"] = int(os.getenv("LLM_MAX_TOKENS"))
        
        # API Keys (used by LangChain, not stored in config but made available)
        if os.getenv("OPENAI_API_KEY"):
            config["llm"]["openai_api_key"] = os.getenv("OPENAI_API_KEY")
        if os.getenv("ANTHROPIC_API_KEY"):
            config["llm"]["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY")
        if os.getenv("OPENAI_API_BASE"):
            config["llm"]["base_url"] = os.getenv("OPENAI_API_BASE")
        
        # Processing settings
        if os.getenv("MAX_PRS_TO_PROCESS"):
            config["processing"]["max_prs"] = int(os.getenv("MAX_PRS_TO_PROCESS"))
        
        # Output settings
        if os.getenv("OUTPUT_DIR"):
            config["output"]["directory"] = os.getenv("OUTPUT_DIR")
        
        # Logging settings
        if os.getenv("LOG_LEVEL"):
            config["logging"]["level"] = os.getenv("LOG_LEVEL")
        if os.getenv("LOG_FILE"):
            config["logging"]["file_path"] = os.getenv("LOG_FILE")
        
        return config
    
    def validate_mcp_config(self, config: Dict[str, Any]) -> bool:
        """Validate MCP configuration structure."""
        required_keys = ["mcpServers"]
        
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required key in MCP config: {key}")
        
        # Validate each server configuration
        for server_name, server_config in config["mcpServers"].items():
            if "command" not in server_config:
                raise ValueError(f"Server '{server_name}' missing 'command' field")
            if "args" not in server_config:
                raise ValueError(f"Server '{server_name}' missing 'args' field")
        
        return True
    
    def validate_agent_config(self, config: Dict[str, Any]) -> bool:
        """Validate agent configuration structure."""
        required_sections = ["llm", "processing", "templates", "output"]
        
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required section in agent config: {section}")
        
        return True


# Singleton instance
_config_loader = None


def get_config_loader(config_dir: str = "config") -> ConfigLoader:
    """Get or create ConfigLoader singleton."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(config_dir)
    return _config_loader
