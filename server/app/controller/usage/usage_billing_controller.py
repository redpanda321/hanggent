"""
Usage Billing Controller

API endpoints for token usage statistics and spending limit management.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.component.auth import Auth, auth_must
from app.component.database import session
from app.component.stripe_config import get_all_plans_info, get_model_pricing_info, get_plan_config, SubscriptionPlan
from app.model.user.user import User
from app.service.usage_billing_service import UsageBillingService

logger = logging.getLogger("usage_billing_controller")

router = APIRouter(prefix="/usage", tags=["Usage Billing"])


class CreditBalanceResponse(BaseModel):
    """Response model for credit balance"""
    credits: float
    plan: str
    minimum_topup: float


@router.get("/balance", response_model=CreditBalanceResponse)
async def get_credit_balance(
    auth: Auth = Depends(auth_must),
    db: Session = Depends(session),
):
    """
    Get the user's current credit balance.
    
    Returns the available credits for pay-per-use and minimum top-up amount.
    """
    user = db.get(User, auth.user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get minimum top-up from plan config
    try:
        plan = SubscriptionPlan(user.subscription_plan or "free")
        plan_config = get_plan_config(plan)
        minimum_topup = plan_config.minimum_topup
    except ValueError:
        minimum_topup = 1.0
    except Exception as e:
        logger.error(f"Failed to get plan config for balance: {e}", exc_info=True)
        minimum_topup = 1.0
    
    return CreditBalanceResponse(
        credits=user.credits or 0.0,
        plan=user.subscription_plan or "free",
        minimum_topup=minimum_topup,
    )


class SpendingLimitUpdate(BaseModel):
    """Request body for updating spending limit"""
    spending_limit: float


class UsageStatsResponse(BaseModel):
    """Response model for usage statistics"""
    billing_period: str
    plan: str
    free_tokens_allowance: int
    free_tokens_used: int
    free_tokens_remaining: int
    paid_tokens_used: int
    total_tokens_used: int
    total_spending: float
    spending_limit: float
    spending_remaining: float
    spending_percentage: float
    alert_threshold_reached: bool
    limit_reached: bool
    model_breakdown: dict


@router.get("/stats", response_model=UsageStatsResponse)
async def get_usage_stats(
    auth: Auth = Depends(auth_must),
    db: Session = Depends(session),
):
    """
    Get current month's usage statistics for the authenticated user.
    
    Returns:
    - Free token allowance and usage
    - Paid token usage
    - Total spending and remaining budget
    - Alert/limit status
    - Breakdown by model
    """
    user = db.get(User, auth.user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        stats = UsageBillingService.get_usage_stats(db, user)
        return UsageStatsResponse(**stats)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get usage stats for user {auth.user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Usage statistics are temporarily unavailable. The billing system may not be fully initialized."
        )


@router.put("/spending-limit")
async def update_spending_limit(
    body: SpendingLimitUpdate,
    auth: Auth = Depends(auth_must),
    db: Session = Depends(session),
):
    """
    Update the user's monthly spending limit.
    
    Free tier users cannot set a spending limit (they have no paid tokens).
    Plus/Pro users can set their own limit.
    """
    user = db.get(User, auth.user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # All tiers can set spending limits (Free users can top up and pay-per-use)
    
    if body.spending_limit < 0:
        raise HTTPException(
            status_code=400,
            detail="Spending limit cannot be negative."
        )
    
    if body.spending_limit > 10000:
        raise HTTPException(
            status_code=400,
            detail="Spending limit cannot exceed $10,000. Contact support for higher limits."
        )
    
    success = UsageBillingService.update_spending_limit(db, user, body.spending_limit)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update spending limit")
    
    return {
        "success": True,
        "message": f"Spending limit updated to ${body.spending_limit:.2f}",
        "spending_limit": body.spending_limit,
    }


@router.get("/plans")
async def get_plans():
    """
    Get all available subscription plans with their features.
    
    Public endpoint - no authentication required.
    """
    return {
        "plans": get_all_plans_info(),
    }


@router.get("/model-pricing")
async def get_model_pricing():
    """
    Get token pricing for all available models.
    
    Returns pricing per 1M tokens (input and output).
    Public endpoint - no authentication required.
    """
    return {
        "models": get_model_pricing_info(),
    }


@router.get("/check-allowance")
async def check_token_allowance(
    estimated_tokens: int = 1000,
    auth: Auth = Depends(auth_must),
    db: Session = Depends(session),
):
    """
    Check if user can consume a certain number of tokens.
    
    Use this before making API calls to check if the user has sufficient
    allowance/budget.
    """
    user = db.get(User, auth.user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    can_consume, reason = UsageBillingService.can_consume_tokens(
        db, user, estimated_tokens
    )
    
    stats = UsageBillingService.get_usage_stats(db, user)
    
    return {
        "can_consume": can_consume,
        "reason": reason if not can_consume else None,
        "free_tokens_remaining": stats["free_tokens_remaining"],
        "spending_remaining": stats["spending_remaining"],
        "limit_reached": stats["limit_reached"],
    }
