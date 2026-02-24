"""
Stripe Payment Controller

Handles checkout sessions, webhooks, customer portal, and subscription management.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from typing import Optional
from app.component.auth import Auth, auth_must
from app.component.database import session
from app.component.stripe_config import (
    is_stripe_enabled,
    require_stripe,
    get_stripe_publishable_key,
    get_stripe_webhook_secret,
    get_all_plans_info,
    get_plan_config,
    get_plan_by_price_id,
    SubscriptionPlan,
    PLAN_CONFIGS,
)
from app.model.user.user import User
from app.component.environment import env
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("payment_controller")

# Stripe error compatibility: SDK v3+ uses stripe.StripeError, older uses stripe.error.StripeError
_stripe_module = None
try:
    import stripe as _stripe_module
except ImportError:
    pass

if _stripe_module is not None:
    _StripeError = getattr(_stripe_module, 'StripeError', None) or getattr(getattr(_stripe_module, 'error', None), 'StripeError', Exception)
    _SignatureVerificationError = getattr(_stripe_module, 'SignatureVerificationError', None) or getattr(getattr(_stripe_module, 'error', None), 'SignatureVerificationError', Exception)
else:
    _StripeError = Exception
    _SignatureVerificationError = Exception

router = APIRouter(tags=["Payment"])


def _append_query_param(url: str, key: str, value: str) -> str:
    """Append a query param to a URL string.

    We intentionally keep this as string concatenation (no URL encoding),
    because Stripe requires literal placeholders like {CHECKOUT_SESSION_ID}.
    Works for hash-based SPA URLs too (e.g. https://host/#/path?x=1).
    """
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{key}={value}"


def _stripe_error_message(err: Exception) -> str:
    try:
        msg = str(err)
        if msg:
            return msg
    except Exception:
        pass
    user_message = getattr(err, "user_message", None)
    return str(user_message or "")


def _is_invalid_stripe_customer_error(err: Exception) -> bool:
    error_msg = _stripe_error_message(err).lower()
    if not error_msg:
        return False
    if "no such customer" in error_msg:
        return True
    if "resource_missing" in error_msg and "customer" in error_msg:
        return True
    if "customer" in error_msg and "does not exist" in error_msg:
        return True
    return False


def _is_invalid_api_key_error(err: Exception) -> bool:
    error_msg = _stripe_error_message(err)
    error_msg_lower = error_msg.lower()
    return (
        "invalid api key" in error_msg
        or "api_key" in error_msg_lower
        or "api key" in error_msg_lower
        or "secret key" in error_msg_lower
    )


# ============================================================================
# Request/Response Models
# ============================================================================

class CheckoutSessionRequest(BaseModel):
    plan_id: str  # "plus" or "pro"
    billing_cycle: str = "monthly"  # "monthly" only (yearly removed)
    success_url: str
    cancel_url: str


class TopUpRequest(BaseModel):
    """Request for credit top-up."""
    amount: float  # Amount in dollars (1, 2, 5, or 10)
    success_url: str
    cancel_url: str


class TopUpResponse(BaseModel):
    """Response for top-up checkout."""
    checkout_url: str
    session_id: str


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


class PortalSessionResponse(BaseModel):
    portal_url: str


class PortalSessionRequest(BaseModel):
    return_url: Optional[str] = None


class SubscriptionStatusResponse(BaseModel):
    plan: str
    status: Optional[str]
    period_end: Optional[datetime]
    cancel_at_period_end: bool = False


class PlansResponse(BaseModel):
    plans: list[dict]
    stripe_enabled: bool
    publishable_key: Optional[str]


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/payment/plans", name="get_pricing_plans", response_model=PlansResponse)
@traceroot.trace()
def get_plans():
    """Get all available subscription plans."""
    stripe_enabled = is_stripe_enabled()
    publishable_key = get_stripe_publishable_key() if stripe_enabled else None
    
    logger.info("Pricing plans retrieved", extra={"stripe_enabled": stripe_enabled})
    return PlansResponse(
        plans=get_all_plans_info(),
        stripe_enabled=stripe_enabled,
        publishable_key=publishable_key,
    )


@router.get("/payment/subscription", name="get_subscription_status", response_model=SubscriptionStatusResponse)
@traceroot.trace()
def get_subscription_status(auth: Auth = Depends(auth_must), db: Session = Depends(session)):
    """Get current user's subscription status."""
    user: User = auth.user
    
    cancel_at_period_end = False
    
    # Check with Stripe if there's an active subscription
    if user.stripe_subscription_id and is_stripe_enabled():
        stripe = require_stripe()
        try:
            subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)
            cancel_at_period_end = subscription.cancel_at_period_end
        except _StripeError as e:
            logger.warning("Failed to retrieve subscription from Stripe", extra={
                "user_id": user.id,
                "error": str(e)
            })
    
    logger.debug("Subscription status retrieved", extra={
        "user_id": user.id,
        "plan": user.subscription_plan
    })
    
    return SubscriptionStatusResponse(
        plan=user.subscription_plan,
        status=user.subscription_status,
        period_end=user.subscription_period_end,
        cancel_at_period_end=cancel_at_period_end,
    )


@router.post("/payment/checkout", name="create_checkout_session", response_model=CheckoutSessionResponse)
@traceroot.trace()
def create_checkout_session(
    request: CheckoutSessionRequest,
    auth: Auth = Depends(auth_must),
    db: Session = Depends(session)
):
    """Create a Stripe checkout session for upgrading subscription."""
    if not is_stripe_enabled():
        logger.warning("Checkout attempted but Stripe is not configured")
        raise HTTPException(status_code=503, detail="Payment system is not configured")
    
    stripe = require_stripe()
    user: User = auth.user
    
    # Validate plan
    try:
        plan = SubscriptionPlan(request.plan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {request.plan_id}")
    
    if plan == SubscriptionPlan.FREE:
        raise HTTPException(status_code=400, detail="Cannot checkout free plan")

    # Prevent re-subscribing to the same plan the user is already on
    if (
        plan.value == user.subscription_plan
        and (user.subscription_status or "").lower() not in {"canceled", "cancelled"}
    ):
        is_still_active = True
        if user.stripe_subscription_id and is_stripe_enabled():
            try:
                current_sub = stripe.Subscription.retrieve(user.stripe_subscription_id)
                sub_status = str(getattr(current_sub, "status", "")).lower()
                cancel_scheduled = bool(getattr(current_sub, "cancel_at_period_end", False))
                if cancel_scheduled or sub_status == "canceled":
                    is_still_active = False
            except _StripeError:
                pass
        if is_still_active:
            raise HTTPException(
                status_code=409,
                detail="You are already subscribed to this plan.",
            )

    if plan == SubscriptionPlan.PLUS and user.subscription_plan == SubscriptionPlan.PRO.value:
        pro_cancellation_scheduled = False
        pro_already_cancelled = (
            (user.subscription_status or "").lower() in {"canceled", "cancelled"}
        )

        if user.stripe_subscription_id and is_stripe_enabled():
            try:
                pro_subscription = stripe.Subscription.retrieve(user.stripe_subscription_id)
                pro_cancellation_scheduled = bool(
                    getattr(pro_subscription, "cancel_at_period_end", False)
                )
                pro_already_cancelled = (
                    str(getattr(pro_subscription, "status", "")).lower() == "canceled"
                )
            except _StripeError as e:
                logger.warning(
                    "Failed to verify Pro cancellation status for Plus checkout guard",
                    extra={
                        "user_id": user.id,
                        "stripe_subscription_id": user.stripe_subscription_id,
                        "error": _stripe_error_message(e),
                    },
                )

        if not pro_cancellation_scheduled and not pro_already_cancelled:
            raise HTTPException(
                status_code=409,
                detail="Cannot switch to Plus while Pro is active. Cancel Pro first.",
            )
    
    plan_config = get_plan_config(plan)
    
    # Get the price ID (monthly only)
    price_id = plan_config.stripe_price_id_monthly
    
    if not price_id:
        logger.error("Price ID not configured for plan", extra={
            "plan": plan.value,
            "billing_cycle": request.billing_cycle
        })
        raise HTTPException(status_code=500, detail="Plan pricing not configured")
    
    # Create checkout session
    checkout_params = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": _append_query_param(
            request.success_url, "session_id", "{CHECKOUT_SESSION_ID}"
        ),
        "cancel_url": request.cancel_url,
        "metadata": {
            "user_id": str(user.id),
            "plan": plan.value,
        },
        "allow_promotion_codes": True,
    }

    if user.stripe_customer_id:
        checkout_params["customer"] = user.stripe_customer_id
    else:
        checkout_params["customer_email"] = user.email
    
    # Add trial period if plan has trial
    if plan_config.has_trial and plan_config.trial_days > 0:
        checkout_params["subscription_data"] = {
            "trial_period_days": plan_config.trial_days,
        }
    
    try:
        checkout_session = stripe.checkout.Session.create(**checkout_params)
        logger.info("Checkout session created", extra={
            "user_id": user.id,
            "plan": plan.value,
            "session_id": checkout_session.id
        })
        return CheckoutSessionResponse(
            checkout_url=checkout_session.url,
            session_id=checkout_session.id,
        )
    except _StripeError as e:
        if (
            user.stripe_customer_id
            and "customer" in checkout_params
            and _is_invalid_stripe_customer_error(e)
        ):
            logger.warning(
                "Stripe customer id invalid for checkout; clearing and retrying with customer_email",
                extra={
                    "user_id": user.id,
                    "stripe_customer_id": user.stripe_customer_id,
                    "error": _stripe_error_message(e),
                },
            )
            try:
                user.stripe_customer_id = None
                db.add(user)
                db.commit()
            except Exception:
                db.rollback()

            try:
                checkout_params.pop("customer", None)
                checkout_params["customer_email"] = user.email
                checkout_session = stripe.checkout.Session.create(**checkout_params)
                logger.info(
                    "Checkout session created after clearing invalid Stripe customer id",
                    extra={
                        "user_id": user.id,
                        "plan": plan.value,
                        "session_id": checkout_session.id,
                    },
                )
                return CheckoutSessionResponse(
                    checkout_url=checkout_session.url,
                    session_id=checkout_session.id,
                )
            except _StripeError as retry_err:
                e = retry_err

        error_msg = _stripe_error_message(e)
        logger.error("Failed to create checkout session", extra={
            "user_id": user.id,
            "error": error_msg
        })
        if _is_invalid_api_key_error(e):
            raise HTTPException(
                status_code=503,
                detail="Payment system is misconfigured. Please contact support."
            )
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.post("/payment/topup", name="create_topup_checkout", response_model=TopUpResponse)
@traceroot.trace()
def create_topup_checkout(
    request: TopUpRequest,
    auth: Auth = Depends(auth_must),
    db: Session = Depends(session)
):
    """
    Create a Stripe checkout session for one-time credit purchase.
    
    Allows users to add credits for pay-per-use after free tokens are exhausted.
    Preset amounts: $1, $2, $5, $10
    """
    if not is_stripe_enabled():
        logger.warning("Top-up attempted but Stripe is not configured")
        raise HTTPException(status_code=503, detail="Payment system is not configured")
    
    stripe = require_stripe()
    user: User = auth.user
    
    # Validate amount is one of preset values
    allowed_amounts = [1.0, 2.0, 5.0, 10.0]
    if request.amount not in allowed_amounts:
        raise HTTPException(
            status_code=400,
            detail=f"Amount must be one of: ${', $'.join(str(int(a)) for a in allowed_amounts)}"
        )
    
    # Get minimum top-up from plan config
    try:
        plan = SubscriptionPlan(user.subscription_plan or "free")
        plan_config = get_plan_config(plan)
        if request.amount < plan_config.minimum_topup:
            raise HTTPException(
                status_code=400,
                detail=f"Minimum top-up amount is ${plan_config.minimum_topup:.2f}"
            )
    except ValueError:
        pass  # Unknown plan, allow any valid amount
    
    # Create Checkout session for one-time payment
    amount_cents = int(request.amount * 100)
    
    try:
        checkout_params = {
            "mode": "payment",  # One-time payment, not subscription
            "line_items": [{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Hanggent Credits",
                        "description": f"${request.amount:.0f} credits for AI model usage",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],
            "success_url": _append_query_param(
                _append_query_param(
                    request.success_url, "session_id", "{CHECKOUT_SESSION_ID}"
                ),
                "topup",
                "success",
            ),
            "cancel_url": request.cancel_url,
            "metadata": {
                "user_id": str(user.id),
                "type": "topup",
                "amount": str(int(request.amount)),
            },
        }

        if user.stripe_customer_id:
            checkout_params["customer"] = user.stripe_customer_id
        else:
            checkout_params["customer_email"] = user.email

        checkout_session = stripe.checkout.Session.create(**checkout_params)
        logger.info("Top-up checkout session created", extra={
            "user_id": user.id,
            "amount": request.amount,
            "session_id": checkout_session.id
        })
        return TopUpResponse(
            checkout_url=checkout_session.url,
            session_id=checkout_session.id,
        )
    except _StripeError as e:
        if (
            user.stripe_customer_id
            and "customer" in checkout_params
            and _is_invalid_stripe_customer_error(e)
        ):
            logger.warning(
                "Stripe customer id invalid for top-up; clearing and retrying with customer_email",
                extra={
                    "user_id": user.id,
                    "stripe_customer_id": user.stripe_customer_id,
                    "error": _stripe_error_message(e),
                },
            )
            try:
                user.stripe_customer_id = None
                db.add(user)
                db.commit()
            except Exception:
                db.rollback()

            try:
                checkout_params.pop("customer", None)
                checkout_params["customer_email"] = user.email
                checkout_session = stripe.checkout.Session.create(**checkout_params)
                logger.info(
                    "Top-up checkout session created after clearing invalid Stripe customer id",
                    extra={
                        "user_id": user.id,
                        "amount": request.amount,
                        "session_id": checkout_session.id,
                    },
                )
                return TopUpResponse(
                    checkout_url=checkout_session.url,
                    session_id=checkout_session.id,
                )
            except _StripeError as retry_err:
                e = retry_err

        error_msg = _stripe_error_message(e)
        logger.error("Failed to create top-up checkout session", extra={
            "user_id": user.id,
            "error": error_msg
        })
        # Provide more specific error messages based on Stripe error type
        if _is_invalid_api_key_error(e):
            raise HTTPException(
                status_code=503,
                detail="Payment system is misconfigured. Please contact support."
            )
        raise HTTPException(status_code=500, detail="Failed to create checkout session")
    except Exception as e:
        logger.error("Unexpected error during top-up checkout", extra={
            "user_id": user.id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


class VerifySessionRequest(BaseModel):
    session_id: str


@router.post("/payment/verify-session", name="verify_checkout_session")
@traceroot.trace()
def verify_checkout_session(
    request: VerifySessionRequest,
    auth: Auth = Depends(auth_must),
    db: Session = Depends(session),
):
    """
    Verify and fulfill a Stripe checkout session.

    Called by the frontend after returning from Stripe to ensure credits are
    granted even if the webhook hasn't arrived yet.  Uses the same idempotency
    logic as the webhook handler, so calling this multiple times is safe.
    """
    if not is_stripe_enabled():
        raise HTTPException(status_code=503, detail="Payment system is not configured")

    stripe = require_stripe()
    user: User = auth.user

    try:
        cs_obj = stripe.checkout.Session.retrieve(request.session_id)
        if hasattr(cs_obj, "to_dict_recursive"):
            cs = cs_obj.to_dict_recursive()
        elif isinstance(cs_obj, dict):
            cs = cs_obj
        else:
            cs = dict(cs_obj)
    except _StripeError as e:
        logger.warning("verify-session: failed to retrieve session", extra={
            "session_id": request.session_id, "error": _stripe_error_message(e),
        })
        raise HTTPException(status_code=400, detail="Invalid session")
    except Exception as e:
        logger.warning("verify-session: failed to normalize session", extra={
            "session_id": request.session_id,
            "error": str(e),
        })
        raise HTTPException(status_code=400, detail="Invalid session")

    # Only process completed sessions that belong to this user
    if cs.get("status") != "complete":
        return {"status": "pending", "credits": float(user.credits or 0)}

    metadata = cs.get("metadata") or {}
    session_user_id = metadata.get("user_id")
    if session_user_id and str(user.id) != str(session_user_id):
        raise HTTPException(status_code=403, detail="Session does not belong to you")

    # Delegate to existing idempotent handlers (safe to replay).
    try:
        session_mode = cs.get("mode")
        if session_mode == "payment" and metadata.get("type") == "topup":
            _handle_topup_completed(cs, db)
        elif session_mode == "subscription":
            _handle_checkout_completed(cs, db)
        else:
            logger.info("verify-session: unsupported mode", extra={
                "session_id": request.session_id,
                "mode": session_mode,
            })
            return {"status": "pending", "credits": float(user.credits or 0)}
    except Exception as e:
        logger.error("verify-session: handler failed", extra={
            "session_id": request.session_id,
            "mode": cs.get("mode"),
            "metadata_type": metadata.get("type"),
            "metadata_user_id": session_user_id,
            "error": str(e),
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to verify session")

    # Re-read user to get the latest credits after potential update
    db.refresh(user)

    logger.info("verify-session completed", extra={
        "user_id": user.id,
        "session_id": request.session_id,
        "credits": float(user.credits or 0),
    })
    return {"status": "complete", "credits": float(user.credits or 0)}


@router.post("/payment/portal", name="create_portal_session", response_model=PortalSessionResponse)
@traceroot.trace()
def create_portal_session(
    request: Optional[PortalSessionRequest] = None,
    auth: Auth = Depends(auth_must),
    db: Session = Depends(session)
):
    """Create a Stripe billing portal session for managing subscription."""
    if not is_stripe_enabled():
        raise HTTPException(status_code=503, detail="Payment system is not configured")
    
    stripe = require_stripe()
    user: User = auth.user
    
    if not user.stripe_customer_id:
        try:
            matches = stripe.Customer.list(email=user.email, limit=10)
        except _StripeError as e:
            error_msg = str(e)
            logger.error("Failed to lookup Stripe customer by email", extra={
                "user_id": user.id,
                "error": error_msg,
            })
            if "Invalid API Key" in error_msg or "api_key" in error_msg.lower():
                raise HTTPException(
                    status_code=503,
                    detail="Payment system is misconfigured. Please contact support."
                )
            raise HTTPException(status_code=500, detail="Failed to lookup billing account")

        customers = getattr(matches, "data", None) or []
        if len(customers) == 1:
            user.stripe_customer_id = customers[0].id
            user.save(db)
            db.commit()
            logger.info("Stripe customer linked by email (single match)", extra={
                "user_id": user.id,
                "customer_id": user.stripe_customer_id,
            })
        elif len(customers) > 1:
            matched = None
            for customer in customers:
                metadata = getattr(customer, "metadata", None) or {}
                customer_user_id = None
                try:
                    customer_user_id = metadata.get("user_id")
                except Exception:
                    customer_user_id = None
                if customer_user_id == str(user.id):
                    matched = customer
                    break

            if matched is None:
                logger.warning("Multiple Stripe customers found for email; cannot disambiguate", extra={
                    "user_id": user.id,
                    "email": user.email,
                    "count": len(customers),
                })
                raise HTTPException(
                    status_code=409,
                    detail="Multiple billing accounts found. Please contact support."
                )

            user.stripe_customer_id = matched.id
            user.save(db)
            db.commit()
            logger.info("Stripe customer linked by email+metadata", extra={
                "user_id": user.id,
                "customer_id": user.stripe_customer_id,
            })
        else:
            raise HTTPException(status_code=400, detail="No billing account found")
    
    # Prefer client-provided return URL (same-origin in frontend), fallback to env APP_URL.
    default_return_url = env("APP_URL", "http://localhost:5173") + "/#/history?tab=settings&settingsTab=billing"
    if request and request.return_url and request.return_url.startswith(("http://", "https://")):
        return_url = request.return_url
    else:
        return_url = default_return_url
    
    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=return_url,
        )
        logger.info("Portal session created", extra={
            "user_id": user.id,
            "customer_id": user.stripe_customer_id
        })
        return PortalSessionResponse(portal_url=portal_session.url)
    except _StripeError as e:
        logger.error("Failed to create portal session", extra={
            "user_id": user.id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Failed to create billing portal session")


@router.post("/payment/cancel", name="cancel_subscription")
@traceroot.trace()
def cancel_subscription(auth: Auth = Depends(auth_must), db: Session = Depends(session)):
    """Cancel the current subscription at period end."""
    if not is_stripe_enabled():
        raise HTTPException(status_code=503, detail="Payment system is not configured")
    
    stripe = require_stripe()
    user: User = auth.user
    
    if not user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription to cancel")
    
    try:
        # Cancel at period end (user keeps access until period ends)
        subscription = stripe.Subscription.modify(
            user.stripe_subscription_id,
            cancel_at_period_end=True,
        )
        logger.info("Subscription cancellation scheduled", extra={
            "user_id": user.id,
            "subscription_id": user.stripe_subscription_id,
            "cancel_at": subscription.cancel_at
        })
        return {"message": "Subscription will be canceled at period end", "cancel_at": subscription.cancel_at}
    except _StripeError as e:
        logger.error("Failed to cancel subscription", extra={
            "user_id": user.id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")


@router.post("/payment/resume", name="resume_subscription")
@traceroot.trace()
def resume_subscription(auth: Auth = Depends(auth_must), db: Session = Depends(session)):
    """Resume a subscription that was scheduled for cancellation."""
    if not is_stripe_enabled():
        raise HTTPException(status_code=503, detail="Payment system is not configured")
    
    stripe = require_stripe()
    user: User = auth.user
    
    if not user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No subscription to resume")
    
    try:
        subscription = stripe.Subscription.modify(
            user.stripe_subscription_id,
            cancel_at_period_end=False,
        )
        logger.info("Subscription resumed", extra={
            "user_id": user.id,
            "subscription_id": user.stripe_subscription_id
        })
        return {"message": "Subscription resumed successfully"}
    except _StripeError as e:
        logger.error("Failed to resume subscription", extra={
            "user_id": user.id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Failed to resume subscription")


# ============================================================================
# Webhook Handler
# ============================================================================

@router.post("/payment/webhook", name="stripe_webhook")
@traceroot.trace()
async def handle_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(session)
):
    """Handle Stripe webhook events."""
    if not is_stripe_enabled():
        raise HTTPException(status_code=503, detail="Payment system is not configured")
    
    stripe = require_stripe()
    webhook_secret = get_stripe_webhook_secret()
    
    if not webhook_secret:
        logger.error("Webhook secret not configured")
        raise HTTPException(status_code=500, detail="Webhook not configured")
    
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, webhook_secret
        )
    except ValueError:
        logger.warning("Invalid webhook payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except _SignatureVerificationError:
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    event_type = event["type"]
    data = event["data"]["object"]
    
    logger.info("Webhook received", extra={"event_type": event_type})
    
    # Handle different event types
    if event_type == "checkout.session.completed":
        # Check if this is a top-up or subscription checkout
        session_mode = data.get("mode")
        if session_mode == "payment":
            _handle_topup_completed(data, db)
        else:
            _handle_checkout_completed(data, db)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(data, db)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data, db)
    elif event_type == "invoice.payment_succeeded":
        _handle_payment_succeeded(data, db)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(data, db)
    
    return {"received": True}


def _handle_checkout_completed(session_data: dict, db: Session):
    """Handle successful checkout completion for subscriptions."""
    customer_id = session_data.get("customer")
    subscription_id = session_data.get("subscription")
    metadata = session_data.get("metadata", {})
    session_id = session_data.get("id")
    
    user_id = metadata.get("user_id")
    plan = metadata.get("plan")
    
    if not user_id:
        # Try to find user by customer ID
        user = db.exec(select(User).where(User.stripe_customer_id == customer_id)).first()
    else:
        user = db.get(User, int(user_id))
    
    if not user:
        logger.error("User not found for checkout", extra={
            "customer_id": customer_id,
            "user_id": user_id
        })
        return

    if customer_id and user.stripe_customer_id != customer_id:
        user.stripe_customer_id = customer_id
    
    # Update user's subscription
    user.stripe_subscription_id = subscription_id
    if plan:
        user.subscription_plan = plan
    user.subscription_status = "active"
    
    # --- Grant credits matching the plan price ---
    credits_added = 0.0
    if plan and session_id:
        try:
            # Prevent double-fulfillment under concurrent webhook + verify-session calls.
            # Postgres-specific; safe to no-op if unsupported.
            try:
                db.exec(text("SELECT pg_advisory_xact_lock(hashtext(:sid))"), {"sid": str(session_id)})
            except Exception:
                pass

            sub_plan = SubscriptionPlan(plan)
            plan_config = get_plan_config(sub_plan)
            credits_amount = plan_config.price_monthly  # e.g. 9.99 or 19.99

            # Skip credit grant if subscription started with a free trial.
            # The first real payment will fire invoice.payment_succeeded instead.
            is_trial = False
            if subscription_id:
                try:
                    stripe = require_stripe()
                    sub_obj = stripe.Subscription.retrieve(subscription_id)
                    if getattr(sub_obj, "trial_end", None) is not None:
                        import time
                        if sub_obj.trial_end > int(time.time()):
                            is_trial = True
                except Exception as trial_err:
                    logger.warning("Could not check trial status", extra={"error": str(trial_err)})

            if not is_trial and credits_amount > 0:
                # Idempotency: check if this checkout session was already credited
                from app.model.pay.order import Order, OrderType, OrderStatus
                existing = db.exec(select(Order).where(Order.stripe_id == session_id)).first()
                if not existing:
                    order = Order(
                        user_id=user.id,
                        stripe_id=session_id,
                        order_type=OrderType.plan,
                        status=OrderStatus.success,
                        price=int(credits_amount * 100),
                        payment_method="stripe",
                    )
                    db.add(order)

                    previous_credits = float(user.credits or 0)
                    user.credits = previous_credits + credits_amount
                    credits_added = credits_amount

                    # Audit trail in UserCreditsRecord
                    from app.model.user.user_credits_record import UserCreditsRecord, CreditsChannel
                    record = UserCreditsRecord(
                        user_id=user.id,
                        amount=int(credits_amount * 100),  # cents for integer field
                        balance=0,
                        channel=CreditsChannel.paid,
                        remark=f"Subscription checkout ({plan}) ${credits_amount:.2f}",
                    )
                    db.add(record)
        except (ValueError, KeyError) as e:
            logger.warning("Could not grant checkout credits", extra={"error": str(e)})
    
    user.save(db)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # If a unique constraint/index on order.stripe_id exists, a parallel
        # webhook/verify-session path may have inserted the Order already.
        try:
            from app.model.pay.order import Order

            existing = db.exec(select(Order).where(Order.stripe_id == session_id)).first()
            if existing:
                logger.info("Checkout already processed (integrity guard)", extra={
                    "user_id": getattr(user, "id", None),
                    "session_id": session_id,
                    "plan": plan,
                })
                return
        except Exception:
            pass

        logger.error("Checkout commit failed", extra={
            "user_id": getattr(user, "id", None),
            "session_id": session_id,
            "plan": plan,
            "error": str(e),
        }, exc_info=True)
        raise
    
    logger.info("Checkout completed - subscription activated", extra={
        "user_id": user.id,
        "plan": plan,
        "subscription_id": subscription_id,
        "credits_added": credits_added,
    })


def _handle_topup_completed(session_data: dict, db: Session):
    """Handle successful top-up payment completion."""
    customer_id = session_data.get("customer")
    metadata = session_data.get("metadata", {})
    
    if metadata.get("type") != "topup":
        return
    
    user_id = metadata.get("user_id")
    amount = float(metadata.get("amount", 0))
    session_id = session_data.get("id")
    
    if not user_id or amount <= 0:
        logger.error("Invalid top-up metadata", extra={"metadata": metadata})
        return
    
    user = db.get(User, int(user_id))
    if not user:
        logger.error("User not found for top-up", extra={"user_id": user_id})
        return

    if customer_id and user.stripe_customer_id != customer_id:
        user.stripe_customer_id = customer_id
        user.save(db)
        db.commit()

    # Prevent double-fulfillment under concurrent webhook + verify-session calls.
    # Postgres-specific; safe to no-op if unsupported.
    if session_id:
        try:
            db.exec(text("SELECT pg_advisory_xact_lock(hashtext(:sid))"), {"sid": str(session_id)})
        except Exception:
            pass
    
    # Idempotency check: ensure this session hasn't already been processed
    from app.model.pay.order import Order
    existing_order = db.exec(
        select(Order).where(Order.stripe_id == session_id)
    ).first()
    if existing_order:
        logger.warning("Top-up session already processed (idempotency guard)", extra={
            "session_id": session_id,
            "user_id": user_id,
        })
        return
    
    # Create order record for idempotency tracking
    from app.model.pay.order import OrderType, OrderStatus
    order = Order(
        user_id=int(user_id),
        stripe_id=session_id,
        order_type=OrderType.addon,
        status=OrderStatus.success,
        price=int(amount * 100),  # Store in cents
        payment_method="stripe",
    )
    db.add(order)
    
    # Add credits to user's balance (dollar amount, e.g. $5.00)
    credits_to_add = float(amount)
    previous_credits = float(user.credits or 0)
    user.credits = previous_credits + credits_to_add

    # Audit trail in UserCreditsRecord so top-up credits appear in credit history
    from app.model.user.user_credits_record import UserCreditsRecord, CreditsChannel
    credit_record = UserCreditsRecord(
        user_id=int(user_id),
        amount=int(amount * 100),  # cents for integer field
        balance=0,
        channel=CreditsChannel.paid,
        remark=f"Top-up ${amount:.2f}",
    )
    db.add(credit_record)

    user.save(db)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # If a unique constraint/index on order.stripe_id exists, a parallel
        # webhook/verify-session path may have inserted the Order already.
        try:
            from app.model.pay.order import Order

            existing_order = db.exec(select(Order).where(Order.stripe_id == session_id)).first()
            if existing_order:
                logger.info("Top-up already processed (integrity guard)", extra={
                    "session_id": session_id,
                    "user_id": user_id,
                    "amount": amount,
                })
                return
        except Exception:
            pass

        logger.error("Top-up commit failed", extra={
            "session_id": session_id,
            "user_id": user_id,
            "amount": amount,
            "error": str(e),
        }, exc_info=True)
        raise
    
    logger.info("Top-up completed - credits added", extra={
        "user_id": user.id,
        "amount": amount,
        "previous_credits": previous_credits,
        "new_credits": user.credits,
        "session_id": session_id
    })


def _handle_subscription_updated(subscription_data: dict, db: Session):
    """Handle subscription updates (plan changes, renewals, etc.)."""
    customer_id = subscription_data.get("customer")
    subscription_id = subscription_data.get("id")
    status = subscription_data.get("status")
    current_period_end = subscription_data.get("current_period_end")
    
    user = db.exec(select(User).where(User.stripe_customer_id == customer_id)).first()
    if not user:
        logger.warning("User not found for subscription update", extra={
            "customer_id": customer_id
        })
        return
    
    # Determine plan from subscription items
    items = subscription_data.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        plan = get_plan_by_price_id(price_id)
        if plan:
            user.subscription_plan = plan.value
    
    user.stripe_subscription_id = subscription_id
    user.subscription_status = status
    if current_period_end:
        user.subscription_period_end = datetime.fromtimestamp(current_period_end)
    
    user.save(db)
    db.commit()
    
    logger.info("Subscription updated", extra={
        "user_id": user.id,
        "status": status,
        "plan": user.subscription_plan
    })


def _handle_subscription_deleted(subscription_data: dict, db: Session):
    """Handle subscription cancellation/deletion."""
    customer_id = subscription_data.get("customer")
    
    user = db.exec(select(User).where(User.stripe_customer_id == customer_id)).first()
    if not user:
        logger.warning("User not found for subscription deletion", extra={
            "customer_id": customer_id
        })
        return
    
    # Reset to free plan
    user.subscription_plan = SubscriptionPlan.FREE.value
    user.stripe_subscription_id = None
    user.subscription_status = "canceled"
    user.subscription_period_end = None
    user.save(db)
    db.commit()
    
    logger.info("Subscription deleted - reverted to free plan", extra={
        "user_id": user.id
    })


def _handle_payment_succeeded(invoice_data: dict, db: Session):
    """Handle successful payment — grants credits matching plan price on renewal."""
    customer_id = invoice_data.get("customer")
    subscription_id = invoice_data.get("subscription")
    invoice_id = invoice_data.get("id")  # e.g. "in_1abc..."
    
    user = db.exec(select(User).where(User.stripe_customer_id == customer_id)).first()
    if not user:
        return
    
    # Reset monthly usage summary for new billing period
    credits_added = 0.0
    try:
        plan = SubscriptionPlan(user.subscription_plan)
        plan_config = get_plan_config(plan)
        
        # Update subscription status on successful payment
        user.subscription_status = "active"
        user.monthly_spending_alert_sent = False
        
        # --- Grant credits matching the plan price ---
        credits_amount = plan_config.price_monthly  # 9.99 or 19.99
        if credits_amount > 0 and invoice_id:
            from app.model.pay.order import Order, OrderType, OrderStatus
            # Idempotency: one credit grant per invoice
            existing = db.exec(select(Order).where(Order.stripe_id == invoice_id)).first()
            if not existing:
                order = Order(
                    user_id=user.id,
                    stripe_id=invoice_id,
                    order_type=OrderType.plan,
                    status=OrderStatus.success,
                    price=int(credits_amount * 100),
                    payment_method="stripe",
                )
                db.add(order)

                previous_credits = float(user.credits or 0)
                user.credits = previous_credits + credits_amount
                credits_added = credits_amount

                # Audit trail
                from app.model.user.user_credits_record import UserCreditsRecord, CreditsChannel
                record = UserCreditsRecord(
                    user_id=user.id,
                    amount=int(credits_amount * 100),
                    balance=0,
                    channel=CreditsChannel.paid,
                    remark=f"Subscription renewal ({plan.value}) ${credits_amount:.2f}",
                )
                db.add(record)
        
        user.save(db)
        db.commit()
        
        logger.info("Payment succeeded - subscription renewed", extra={
            "user_id": user.id,
            "plan": user.subscription_plan,
            "free_tokens": plan_config.free_tokens,
            "credits_added": credits_added,
            "invoice_id": invoice_id,
        })
    except (ValueError, KeyError):
        logger.warning("Invalid subscription plan on payment success", extra={
            "user_id": user.id,
            "plan": user.subscription_plan
        })


def _handle_payment_failed(invoice_data: dict, db: Session):
    """Handle failed payment."""
    customer_id = invoice_data.get("customer")
    
    user = db.exec(select(User).where(User.stripe_customer_id == customer_id)).first()
    if not user:
        return
    
    user.subscription_status = "past_due"
    user.save(db)
    db.commit()
    
    logger.warning("Payment failed", extra={
        "user_id": user.id,
        "customer_id": customer_id
    })
