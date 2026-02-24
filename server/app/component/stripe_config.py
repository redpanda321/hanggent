"""
Stripe Configuration for Hanggent Payment System

This module provides Stripe SDK initialization and payment plan configurations.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from app.component.environment import env
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("stripe_config")

try:
    import stripe as _stripe
except ModuleNotFoundError:  # pragma: no cover
    _stripe = None


def _is_valid_stripe_secret_key(secret_key: Optional[str]) -> bool:
    if not secret_key:
        return False
    key = secret_key.strip()
    if not key:
        return False
    if not key.startswith("sk_"):
        return False
    return len(key) >= 16


# ============================================================================
# Stripe API Configuration
# ============================================================================

def get_stripe_secret_key() -> Optional[str]:
    """Get Stripe secret key from environment"""
    return env("STRIPE_SECRET_KEY")


def get_stripe_publishable_key() -> Optional[str]:
    """Get Stripe publishable key from environment"""
    return env("STRIPE_PUBLISHABLE_KEY")


def get_stripe_webhook_secret() -> Optional[str]:
    """Get Stripe webhook secret from environment"""
    return env("STRIPE_WEBHOOK_SECRET")


def init_stripe() -> bool:
    """
    Initialize Stripe SDK with secret key.
    Returns True if Stripe is properly configured, False otherwise.
    """
    if _stripe is None:
        logger.warning("Stripe SDK not installed: `stripe` python package missing")
        return False

    secret_key = get_stripe_secret_key()
    if not secret_key:
        logger.warning("Stripe not configured: STRIPE_SECRET_KEY is missing")
        return False
    if not _is_valid_stripe_secret_key(secret_key):
        logger.warning("Stripe not configured: STRIPE_SECRET_KEY format is invalid")
        return False
    
    _stripe.api_key = secret_key.strip()
    logger.info("Stripe SDK initialized successfully")
    return True


def is_stripe_enabled() -> bool:
    """Check if Stripe is enabled (has valid configuration)"""
    return _stripe is not None and _is_valid_stripe_secret_key(get_stripe_secret_key())


def get_stripe_module():
    """Return the imported Stripe SDK module, or None if not installed."""
    return _stripe


def require_stripe():
    """Return Stripe SDK module if available+configured, else raise."""
    if not init_stripe() or _stripe is None:
        raise RuntimeError("Stripe is not available or not configured")
    return _stripe


# ============================================================================
# Subscription Plans Configuration
# ============================================================================

class SubscriptionPlan(str, Enum):
    """Available subscription plans"""
    FREE = "free"
    PLUS = "plus"
    PRO = "pro"


@dataclass
class PlanFeatures:
    """Features and limits for each plan - Token-based billing"""
    name: str
    price_monthly: float
    free_tokens: int  # Monthly free tokens included in plan
    default_spending_limit: float  # Default spending limit for pay-per-use
    spending_alert_threshold: float  # Alert at this percentage (0.0-1.0)
    minimum_topup: float  # Minimum amount for credit top-up
    allowed_models: list[str]
    support_level: str
    features: list[str]  # List of feature descriptions
    has_trial: bool
    trial_days: int
    stripe_price_id_monthly: Optional[str]


# Model pricing per 1M tokens (input/output) - Updated Jan 2026
# Format: {"model_id": (input_price_per_1m, output_price_per_1m)}
MODEL_TOKEN_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI Models
    "gpt-5": (1.25, 10.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.5-preview": (75.00, 150.00),
    "o1": (15.00, 60.00),
    "o1-mini": (1.10, 4.40),
    "o3-mini": (1.10, 4.40),
    # Anthropic Models
    "claude-opus-4-20250514": (15.00, 75.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
    # Google Models
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.0-flash": (0.10, 0.40),
    # DeepSeek Models
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
    "deepseek-v3.1": (0.20, 0.84),
    # OpenAI GPT-4.1 Models
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    # Anthropic Claude 4.5
    "claude-4-5-sonnet-20250514": (3.00, 15.00),
    # MiniMax Models
    "MiniMax-Text-01": (1.10, 4.40),
    "MiniMax-M1": (1.50, 8.00),
    # KIMI / Moonshot Models
    "kimi-k2": (0.60, 2.40),
    "moonshot-v1-128k": (0.84, 0.84),
    # Z.ai Models
    "z1-preview": (2.00, 8.00),
    # Qwen (Alibaba) Models
    "qwen-plus": (0.80, 2.00),
    "qwen-max": (2.40, 9.60),
    "qwen-turbo": (0.30, 0.60),
    # xAI Models
    "grok-4-fast": (0.20, 0.80),
    "grok-4": (3.00, 15.00),
}


def get_model_pricing(model_id: str) -> tuple[float, float]:
    """Get token pricing for a model. Returns (input_per_1m, output_per_1m)."""
    # Try exact match first
    if model_id in MODEL_TOKEN_PRICING:
        return MODEL_TOKEN_PRICING[model_id]
    # Try prefix match for versioned models
    for known_model, pricing in MODEL_TOKEN_PRICING.items():
        if model_id.startswith(known_model.split("-")[0]):
            return pricing
    # Default to gpt-4o-mini pricing if unknown
    return MODEL_TOKEN_PRICING["gpt-4o-mini"]


def calculate_token_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in dollars for token usage."""
    input_price, output_price = get_model_pricing(model_id)
    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    return input_cost + output_cost


# All available models for all plans
ALL_MODELS = [
    "gpt-4o-mini", "gpt-4o", "gpt-5", "gpt-4.5-preview", "gpt-4.1", "gpt-4.1-mini",
    "o1", "o1-mini", "o3-mini",
    "claude-3-haiku-20240307", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
    "claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-4-5-sonnet-20250514",
    "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro",
    "deepseek-chat", "deepseek-reasoner", "deepseek-v3.1",
    "MiniMax-Text-01", "MiniMax-M1",
    "kimi-k2", "moonshot-v1-128k",
    "z1-preview",
    "qwen-plus", "qwen-max", "qwen-turbo",
    "grok-4-fast", "grok-4",
]

# Plan configurations - Stripe Price IDs should be set via environment variables
# or configured in Stripe Dashboard
PLAN_CONFIGS: dict[SubscriptionPlan, PlanFeatures] = {
    SubscriptionPlan.FREE: PlanFeatures(
        name="Free",
        price_monthly=0.0,
        free_tokens=80_000,  # 80K tokens free per month
        default_spending_limit=100.0,  # Allow pay-per-use up to $100
        spending_alert_threshold=0.90,
        minimum_topup=1.0,  # Minimum $1 to add credits
        allowed_models=ALL_MODELS,  # All models available
        support_level="email",
        features=["80K tokens free", "All cloud models", "Pay-per-use (min $1)", "Email support"],
        has_trial=False,
        trial_days=0,
        stripe_price_id_monthly=None,
    ),
    SubscriptionPlan.PLUS: PlanFeatures(
        name="Plus",
        price_monthly=9.99,
        free_tokens=90_000,  # 90K tokens free per month
        default_spending_limit=100.0,  # $100 default spending limit
        spending_alert_threshold=0.90,  # Alert at 90%
        minimum_topup=1.0,
        allowed_models=ALL_MODELS,  # All models available
        support_level="priority_email",
        features=["90K tokens free", "All cloud models", "Pay-per-use", "Priority email support"],
        has_trial=False,
        trial_days=0,
        stripe_price_id_monthly=env("STRIPE_PRICE_PLUS_MONTHLY"),
    ),
    SubscriptionPlan.PRO: PlanFeatures(
        name="Pro",
        price_monthly=19.99,
        free_tokens=100_000,  # 100K tokens free per month
        default_spending_limit=500.0,  # $500 default spending limit
        spending_alert_threshold=0.90,  # Alert at 90%
        minimum_topup=1.0,
        allowed_models=ALL_MODELS,  # All models available
        support_level="high_priority",
        features=["100K tokens free", "All cloud models", "Pay-per-use", "High-priority support"],
        has_trial=False,
        trial_days=0,
        stripe_price_id_monthly=env("STRIPE_PRICE_PRO_MONTHLY"),
    ),
}


def get_plan_config(plan: SubscriptionPlan) -> PlanFeatures:
    """Get configuration for a specific plan"""
    return PLAN_CONFIGS[plan]


def get_plan_by_price_id(price_id: str) -> Optional[SubscriptionPlan]:
    """Find plan by Stripe price ID"""
    for plan, config in PLAN_CONFIGS.items():
        if config.stripe_price_id_monthly == price_id:
            return plan
    return None


def is_model_allowed(plan: SubscriptionPlan, model_id: str) -> bool:
    """Check if a model is allowed for a given plan"""
    config = get_plan_config(plan)
    # Allow if model is in the list or if it starts with an allowed model name
    return any(
        model_id == allowed or model_id.startswith(allowed.split("-")[0])
        for allowed in config.allowed_models
    )


def get_all_plans_info() -> list[dict]:
    """Get all plans information for frontend display"""
    return [
        {
            "id": plan.value,
            "name": config.name,
            "price_monthly": config.price_monthly,
            "free_tokens": config.free_tokens,
            "default_spending_limit": config.default_spending_limit,
            "minimum_topup": config.minimum_topup,
            "allowed_models": config.allowed_models,
            "support_level": config.support_level,
            "features": config.features,
            "has_trial": config.has_trial,
            "trial_days": config.trial_days,
        }
        for plan, config in PLAN_CONFIGS.items()
    ]


def get_model_pricing_info() -> list[dict]:
    """Get all model pricing for frontend display"""
    return [
        {
            "model_id": model_id,
            "input_price_per_1m": pricing[0],
            "output_price_per_1m": pricing[1],
        }
        for model_id, pricing in MODEL_TOKEN_PRICING.items()
    ]
