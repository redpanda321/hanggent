"""
TOML Configuration Loader

Provides support for loading configuration from TOML files, similar to
backend-manus config.toml format.

Configuration precedence (highest to lowest):
1. Environment variables (HANGGENT_*)
2. Runtime overrides (API parameters)
3. Project-level .hanggent.toml
4. User-level ~/.hanggent/config.toml
5. Default values

Example config.toml:
```toml
[llm]
model = "gpt-4o"
api_key = "sk-..."
base_url = "https://api.openai.com/v1"
max_tokens = 4096

[browser]
headless = true
browser_type = "chromium"

[planning]
enabled = true
max_steps = 15
default_agent = "opencode"

[search]
engine = "google"
api_key = "..."
```

Usage:
    from app.utils.toml_config import load_toml_config, merge_config
    
    # Load and merge TOML config
    toml_settings = load_toml_config(project_path="/path/to/project")
    
    # Merge with existing config
    merged = merge_config(base_config, toml_settings)
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("toml_config")

# Try to import tomli/toml
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for Python < 3.11
    except ImportError:
        tomllib = None
        logger.warning("TOML support not available. Install tomli for Python < 3.11")


class LLMConfig(BaseModel):
    """LLM configuration from TOML."""
    model: str = Field(default="gpt-4o", description="Model name")
    api_key: Optional[str] = Field(default=None, description="API key")
    base_url: Optional[str] = Field(default=None, description="API base URL")
    max_tokens: int = Field(default=4096, description="Maximum tokens per request")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    timeout: float = Field(default=60.0, description="Request timeout in seconds")


class BrowserTomlConfig(BaseModel):
    """Browser configuration from TOML."""
    headless: bool = Field(default=True, description="Run in headless mode")
    browser_type: str = Field(default="chromium", description="Browser type")
    disable_security: bool = Field(default=False, description="Disable security")
    cdp_port: int = Field(default=9222, description="CDP port for Electron mode")


class PlanningTomlConfig(BaseModel):
    """Planning configuration from TOML."""
    enabled: bool = Field(default=False, description="Enable planning mode")
    max_steps: int = Field(default=20, description="Maximum plan steps")
    max_retries: int = Field(default=2, description="Max retries per step")
    step_timeout: float = Field(default=300.0, description="Step timeout")
    default_agent: str = Field(default="opencode", description="Default agent")
    parallel_steps: bool = Field(default=False, description="Allow parallel steps")


class SearchTomlConfig(BaseModel):
    """Search engine configuration from TOML."""
    engine: str = Field(default="duckduckgo", description="Search engine")
    api_key: Optional[str] = Field(default=None, description="Search API key")
    search_engine_id: Optional[str] = Field(default=None, description="Google CSE ID")
    max_results: int = Field(default=10, description="Max search results")
    fallback_engines: List[str] = Field(
        default_factory=lambda: ["duckduckgo", "wikipedia"],
        description="Fallback search engines"
    )


class SandboxTomlConfig(BaseModel):
    """Sandbox configuration from TOML."""
    type: str = Field(default="none", description="Sandbox type: none, docker, daytona")
    image: str = Field(default="", description="Container image")
    memory_limit: str = Field(default="512m", description="Memory limit")
    cpu_limit: float = Field(default=1.0, description="CPU limit")
    vnc_enabled: bool = Field(default=False, description="Enable VNC")


class TomlSettings(BaseModel):
    """Root TOML configuration model."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    browser: BrowserTomlConfig = Field(default_factory=BrowserTomlConfig)
    planning: PlanningTomlConfig = Field(default_factory=PlanningTomlConfig)
    search: SearchTomlConfig = Field(default_factory=SearchTomlConfig)
    sandbox: SandboxTomlConfig = Field(default_factory=SandboxTomlConfig)
    
    # Extra sections for custom configuration
    extra: Dict[str, Any] = Field(default_factory=dict)


def find_project_config(
    start_path: Optional[Union[str, Path]] = None,
    config_name: str = ".hanggent.toml",
    max_depth: int = 10,
) -> Optional[Path]:
    """
    Find project-level TOML config by walking up the directory tree.
    
    Args:
        start_path: Starting directory (defaults to current working directory)
        config_name: Name of the config file
        max_depth: Maximum directories to traverse up
    
    Returns:
        Path to config file if found, None otherwise
    """
    current = Path(start_path or os.getcwd()).resolve()
    
    for _ in range(max_depth):
        config_path = current / config_name
        if config_path.is_file():
            logger.debug(f"Found project config: {config_path}")
            return config_path
        
        parent = current.parent
        if parent == current:
            # Reached root
            break
        current = parent
    
    return None


def load_toml_file(path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load a TOML file and return its contents as a dictionary.
    
    Args:
        path: Path to the TOML file
    
    Returns:
        Dictionary of TOML contents
    
    Raises:
        ImportError: If TOML library not available
        FileNotFoundError: If file doesn't exist
        ValueError: If TOML parsing fails
    """
    if tomllib is None:
        raise ImportError(
            "TOML support not available. Install tomli: pip install tomli"
        )
    
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"TOML config file not found: {path}")
    
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse TOML file {path}: {e}")


def load_toml_config(
    user_config_path: str = "~/.hanggent/config.toml",
    project_path: Optional[Union[str, Path]] = None,
    project_config_name: str = ".hanggent.toml",
) -> TomlSettings:
    """
    Load TOML configuration with proper precedence.
    
    Loads configuration from:
    1. User-level config (~/.hanggent/config.toml)
    2. Project-level config (.hanggent.toml in project or parent dirs)
    
    Project config takes precedence over user config.
    
    Args:
        user_config_path: Path to user-level config
        project_path: Starting path for project config search
        project_config_name: Name of project-level config file
    
    Returns:
        TomlSettings instance with merged configuration
    """
    merged_data: Dict[str, Any] = {}
    
    # 1. Load user config
    user_path = Path(user_config_path).expanduser()
    if user_path.is_file():
        try:
            user_data = load_toml_file(user_path)
            merged_data.update(user_data)
            logger.info(f"Loaded user config from {user_path}")
        except Exception as e:
            logger.warning(f"Failed to load user config: {e}")
    
    # 2. Load project config (takes precedence)
    project_config = find_project_config(project_path, project_config_name)
    if project_config:
        try:
            project_data = load_toml_file(project_config)
            # Deep merge project over user
            merged_data = deep_merge(merged_data, project_data)
            logger.info(f"Loaded project config from {project_config}")
        except Exception as e:
            logger.warning(f"Failed to load project config: {e}")
    
    # Parse known sections
    settings = TomlSettings()
    
    if "llm" in merged_data:
        settings.llm = LLMConfig(**merged_data["llm"])
    
    if "browser" in merged_data:
        settings.browser = BrowserTomlConfig(**merged_data["browser"])
    
    if "planning" in merged_data:
        settings.planning = PlanningTomlConfig(**merged_data["planning"])
    
    if "search" in merged_data:
        settings.search = SearchTomlConfig(**merged_data["search"])
    
    if "sandbox" in merged_data:
        settings.sandbox = SandboxTomlConfig(**merged_data["sandbox"])
    
    # Store extra sections
    known_sections = {"llm", "browser", "planning", "search", "sandbox"}
    settings.extra = {
        k: v for k, v in merged_data.items() 
        if k not in known_sections
    }
    
    return settings


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.
    
    Values from override take precedence. Nested dicts are merged recursively.
    
    Args:
        base: Base dictionary
        override: Override dictionary (takes precedence)
    
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if (
            key in result 
            and isinstance(result[key], dict) 
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def apply_toml_to_chat_options(
    options: "Chat",  # type: ignore
    toml_settings: TomlSettings,
) -> None:
    """
    Apply TOML settings to Chat options.
    
    Only applies settings that aren't already set (don't override explicit values).
    
    Args:
        options: Chat options to update
        toml_settings: Loaded TOML settings
    """
    # Apply LLM settings if not explicitly set
    if toml_settings.llm.api_key and not options.api_key:
        options.api_key = toml_settings.llm.api_key
    
    if toml_settings.llm.base_url and not options.api_url:
        options.api_url = toml_settings.llm.base_url
    
    # Apply planning settings
    if toml_settings.planning.enabled and not options.planning_mode:
        options.planning_mode = True
    
    # Apply search settings
    if toml_settings.search.api_key and options.search_config is None:
        options.search_config = {
            "GOOGLE_API_KEY": toml_settings.search.api_key,
            "SEARCH_ENGINE_ID": toml_settings.search.search_engine_id or "",
        }


def create_example_config(output_path: Optional[Union[str, Path]] = None) -> str:
    """
    Create an example TOML configuration file.
    
    Args:
        output_path: Optional path to write the file
    
    Returns:
        Example TOML content as string
    """
    example = '''# Hanggent Configuration
# Place this file at ~/.hanggent/config.toml (user-level)
# or .hanggent.toml in your project directory (project-level)

[llm]
# model = "gpt-4o"
# api_key = "sk-..."
# base_url = "https://api.openai.com/v1"
# max_tokens = 4096
# temperature = 0.7

[browser]
headless = true
browser_type = "chromium"
# cdp_port = 9222

[planning]
# Enable planning mode for explicit step tracking
enabled = false
max_steps = 20
max_retries = 2
step_timeout = 300.0
default_agent = "opencode"
# parallel_steps = false

[search]
engine = "duckduckgo"
# api_key = ""
# search_engine_id = ""
max_results = 10
fallback_engines = ["duckduckgo", "wikipedia"]

[sandbox]
type = "none"  # none, docker, daytona
# image = "daytonaio/ai-sandbox:latest"
# memory_limit = "512m"
# cpu_limit = 1.0
# vnc_enabled = false
'''
    
    if output_path:
        path = Path(output_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(example)
        logger.info(f"Created example config at {path}")
    
    return example


# Type hint for avoiding circular import
if False:  # TYPE_CHECKING
    from app.model.chat import Chat
