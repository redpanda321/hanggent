"""
Watermark Usage Info Controller

Provides the /v1/watermark/usage-info endpoint that the frontend website
calls to display current usage and billing information.
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from app.component.auth import Auth, auth_must
from app.component.database import session
from app.component.stripe_config import (
    SubscriptionPlan,
    get_plan_config,
)
from app.model.user.user import User
from app.service.usage_billing_service import UsageBillingService

logger = logging.getLogger("server_watermark_controller")

router = APIRouter(prefix="/v1/watermark", tags=["Watermark Usage"])


# ---- Currency conversion rates (approximate, relative to USD) ----
_CURRENCY_RATES: dict[str, float] = {
    "usd": 1.0,
    "eur": 0.92,
    "gbp": 0.79,
    "jpy": 149.50,
    "cny": 7.24,
    "krw": 1320.0,
}


def _convert_currency(amount_usd: float, currency: str) -> float:
    """Convert a USD amount to the requested currency."""
    rate = _CURRENCY_RATES.get(currency.lower(), 1.0)
    return round(amount_usd * rate, 4)


class UsageInfoResponse(BaseModel):
    """Response model for watermark usage-info."""

    # Plan info
    plan: str
    plan_name: str

    # Token usage
    free_tokens_allowance: int
    free_tokens_used: int
    free_tokens_remaining: int
    paid_tokens_used: int
    total_tokens_used: int

    # Spending (in requested currency)
    currency: str
    total_spending: float
    spending_limit: float
    spending_remaining: float
    spending_percentage: float

    # Alerts
    alert_threshold_reached: bool
    limit_reached: bool

    # Credits
    credits: int

    # Model breakdown
    model_breakdown: dict


@router.get("/usage-info", name="watermark usage info", response_model=UsageInfoResponse)
async def get_usage_info(
    currency: str = Query("usd", description="Currency code for spending amounts (e.g. usd, eur, cny)"),
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
):
    """
    Return the authenticated user's current usage and billing information.

    This is the endpoint the frontend website calls to display usage stats
    on the pricing / dashboard pages.
    """
    user = session.get(User, auth.user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        stats = UsageBillingService.get_usage_stats(session, user)
    except Exception as e:
        logger.error("Failed to fetch usage stats", extra={
            "user_id": auth.user.id,
            "error": str(e),
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve usage information.")

    cur = currency.lower().strip()

    try:
        plan = SubscriptionPlan(user.subscription_plan or "free")
        plan_config = get_plan_config(plan)
        plan_name = plan_config.name
    except ValueError:
        plan_name = (user.subscription_plan or "free").capitalize()

    return UsageInfoResponse(
        plan=user.subscription_plan or "free",
        plan_name=plan_name,
        free_tokens_allowance=stats["free_tokens_allowance"],
        free_tokens_used=stats["free_tokens_used"],
        free_tokens_remaining=stats["free_tokens_remaining"],
        paid_tokens_used=stats["paid_tokens_used"],
        total_tokens_used=stats["total_tokens_used"],
        currency=cur,
        total_spending=_convert_currency(stats["total_spending"], cur),
        spending_limit=_convert_currency(stats["spending_limit"], cur),
        spending_remaining=_convert_currency(stats["spending_remaining"], cur),
        spending_percentage=stats["spending_percentage"],
        alert_threshold_reached=stats["alert_threshold_reached"],
        limit_reached=stats["limit_reached"],
        credits=user.credits or 0,
        model_breakdown=stats["model_breakdown"],
    )
