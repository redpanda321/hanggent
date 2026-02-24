"""
Model Routing Configuration for Multi-LLM Support.

This module provides data structures and logic for routing different agents
to different LLM models based on agent type, task complexity, and cost optimization.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class TaskComplexity(str, Enum):
    """Task complexity levels for cost-aware model routing."""
    simple = "simple"      # Direct answers, quick tasks (e.g., task planning)
    moderate = "moderate"  # Standard agent tasks (e.g., browsing, document)
    complex = "complex"    # Multi-step reasoning, coding (e.g., developer)


class CostTier(str, Enum):
    """Cost tier classification for models."""
    cheap = "cheap"        # e.g., gpt-4o-mini, claude-3-haiku, gemini-1.5-flash
    standard = "standard"  # e.g., gpt-4o, claude-3.5-sonnet, gemini-1.5-pro
    premium = "premium"    # e.g., o1, claude-3-opus, gpt-4


class AgentModelConfig(BaseModel):
    """Model configuration for a specific agent type."""
    model_platform: str
    model_type: str
    api_key: Optional[str] = None  # None = use default from Chat
    api_url: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "allow"

    def has_custom_config(self) -> bool:
        """Check if any custom model configuration is set."""
        return any(
            [
                self.model_platform is not None,
                self.model_type is not None,
                self.api_key is not None,
                self.api_url is not None,
                self.extra_params is not None,
            ]
        )


class AutoScalingConfig(BaseModel):
    """
    Auto-scaling configuration for cost management and fallback handling.
    
    Provides two auto-scaling mechanisms:
    1. Fallback on error: Switch to fallback model when primary fails
    2. Cost limits: Switch to cheaper model when cost limit reached
    """
    # Fallback on error
    fallback_enabled: bool = True
    fallback_model: Optional[AgentModelConfig] = None  # Model to use when primary fails
    max_retries: int = 2  # Max retries before fallback
    retry_delay_seconds: float = 1.0  # Delay between retries
    
    # Cost limit auto-scaling
    cost_limit_enabled: bool = False
    daily_cost_limit: Optional[float] = None  # Max daily spend in USD
    monthly_cost_limit: Optional[float] = None  # Max monthly spend in USD
    cost_limit_fallback_model: Optional[AgentModelConfig] = None  # Model when limit reached
    
    # Proactive cost management
    warn_at_percentage: float = 80.0  # Warn when this % of limit is reached
    downgrade_at_percentage: float = 90.0  # Auto-downgrade at this %


class ModelRoutingConfig(BaseModel):
    """
    Configuration for model routing per agent/complexity.
    
    Supports three routing strategies:
    1. Default model (fallback for all agents)
    2. Per-agent overrides (specific model for specific agent)
    3. Complexity-based routing (cheap/standard/premium based on task complexity)
    """
    # Default model (fallback)
    default: AgentModelConfig
    
    # Per-agent overrides (optional) - key is agent name from Agents enum
    agent_overrides: Dict[str, AgentModelConfig] = Field(default_factory=dict)
    
    # Complexity-based routing (optional)
    complexity_routing: Dict[TaskComplexity, AgentModelConfig] = Field(default_factory=dict)
    
    # Enable complexity-based routing (if False, only agent_overrides are used)
    use_complexity_routing: bool = False
    
    # Auto-scaling configuration
    auto_scaling: AutoScalingConfig = Field(default_factory=AutoScalingConfig)
    
    def get_model_for_agent(
        self, 
        agent_name: str, 
        complexity: Optional[TaskComplexity] = None
    ) -> AgentModelConfig:
        """
        Get appropriate model config for an agent.
        
        Priority order:
        1. Agent-specific override (if exists)
        2. Complexity-based routing (if enabled and complexity provided)
        3. Default model
        
        Args:
            agent_name: Name of the agent (from Agents enum)
            complexity: Optional task complexity level
            
        Returns:
            AgentModelConfig for the agent
        """
        # Priority 1: Agent-specific override
        if agent_name in self.agent_overrides:
            return self.agent_overrides[agent_name]
        
        # Priority 2: Complexity-based routing
        if self.use_complexity_routing and complexity and complexity in self.complexity_routing:
            return self.complexity_routing[complexity]
        
        # Priority 3: Default
        return self.default


# Default complexity mapping for each agent type
AGENT_DEFAULT_COMPLEXITY: Dict[str, TaskComplexity] = {
    "task_agent": TaskComplexity.simple,
    "coordinator_agent": TaskComplexity.simple,
    "question_confirm_agent": TaskComplexity.simple,
    "task_summary_agent": TaskComplexity.simple,
    "new_worker_agent": TaskComplexity.simple,
    "browser_agent": TaskComplexity.moderate,
    "document_agent": TaskComplexity.moderate,
    "multi_modal_agent": TaskComplexity.moderate,
    "social_medium_agent": TaskComplexity.moderate,
    "mcp_agent": TaskComplexity.moderate,
    "developer_agent": TaskComplexity.complex,
    "opencode_agent": TaskComplexity.complex,
}


# Recommended models by cost tier
COST_TIER_MODELS: Dict[CostTier, List[str]] = {
    CostTier.cheap: [
        "gpt-4o-mini",
        "claude-3-haiku-20240307",
        "gemini-1.5-flash",
        "deepseek-chat",
        "qwen-turbo",
    ],
    CostTier.standard: [
        "gpt-4o",
        "claude-3-5-sonnet-20241022",
        "gemini-1.5-pro",
        "deepseek-reasoner",
        "qwen-plus",
    ],
    CostTier.premium: [
        "o1",
        "o1-preview",
        "claude-3-opus-20240229",
        "gpt-4-turbo",
        "qwen-max",
    ],
}


def get_default_complexity_for_agent(agent_name: str) -> TaskComplexity:
    """Get the default complexity level for an agent."""
    return AGENT_DEFAULT_COMPLEXITY.get(agent_name, TaskComplexity.moderate)


def is_model_in_tier(model_type: str, tier: CostTier) -> bool:
    """Check if a model belongs to a specific cost tier."""
    tier_models = COST_TIER_MODELS.get(tier, [])
    model_lower = model_type.lower()
    return any(m.lower() in model_lower or model_lower in m.lower() for m in tier_models)


def suggest_tier_for_model(model_type: str) -> CostTier:
    """Suggest a cost tier for a given model."""
    for tier in [CostTier.cheap, CostTier.standard, CostTier.premium]:
        if is_model_in_tier(model_type, tier):
            return tier
    # Default to standard if unknown
    return CostTier.standard
