"""
Model Access Service

Provides model validation based on user's subscription plan.
This service checks if users are allowed to use specific AI models.
"""
from typing import Optional
from sqlmodel import Session, select
from app.model.user.user import User
from app.component.stripe_config import (
    SubscriptionPlan,
    get_plan_config,
    is_model_allowed as check_model_allowed,
)
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("model_access_service")


class ModelAccessService:
    """Service for validating model access based on subscription plans."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_user_plan(self, user_id: int) -> SubscriptionPlan:
        """Get user's current subscription plan."""
        user = self.session.get(User, user_id)
        if not user:
            logger.warning("User not found for model access check", extra={"user_id": user_id})
            return SubscriptionPlan.FREE
        
        try:
            return SubscriptionPlan(user.subscription_plan)
        except ValueError:
            logger.warning("Invalid subscription plan for user", extra={
                "user_id": user_id,
                "plan": user.subscription_plan
            })
            return SubscriptionPlan.FREE
    
    def is_model_allowed_for_user(self, user_id: int, model_id: str) -> bool:
        """
        Check if a user is allowed to use a specific model.
        
        Args:
            user_id: The user's ID
            model_id: The model identifier (e.g., "gpt-4o", "claude-3-5-sonnet-20241022")
        
        Returns:
            True if the model is allowed, False otherwise
        """
        plan = self.get_user_plan(user_id)
        allowed = check_model_allowed(plan, model_id)
        
        if not allowed:
            logger.info("Model access denied", extra={
                "user_id": user_id,
                "plan": plan.value,
                "model_id": model_id
            })
        
        return allowed
    
    def get_allowed_models(self, user_id: int) -> list[str]:
        """Get list of models allowed for a user."""
        plan = self.get_user_plan(user_id)
        config = get_plan_config(plan)
        return config.allowed_models
    
    def validate_model_routing(self, user_id: int, model_routing: dict) -> tuple[bool, Optional[str]]:
        """
        Validate all models in a model routing configuration.
        
        Args:
            user_id: The user's ID
            model_routing: Model routing configuration dict
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not model_routing:
            return True, None
        
        plan = self.get_user_plan(user_id)
        
        # Check default model
        default_model = model_routing.get("default_model")
        if default_model and not check_model_allowed(plan, default_model):
            return False, f"Model '{default_model}' is not available on your {plan.value} plan"
        
        # Check per-agent models
        agent_models = model_routing.get("agent_models", {})
        for agent_name, config in agent_models.items():
            model = config.get("model") if isinstance(config, dict) else None
            if model and not check_model_allowed(plan, model):
                return False, f"Model '{model}' for agent '{agent_name}' is not available on your {plan.value} plan"
        
        # Check complexity-based models
        complexity_routing = model_routing.get("complexity_routing", {})
        for complexity, model in complexity_routing.items():
            if model and not check_model_allowed(plan, model):
                return False, f"Model '{model}' for complexity '{complexity}' is not available on your {plan.value} plan"
        
        return True, None
    
    def filter_models_for_plan(self, models: list[str], user_id: int) -> list[str]:
        """
        Filter a list of models to only include those available on user's plan.
        
        Args:
            models: List of model IDs to filter
            user_id: The user's ID
        
        Returns:
            Filtered list of allowed models
        """
        plan = self.get_user_plan(user_id)
        return [m for m in models if check_model_allowed(plan, m)]


def validate_model_access(session: Session, user_id: int, model_id: str) -> tuple[bool, Optional[str]]:
    """
    Utility function to quickly validate model access.
    
    Args:
        session: Database session
        user_id: User ID
        model_id: Model identifier
    
    Returns:
        Tuple of (is_allowed, error_message_if_not_allowed)
    """
    service = ModelAccessService(session)
    if service.is_model_allowed_for_user(user_id, model_id):
        return True, None
    
    plan = service.get_user_plan(user_id)
    allowed_models = service.get_allowed_models(user_id)
    return False, f"Model '{model_id}' requires a higher subscription plan. Your {plan.value} plan includes: {', '.join(allowed_models)}"
