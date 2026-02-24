"""Admin LLM Configuration models.

These models store system-wide LLM provider configurations and pricing
that serve as fallback for users who haven't configured their own API keys.
"""  # noqa: ERA001 – rebuild 2026-02-19
from datetime import datetime
from decimal import Decimal
from enum import IntEnum
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, SmallInteger, String, Text, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlmodel import Field, JSON
from sqlalchemy_utils import ChoiceType
from sqlalchemy import text
from app.model.abstract.model import AbstractModel, DefaultTimes


class ConfigStatus(IntEnum):
    """Status for admin LLM configurations."""
    disabled = 0
    enabled = 1


class AdminLLMConfig(AbstractModel, DefaultTimes, table=True):
    """System-wide LLM provider configuration.
    
    This table stores API keys and endpoints for LLM providers that are used
    as fallbacks when users don't have their own provider configuration.
    Only admin users can manage these configurations.
    """
    __tablename__ = "admin_llm_config"
    __table_args__ = (
        UniqueConstraint("provider_name", name="uix_admin_llm_config_provider"),
    )
    
    id: int = Field(default=None, primary_key=True)
    provider_name: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    display_name: str = Field(default="", sa_column=Column(String(128)))
    api_key: str = Field(sa_column=Column(Text, nullable=False))
    endpoint_url: str = Field(default="", sa_column=Column(String(512)))
    # The specific model to use with this provider (e.g. "gpt-4o", "claude-3-5-sonnet-20241022")
    model_type: str = Field(default="", sa_column=Column(String(128), server_default=text("''")))
    # JSON field for provider-specific config (e.g., Azure deployment name, org ID)
    extra_config: dict | None = Field(default=None, sa_column=Column(JSON))
    status: ConfigStatus = Field(
        default=ConfigStatus.enabled,
        sa_column=Column(ChoiceType(ConfigStatus, SmallInteger()), server_default=text("1")),
    )
    # Priority for load balancing when multiple configs exist
    priority: int = Field(default=0, sa_column=Column(SmallInteger(), server_default=text("0")))
    # Rate limit tracking
    rate_limit_rpm: int | None = Field(default=None, description="Requests per minute limit")
    rate_limit_tpm: int | None = Field(default=None, description="Tokens per minute limit")
    # Notes for admin reference
    notes: str = Field(default="", sa_column=Column(Text))


class AdminLLMConfigCreate(BaseModel):
    """Input model for creating admin LLM config."""
    provider_name: str
    display_name: str = ""
    api_key: str
    endpoint_url: str = ""
    model_type: str = ""
    extra_config: dict | None = None
    status: ConfigStatus = ConfigStatus.enabled
    priority: int = 0
    rate_limit_rpm: int | None = None
    rate_limit_tpm: int | None = None
    notes: str = ""


class AdminLLMConfigUpdate(BaseModel):
    """Input model for updating admin LLM config."""
    display_name: str | None = None
    api_key: str | None = None
    endpoint_url: str | None = None
    model_type: str | None = None
    extra_config: dict | None = None
    status: ConfigStatus | None = None
    priority: int | None = None
    rate_limit_rpm: int | None = None
    rate_limit_tpm: int | None = None
    notes: str | None = None


class AdminLLMConfigOut(BaseModel):
    """Output model for admin LLM config (masks API key)."""
    id: int
    provider_name: str
    display_name: str
    api_key_masked: str  # Shows only last 4 chars
    endpoint_url: str
    model_type: str
    extra_config: dict | None
    status: ConfigStatus
    priority: int
    rate_limit_rpm: int | None
    rate_limit_tpm: int | None
    notes: str
    created_at: datetime
    updated_at: datetime


class AdminModelPricing(AbstractModel, DefaultTimes, table=True):
    """Pricing configuration for LLM models.
    
    Stores input/output token pricing for different models,
    used for usage tracking and billing calculations.
    """
    __tablename__ = "admin_model_pricing"
    __table_args__ = (
        UniqueConstraint("provider_name", "model_name", name="uix_admin_model_pricing_provider_model"),
    )
    
    id: int = Field(default=None, primary_key=True)
    provider_name: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    model_name: str = Field(sa_column=Column(String(128), nullable=False, index=True))
    display_name: str = Field(default="", sa_column=Column(String(256)))
    # Pricing per million tokens (stored as Decimal for precision)
    input_price_per_million: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(10, 4), server_default=text("0"))
    )
    output_price_per_million: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(10, 4), server_default=text("0"))
    )
    # Cost tier for routing decisions
    cost_tier: str = Field(default="standard", sa_column=Column(String(20), server_default=text("'standard'")))
    # Context window size
    context_length: int | None = Field(default=None, description="Max context window in tokens")
    # Whether this model is available for use
    is_available: bool = Field(default=True, sa_column=Column(Boolean, server_default=text("true")))
    # Notes
    notes: str = Field(default="", sa_column=Column(Text))


class AdminModelPricingCreate(BaseModel):
    """Input model for creating model pricing."""
    provider_name: str
    model_name: str
    display_name: str = ""
    input_price_per_million: Decimal = Decimal("0")
    output_price_per_million: Decimal = Decimal("0")
    cost_tier: str = "standard"
    context_length: int | None = None
    is_available: bool = True
    notes: str = ""


class AdminModelPricingUpdate(BaseModel):
    """Input model for updating model pricing."""
    display_name: str | None = None
    input_price_per_million: Decimal | None = None
    output_price_per_million: Decimal | None = None
    cost_tier: str | None = None
    context_length: int | None = None
    is_available: bool | None = None
    notes: str | None = None


class AdminModelPricingOut(BaseModel):
    """Output model for model pricing."""
    id: int
    provider_name: str
    model_name: str
    display_name: str
    input_price_per_million: Decimal
    output_price_per_million: Decimal
    cost_tier: str
    context_length: int | None
    is_available: bool
    notes: str
    created_at: datetime
    updated_at: datetime


# Default provider configurations with placeholder keys
DEFAULT_PROVIDERS = [
    {
        "provider_name": "hanggent",
        "display_name": "Hanggent Cloud",
        "endpoint_url": "https://api.hangent.com/v1",
        "model_type": "gpt-4o",
    },
    {
        "provider_name": "openai",
        "display_name": "OpenAI",
        "endpoint_url": "https://api.openai.com/v1",
        "model_type": "gpt-4o",
    },
    {
        "provider_name": "anthropic",
        "display_name": "Anthropic",
        "endpoint_url": "https://api.anthropic.com",
        "model_type": "claude-3-5-sonnet-20241022",
    },
    {
        "provider_name": "google",
        "display_name": "Google AI (Gemini)",
        "endpoint_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model_type": "gemini-2.0-flash",
    },
    {
        "provider_name": "azure",
        "display_name": "Azure OpenAI",
        "endpoint_url": "",  # User must configure
        "model_type": "gpt-4o",
    },
    {
        "provider_name": "groq",
        "display_name": "Groq",
        "endpoint_url": "https://api.groq.com/openai/v1",
        "model_type": "llama-3.3-70b-versatile",
    },
    {
        "provider_name": "deepseek",
        "display_name": "DeepSeek",
        "endpoint_url": "https://api.deepseek.com",
        "model_type": "deepseek-chat",
    },
    {
        "provider_name": "openrouter",
        "display_name": "OpenRouter",
        "endpoint_url": "https://openrouter.ai/api/v1",
        "model_type": "openai/gpt-4o",
    },
    {
        "provider_name": "together",
        "display_name": "Together AI",
        "endpoint_url": "https://api.together.xyz/v1",
        "model_type": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    },
    {
        "provider_name": "minimax",
        "display_name": "MiniMax",
        "endpoint_url": "https://api.minimax.io/v1",
        "model_type": "MiniMax-Text-01",
    },
    {
        "provider_name": "kimi",
        "display_name": "KIMI (Moonshot)",
        "endpoint_url": "https://api.moonshot.ai/v1",
        "model_type": "kimi-k2",
    },
    {
        "provider_name": "z-ai",
        "display_name": "Z.ai",
        "endpoint_url": "https://api.z.ai/api/coding/paas/v4/",
        "model_type": "z1-preview",
    },
    {
        "provider_name": "qwen",
        "display_name": "Qwen (Tongyi Qianwen)",
        "endpoint_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "model_type": "qwen-plus",
    },
    {
        "provider_name": "xai",
        "display_name": "xAI",
        "endpoint_url": "https://api.x.ai/v1",
        "model_type": "grok-4-fast",
    },
]

# Default model pricing (prices as of early 2025, per million tokens)
DEFAULT_MODEL_PRICING = [
    # OpenAI
    {"provider_name": "openai", "model_name": "gpt-4o", "display_name": "GPT-4o", "input_price_per_million": "2.50", "output_price_per_million": "10.00", "cost_tier": "standard", "context_length": 128000},
    {"provider_name": "openai", "model_name": "gpt-4o-mini", "display_name": "GPT-4o Mini", "input_price_per_million": "0.15", "output_price_per_million": "0.60", "cost_tier": "cheap", "context_length": 128000},
    {"provider_name": "openai", "model_name": "gpt-4-turbo", "display_name": "GPT-4 Turbo", "input_price_per_million": "10.00", "output_price_per_million": "30.00", "cost_tier": "premium", "context_length": 128000},
    {"provider_name": "openai", "model_name": "o1", "display_name": "o1", "input_price_per_million": "15.00", "output_price_per_million": "60.00", "cost_tier": "premium", "context_length": 200000},
    {"provider_name": "openai", "model_name": "o1-mini", "display_name": "o1 Mini", "input_price_per_million": "3.00", "output_price_per_million": "12.00", "cost_tier": "standard", "context_length": 128000},
    # Anthropic
    {"provider_name": "anthropic", "model_name": "claude-3-5-sonnet-20241022", "display_name": "Claude 3.5 Sonnet", "input_price_per_million": "3.00", "output_price_per_million": "15.00", "cost_tier": "standard", "context_length": 200000},
    {"provider_name": "anthropic", "model_name": "claude-3-5-haiku-20241022", "display_name": "Claude 3.5 Haiku", "input_price_per_million": "0.80", "output_price_per_million": "4.00", "cost_tier": "cheap", "context_length": 200000},
    {"provider_name": "anthropic", "model_name": "claude-3-opus-20240229", "display_name": "Claude 3 Opus", "input_price_per_million": "15.00", "output_price_per_million": "75.00", "cost_tier": "premium", "context_length": 200000},
    # Google
    {"provider_name": "google", "model_name": "gemini-2.0-flash", "display_name": "Gemini 2.0 Flash", "input_price_per_million": "0.10", "output_price_per_million": "0.40", "cost_tier": "cheap", "context_length": 1000000},
    {"provider_name": "google", "model_name": "gemini-1.5-pro", "display_name": "Gemini 1.5 Pro", "input_price_per_million": "1.25", "output_price_per_million": "5.00", "cost_tier": "standard", "context_length": 2000000},
    {"provider_name": "google", "model_name": "gemini-1.5-flash", "display_name": "Gemini 1.5 Flash", "input_price_per_million": "0.075", "output_price_per_million": "0.30", "cost_tier": "cheap", "context_length": 1000000},
    # DeepSeek
    {"provider_name": "deepseek", "model_name": "deepseek-chat", "display_name": "DeepSeek Chat (V3)", "input_price_per_million": "0.27", "output_price_per_million": "1.10", "cost_tier": "cheap", "context_length": 64000},
    {"provider_name": "deepseek", "model_name": "deepseek-reasoner", "display_name": "DeepSeek Reasoner (R1)", "input_price_per_million": "0.55", "output_price_per_million": "2.19", "cost_tier": "standard", "context_length": 64000},
    # Groq
    {"provider_name": "groq", "model_name": "llama-3.3-70b-versatile", "display_name": "Llama 3.3 70B", "input_price_per_million": "0.59", "output_price_per_million": "0.79", "cost_tier": "cheap", "context_length": 128000},
    {"provider_name": "groq", "model_name": "mixtral-8x7b-32768", "display_name": "Mixtral 8x7B", "input_price_per_million": "0.24", "output_price_per_million": "0.24", "cost_tier": "cheap", "context_length": 32768},
    # MiniMax
    {"provider_name": "minimax", "model_name": "MiniMax-Text-01", "display_name": "MiniMax Text 01", "input_price_per_million": "1.10", "output_price_per_million": "4.40", "cost_tier": "standard", "context_length": 1000000},
    {"provider_name": "minimax", "model_name": "MiniMax-M1", "display_name": "MiniMax M1", "input_price_per_million": "1.50", "output_price_per_million": "8.00", "cost_tier": "standard", "context_length": 1000000},
    # KIMI (Moonshot)
    {"provider_name": "kimi", "model_name": "kimi-k2", "display_name": "Kimi K2", "input_price_per_million": "0.60", "output_price_per_million": "2.40", "cost_tier": "standard", "context_length": 131072},
    {"provider_name": "kimi", "model_name": "moonshot-v1-128k", "display_name": "Moonshot V1 128K", "input_price_per_million": "0.84", "output_price_per_million": "0.84", "cost_tier": "cheap", "context_length": 128000},
    # Z.ai
    {"provider_name": "z-ai", "model_name": "z1-preview", "display_name": "Z1 Preview", "input_price_per_million": "2.00", "output_price_per_million": "8.00", "cost_tier": "standard", "context_length": 131072},
    # Qwen (Alibaba)
    {"provider_name": "qwen", "model_name": "qwen-plus", "display_name": "Qwen Plus", "input_price_per_million": "0.80", "output_price_per_million": "2.00", "cost_tier": "cheap", "context_length": 131072},
    {"provider_name": "qwen", "model_name": "qwen-max", "display_name": "Qwen Max", "input_price_per_million": "2.40", "output_price_per_million": "9.60", "cost_tier": "standard", "context_length": 32768},
    {"provider_name": "qwen", "model_name": "qwen-turbo", "display_name": "Qwen Turbo", "input_price_per_million": "0.30", "output_price_per_million": "0.60", "cost_tier": "cheap", "context_length": 131072},
    # xAI
    {"provider_name": "xai", "model_name": "grok-4-fast", "display_name": "Grok 4 Fast", "input_price_per_million": "0.20", "output_price_per_million": "0.80", "cost_tier": "cheap", "context_length": 131072},
    {"provider_name": "xai", "model_name": "grok-4", "display_name": "Grok 4", "input_price_per_million": "3.00", "output_price_per_million": "15.00", "cost_tier": "standard", "context_length": 131072},
]
