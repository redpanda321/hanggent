"""
Usage Record model for tracking agent token usage and cost.

This module provides data structures for tracking:
- Per-agent token consumption
- Model-specific usage metrics
- Estimated costs based on token pricing
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from sqlalchemy import Float, Integer, Column, String, Index
from sqlmodel import Field, JSON
from pydantic import BaseModel, Field as PydanticField
from app.model.abstract.model import AbstractModel, DefaultTimes


class UsageRecord(AbstractModel, DefaultTimes, table=True):
    """
    Usage record for tracking agent token consumption and cost.
    
    Tracks usage per agent execution including:
    - Token counts (input, output, total)
    - Model information (platform, type)
    - Estimated cost based on pricing
    - Task context (task_id, project_id)
    """
    __tablename__ = "usage_record"
    
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    task_id: str = Field(index=True)
    project_id: Optional[str] = Field(default=None, index=True)
    
    # Agent information
    agent_name: str = Field(sa_column=Column(String(64), index=True))
    agent_step: Optional[int] = Field(default=None)  # Step number in task execution
    
    # Model information
    model_platform: str = Field(sa_column=Column(String(64)))
    model_type: str = Field(sa_column=Column(String(128)))
    
    # Token counts
    input_tokens: int = Field(default=0, sa_column=Column(Integer, server_default="0"))
    output_tokens: int = Field(default=0, sa_column=Column(Integer, server_default="0"))
    total_tokens: int = Field(default=0, sa_column=Column(Integer, server_default="0"))
    
    # Cost estimation (in USD)
    estimated_cost: float = Field(default=0.0, sa_column=Column(Float, server_default="0"))
    
    # Execution metadata
    execution_time_ms: Optional[int] = Field(default=None)  # Execution time in milliseconds
    success: bool = Field(default=True)
    error_message: Optional[str] = Field(default=None, sa_column=Column(String(512)))
    
    # Additional context
    extra_metadata: Optional[dict] = Field(default=None, sa_column=Column("metadata", JSON))
    
    __table_args__ = (
        Index('idx_usage_user_created', 'user_id', 'created_at'),
        Index('idx_usage_task_agent', 'task_id', 'agent_name'),
    )


class UsageRecordIn(BaseModel):
    """Input schema for creating a usage record."""
    task_id: str
    project_id: Optional[str] = None
    agent_name: str
    agent_step: Optional[int] = None
    model_platform: str
    model_type: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    execution_time_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Optional[dict] = None


class UsageRecordOut(BaseModel):
    """Output schema for usage record."""
    id: int
    user_id: int
    task_id: str
    project_id: Optional[str] = None
    agent_name: str
    agent_step: Optional[int] = None
    model_platform: str
    model_type: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    execution_time_ms: Optional[int] = None
    success: bool
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


class UsageSummaryByAgent(BaseModel):
    """Summary of usage grouped by agent."""
    agent_name: str
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost: float
    success_rate: float
    avg_execution_time_ms: Optional[float] = None


class UsageSummaryByModel(BaseModel):
    """Summary of usage grouped by model."""
    model_platform: str
    model_type: str
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost: float


class UsageSummaryByDay(BaseModel):
    """Summary of usage grouped by day."""
    date: str
    total_calls: int
    total_tokens: int
    total_cost: float


class UsageDashboardData(BaseModel):
    """Complete dashboard data for usage visualization."""
    total_tokens: int
    total_cost: float
    total_calls: int
    by_agent: List[UsageSummaryByAgent]
    by_model: List[UsageSummaryByModel]
    by_day: List[UsageSummaryByDay]
    # Time range info
    start_date: Optional[str] = None
    end_date: Optional[str] = None


# Token pricing per 1M tokens (approximate, can be configured)
MODEL_PRICING = {
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "o1": {"input": 15.00, "output": 60.00},
    "o1-preview": {"input": 15.00, "output": 60.00},
    "o1-mini": {"input": 3.00, "output": 12.00},
    
    # Anthropic
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    
    # Google
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    
    # DeepSeek
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    
    # Default fallback
    "default": {"input": 1.00, "output": 3.00},
}


def estimate_cost(model_type: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estimate cost in USD based on model type and token counts.
    
    Args:
        model_type: The model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        
    Returns:
        Estimated cost in USD
    """
    # Find pricing, use partial matching for model variants
    pricing = MODEL_PRICING.get("default")
    model_lower = model_type.lower()
    
    for model_key, model_pricing in MODEL_PRICING.items():
        if model_key != "default" and model_key.lower() in model_lower:
            pricing = model_pricing
            break
    
    # Calculate cost (pricing is per 1M tokens)
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    
    return round(input_cost + output_cost, 6)
