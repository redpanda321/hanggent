"""
User Usage Summary Model

Tracks monthly token usage and spending for billing purposes.
"""
from datetime import datetime
from sqlalchemy import Integer, Float, Boolean, text
from sqlmodel import Field, Column
from app.model.abstract.model import AbstractModel, DefaultTimes


class UserUsageSummary(AbstractModel, DefaultTimes, table=True):
    """
    Monthly usage summary for each user.
    One record per user per billing period (month).
    """
    __tablename__ = "user_usage_summary"
    
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, description="User ID")
    
    # Billing period (year-month format for easy querying)
    billing_year: int = Field(description="Billing year (e.g., 2026)")
    billing_month: int = Field(description="Billing month (1-12)")
    
    # Token usage tracking
    total_input_tokens: int = Field(
        default=0,
        sa_column=Column(Integer, server_default=text("0")),
        description="Total input tokens used this period"
    )
    total_output_tokens: int = Field(
        default=0,
        sa_column=Column(Integer, server_default=text("0")),
        description="Total output tokens used this period"
    )
    free_tokens_used: int = Field(
        default=0,
        sa_column=Column(Integer, server_default=text("0")),
        description="Free tokens consumed from plan allowance"
    )
    paid_tokens_used: int = Field(
        default=0,
        sa_column=Column(Integer, server_default=text("0")),
        description="Paid tokens consumed (after free allowance)"
    )
    
    # Spending tracking
    total_spending: float = Field(
        default=0.0,
        sa_column=Column(Float, server_default=text("0.0")),
        description="Total spending in dollars for this period"
    )
    spending_limit: float = Field(
        default=100.0,
        sa_column=Column(Float, server_default=text("100.0")),
        description="Spending limit for this period"
    )
    
    # Alert tracking
    alert_threshold_reached: bool = Field(
        default=False,
        sa_column=Column(Boolean, server_default=text("0")),
        description="Whether 90% spending alert was triggered"
    )
    alert_sent_at: datetime | None = Field(
        default=None,
        description="When the spending alert was sent"
    )
    limit_reached: bool = Field(
        default=False,
        sa_column=Column(Boolean, server_default=text("0")),
        description="Whether spending limit was reached"
    )
    limit_reached_at: datetime | None = Field(
        default=None,
        description="When the spending limit was reached"
    )
    
    # Model-specific usage (JSON field for detailed breakdown)
    # This will store: {"gpt-5": {"input": 1000, "output": 500, "cost": 0.05}, ...}
    model_usage_breakdown: str | None = Field(
        default=None,
        description="JSON breakdown of usage by model"
    )
    
    class Config:
        """SQLModel configuration"""
        table = True


class UserUsageSummaryOut:
    """Output schema for user usage summary"""
    id: int
    user_id: int
    billing_year: int
    billing_month: int
    total_input_tokens: int
    total_output_tokens: int
    free_tokens_used: int
    paid_tokens_used: int
    total_spending: float
    spending_limit: float
    alert_threshold_reached: bool
    limit_reached: bool
    created_at: datetime
    updated_at: datetime
