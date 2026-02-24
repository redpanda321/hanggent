"""
Usage Billing Service

Handles token consumption, free vs paid calculation, and spending alerts.
"""
import json
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select

from app.component.stripe_config import (
    SubscriptionPlan, 
    get_plan_config, 
    calculate_token_cost,
    get_model_pricing,
)
from app.model.admin.admin_settings import AdminSettings
from app.model.user.user import User
from app.model.usage.user_usage_summary import UserUsageSummary
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("usage_billing_service")


class UsageBillingService:
    """
    Service for managing token-based billing.
    
    Handles:
    - Token consumption (free vs paid)
    - Spending tracking and limits
    - Alert notifications at 90% threshold
    """
    
    @staticmethod
    def _safe_user_plan(user: User) -> SubscriptionPlan:
        plan_raw = getattr(user, "subscription_plan", None) or SubscriptionPlan.FREE.value
        try:
            return SubscriptionPlan(plan_raw)
        except ValueError:
            return SubscriptionPlan.FREE

    @staticmethod
    def get_or_create_monthly_summary(
        session: Session, 
        user_id: int, 
        year: Optional[int] = None, 
        month: Optional[int] = None
    ) -> UserUsageSummary:
        """
        Get or create a usage summary for the user's current billing period.
        """
        now = datetime.utcnow()
        year = year or now.year
        month = month or now.month
        
        # Try to find existing summary
        statement = select(UserUsageSummary).where(
            UserUsageSummary.user_id == user_id,
            UserUsageSummary.billing_year == year,
            UserUsageSummary.billing_month == month,
        )
        summary = session.exec(statement).first()
        
        if not summary:
            # Get user's spending limit from their plan
            user = session.get(User, user_id)
            if user:
                plan = UsageBillingService._safe_user_plan(user)
                plan_config = get_plan_config(plan)
                spending_limit = user.spending_limit or plan_config.default_spending_limit
            else:
                spending_limit = 100.0
            
            summary = UserUsageSummary(
                user_id=user_id,
                billing_year=year,
                billing_month=month,
                spending_limit=spending_limit,
            )
            session.add(summary)
            session.commit()
            session.refresh(summary)
        
        return summary
    
    @staticmethod
    def get_user_free_token_allowance(user: User) -> int:
        """Get the free token allowance for a user based on their plan."""
        plan = UsageBillingService._safe_user_plan(user)
        
        plan_config = get_plan_config(plan)
        return plan_config.free_tokens
    
    @staticmethod
    def can_consume_tokens(
        session: Session, 
        user: User, 
        estimated_tokens: int
    ) -> tuple[bool, str]:
        """
        Check if user can consume more tokens.
        
        Returns (can_consume, reason_if_not)
        """
        summary = UsageBillingService.get_or_create_monthly_summary(session, user.id)
        plan_config = get_plan_config(UsageBillingService._safe_user_plan(user))
        
        # Calculate remaining free tokens
        free_allowance = plan_config.free_tokens
        free_remaining = max(0, free_allowance - summary.free_tokens_used)
        
        # If within free allowance, always allow
        if estimated_tokens <= free_remaining:
            return True, ""
        
        # For paid tokens, check if user has credits (all tiers can pay-per-use)
        if (user.credits or 0) <= 0:
            if user.subscription_plan == SubscriptionPlan.FREE.value:
                return False, "Free tokens exhausted. Top up credits or upgrade to Plus/Pro for more free tokens."
            else:
                return False, "Free tokens exhausted and no credits remaining. Top up credits to continue."
        
        # Check spending limit
        if summary.limit_reached:
            return False, f"Monthly spending limit of ${summary.spending_limit:.2f} reached. Increase your limit in settings."
        
        return True, ""
    
    @staticmethod
    def consume_tokens(
        session: Session,
        user: User,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> dict:
        """
        Consume tokens and update billing.
        
        Returns a dict with consumption details:
        {
            "success": bool,
            "free_tokens_used": int,
            "paid_tokens_used": int,
            "cost": float,
            "alert_triggered": bool,
            "limit_reached": bool,
        }
        """
        total_tokens = input_tokens + output_tokens
        summary = UsageBillingService.get_or_create_monthly_summary(session, user.id)
        plan_config = get_plan_config(UsageBillingService._safe_user_plan(user))
        
        # Calculate how many free tokens remain
        free_allowance = plan_config.free_tokens
        free_remaining = max(0, free_allowance - summary.free_tokens_used)
        
        # Split consumption between free and paid
        free_consumed = min(total_tokens, free_remaining)
        paid_consumed = total_tokens - free_consumed
        
        # Calculate cost for paid tokens (proportional split between input/output)
        cost = 0.0
        if paid_consumed > 0:
            # Estimate the ratio of input to output in paid consumption
            total = input_tokens + output_tokens
            if total > 0:
                paid_input = int((input_tokens / total) * paid_consumed)
                paid_output = paid_consumed - paid_input
            else:
                paid_input = paid_output = paid_consumed // 2
            
            cost = calculate_token_cost(model_id, paid_input, paid_output)

            # Apply global additional fee percentage
            try:
                fee_percent = AdminSettings.get_additional_fee_percent(session)
                if fee_percent > 0:
                    cost *= (1 + fee_percent / 100)
            except Exception:
                # Graceful fallback – if the table doesn't exist yet, skip fee
                pass
        
        # Update summary
        summary.total_input_tokens += input_tokens
        summary.total_output_tokens += output_tokens
        summary.free_tokens_used += free_consumed
        summary.paid_tokens_used += paid_consumed
        summary.total_spending += cost
        
        # Deduct cost from user's credit balance so "Available credits" stays accurate
        if cost > 0:
            user.credits = max(0.0, float(user.credits or 0) - cost)
            session.add(user)
        
        # Update model breakdown
        breakdown = json.loads(summary.model_usage_breakdown or "{}")
        if model_id not in breakdown:
            breakdown[model_id] = {"input": 0, "output": 0, "cost": 0.0}
        breakdown[model_id]["input"] += input_tokens
        breakdown[model_id]["output"] += output_tokens
        breakdown[model_id]["cost"] += cost
        summary.model_usage_breakdown = json.dumps(breakdown)
        
        # Check for spending alert (90% threshold)
        alert_triggered = False
        if (not summary.alert_threshold_reached and 
            summary.spending_limit > 0 and
            summary.total_spending >= summary.spending_limit * plan_config.spending_alert_threshold):
            summary.alert_threshold_reached = True
            summary.alert_sent_at = datetime.utcnow()
            alert_triggered = True
            logger.info(f"Spending alert triggered for user {user.id}: ${summary.total_spending:.2f} of ${summary.spending_limit:.2f}")
        
        # Check for spending limit
        limit_reached = False
        if (not summary.limit_reached and 
            summary.spending_limit > 0 and
            summary.total_spending >= summary.spending_limit):
            summary.limit_reached = True
            summary.limit_reached_at = datetime.utcnow()
            limit_reached = True
            logger.info(f"Spending limit reached for user {user.id}: ${summary.total_spending:.2f}")
        
        session.add(summary)
        session.commit()
        
        return {
            "success": True,
            "free_tokens_used": free_consumed,
            "paid_tokens_used": paid_consumed,
            "cost": cost,
            "alert_triggered": alert_triggered,
            "limit_reached": limit_reached,
            "total_spending": summary.total_spending,
            "spending_limit": summary.spending_limit,
        }
    
    @staticmethod
    def get_usage_stats(session: Session, user: User) -> dict:
        """
        Get current usage statistics for a user.
        """
        summary = UsageBillingService.get_or_create_monthly_summary(session, user.id)
        plan_config = get_plan_config(UsageBillingService._safe_user_plan(user))
        
        free_remaining = max(0, plan_config.free_tokens - summary.free_tokens_used)
        spending_remaining = max(0, summary.spending_limit - summary.total_spending)
        
        return {
            "billing_period": f"{summary.billing_year}-{summary.billing_month:02d}",
            "plan": user.subscription_plan or "free",
            "free_tokens_allowance": plan_config.free_tokens,
            "free_tokens_used": summary.free_tokens_used,
            "free_tokens_remaining": free_remaining,
            "paid_tokens_used": summary.paid_tokens_used,
            "total_tokens_used": summary.total_input_tokens + summary.total_output_tokens,
            "total_spending": summary.total_spending,
            "spending_limit": summary.spending_limit,
            "spending_remaining": spending_remaining,
            "spending_percentage": (summary.total_spending / summary.spending_limit * 100) if summary.spending_limit > 0 else 0,
            "alert_threshold_reached": summary.alert_threshold_reached,
            "limit_reached": summary.limit_reached,
            "model_breakdown": json.loads(summary.model_usage_breakdown or "{}"),
        }
    
    @staticmethod
    def update_spending_limit(session: Session, user: User, new_limit: float) -> bool:
        """
        Update the user's spending limit.
        """
        if new_limit < 0:
            return False
        
        # Update user's default spending limit
        user.spending_limit = new_limit
        session.add(user)
        
        # Update current month's summary
        summary = UsageBillingService.get_or_create_monthly_summary(session, user.id)
        summary.spending_limit = new_limit
        
        # Reset limit_reached if new limit is higher than current spending
        if summary.total_spending < new_limit:
            summary.limit_reached = False
            summary.limit_reached_at = None
        
        session.add(summary)
        session.commit()
        
        logger.info(f"Updated spending limit for user {user.id} to ${new_limit:.2f}")
        return True
    
    @staticmethod
    def reset_monthly_alert(session: Session, user: User) -> None:
        """
        Reset the monthly spending alert flag (called at start of new billing period).
        """
        user.monthly_spending_alert_sent = False
        session.add(user)
        session.commit()


# Singleton instance
usage_billing_service = UsageBillingService()
