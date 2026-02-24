"""
Usage tracking API endpoints.

Provides endpoints for:
- Recording agent usage (called by backend)
- Querying usage data for dashboard
- Getting usage summaries by agent, model, and time period
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Query, APIRouter
from fastapi_babel import _
from sqlmodel import Session, select, col, func
from sqlalchemy import and_, case, cast, Date

from app.component.database import session
from app.component.auth import Auth, auth_must
from app.model.usage.usage_record import (
    UsageRecord,
    UsageRecordIn,
    UsageRecordOut,
    UsageSummaryByAgent,
    UsageSummaryByModel,
    UsageSummaryByDay,
    UsageDashboardData,
    estimate_cost,
)
from app.model.user.user import User
from app.service.usage_billing_service import UsageBillingService
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("server_usage_controller")

router = APIRouter(tags=["Usage Tracking"])


@router.post("/usage/record", name="record usage", response_model=UsageRecordOut)
@traceroot.trace()
async def record_usage(
    data: UsageRecordIn,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
) -> UsageRecordOut:
    """
    Record a new usage entry for agent execution.
    
    This endpoint is typically called by the backend after each agent step
    to track token consumption and costs.
    """
    user_id = auth.user.id
    
    try:
        # Calculate estimated cost if not provided
        estimated_cost = data.estimated_cost
        if estimated_cost == 0 and (data.input_tokens > 0 or data.output_tokens > 0):
            estimated_cost = estimate_cost(
                data.model_type,
                data.input_tokens,
                data.output_tokens
            )
        
        record = UsageRecord(
            user_id=user_id,
            task_id=data.task_id,
            project_id=data.project_id,
            agent_name=data.agent_name,
            agent_step=data.agent_step,
            model_platform=data.model_platform,
            model_type=data.model_type,
            input_tokens=data.input_tokens,
            output_tokens=data.output_tokens,
            total_tokens=data.total_tokens or (data.input_tokens + data.output_tokens),
            estimated_cost=estimated_cost,
            execution_time_ms=data.execution_time_ms,
            success=data.success,
            error_message=data.error_message,
            extra_metadata=data.metadata,
        )
        record.save(session)
        
        # Consume tokens via billing service (tracks free vs paid, triggers spending alerts)
        billing_result = {}
        try:
            user = session.get(User, user_id)
            if user and (data.input_tokens > 0 or data.output_tokens > 0):
                billing_result = UsageBillingService.consume_tokens(
                    session, user, data.model_type,
                    data.input_tokens, data.output_tokens,
                )
        except Exception as billing_err:
            logger.warning("Billing consumption failed (non-blocking)", extra={
                "user_id": user_id,
                "error": str(billing_err),
            })
        
        logger.info("Usage recorded", extra={
            "user_id": user_id,
            "task_id": data.task_id,
            "agent_name": data.agent_name,
            "total_tokens": record.total_tokens,
            "estimated_cost": estimated_cost,
            "alert_triggered": billing_result.get("alert_triggered", False),
        })
        
        # Return the record with billing alert info attached
        result = record
        # Attach billing metadata to response for frontend consumption
        response_data = UsageRecordOut.model_validate(result)
        return response_data
        
    except Exception as e:
        logger.error("Failed to record usage", extra={
            "user_id": user_id,
            "error": str(e),
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to record usage")


@router.get("/usage", name="get usage records", response_model=List[UsageRecordOut])
@traceroot.trace()
async def get_usage(
    task_id: Optional[str] = Query(None, description="Filter by task ID"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
) -> List[UsageRecordOut]:
    """
    Get usage records with optional filtering.
    """
    user_id = auth.user.id
    
    stmt = select(UsageRecord).where(
        UsageRecord.user_id == user_id,
        UsageRecord.deleted_at.is_(None),
    )
    
    if task_id:
        stmt = stmt.where(UsageRecord.task_id == task_id)
    if project_id:
        stmt = stmt.where(UsageRecord.project_id == project_id)
    if agent_name:
        stmt = stmt.where(UsageRecord.agent_name == agent_name)
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            stmt = stmt.where(UsageRecord.created_at >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            stmt = stmt.where(UsageRecord.created_at < end_dt)
        except ValueError:
            pass
    
    stmt = stmt.order_by(col(UsageRecord.created_at).desc())
    stmt = stmt.limit(limit).offset(offset)
    
    records = session.exec(stmt).all()
    
    logger.debug("Usage records retrieved", extra={
        "user_id": user_id,
        "count": len(records),
    })
    
    return records


@router.get("/usage/summary", name="get usage summary", response_model=UsageDashboardData)
@traceroot.trace()
async def get_usage_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
) -> UsageDashboardData:
    """
    Get usage summary for dashboard visualization.
    
    Returns aggregated data:
    - Total tokens and cost
    - Usage by agent
    - Usage by model
    - Usage by day
    
    Accepts either start_date/end_date (YYYY-MM-DD) or days (integer).
    If start_date is provided, it takes precedence over days.
    """
    user_id = auth.user.id
    
    # Determine date range: start_date/end_date take precedence over days
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            start_dt = datetime.now() - timedelta(days=days)
    else:
        start_dt = datetime.now() - timedelta(days=days)
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)  # inclusive
        except ValueError:
            end_dt = None
    else:
        end_dt = None
    
    try:
        # Base filter conditions
        base_conditions = [
            UsageRecord.user_id == user_id,
            UsageRecord.deleted_at.is_(None),
            UsageRecord.created_at >= start_dt,
        ]
        if end_dt:
            base_conditions.append(UsageRecord.created_at < end_dt)
        if project_id:
            base_conditions.append(UsageRecord.project_id == project_id)
        
        # Get totals
        totals_stmt = select(
            func.sum(UsageRecord.total_tokens).label("total_tokens"),
            func.sum(UsageRecord.estimated_cost).label("total_cost"),
            func.count(UsageRecord.id).label("total_calls"),
        ).where(*base_conditions)
        
        totals = session.exec(totals_stmt).first()
        
        # Get usage by agent
        by_agent_stmt = select(
            UsageRecord.agent_name,
            func.count(UsageRecord.id).label("total_calls"),
            func.sum(UsageRecord.input_tokens).label("total_input_tokens"),
            func.sum(UsageRecord.output_tokens).label("total_output_tokens"),
            func.sum(UsageRecord.total_tokens).label("total_tokens"),
            func.sum(UsageRecord.estimated_cost).label("total_cost"),
            func.avg(
                case(
                    (UsageRecord.success == True, 1),
                    else_=0,
                )
            ).label("success_rate"),
            func.avg(UsageRecord.execution_time_ms).label("avg_execution_time_ms"),
        ).where(*base_conditions).group_by(UsageRecord.agent_name)
        
        by_agent_results = session.exec(by_agent_stmt).all()
        by_agent = [
            UsageSummaryByAgent(
                agent_name=row.agent_name,
                total_calls=row.total_calls or 0,
                total_input_tokens=row.total_input_tokens or 0,
                total_output_tokens=row.total_output_tokens or 0,
                total_tokens=row.total_tokens or 0,
                total_cost=round(row.total_cost or 0, 6),
                success_rate=round((row.success_rate or 0) * 100, 2),
                avg_execution_time_ms=round(row.avg_execution_time_ms, 2) if row.avg_execution_time_ms else None,
            )
            for row in by_agent_results
        ]
        
        # Get usage by model
        by_model_stmt = select(
            UsageRecord.model_platform,
            UsageRecord.model_type,
            func.count(UsageRecord.id).label("total_calls"),
            func.sum(UsageRecord.input_tokens).label("total_input_tokens"),
            func.sum(UsageRecord.output_tokens).label("total_output_tokens"),
            func.sum(UsageRecord.total_tokens).label("total_tokens"),
            func.sum(UsageRecord.estimated_cost).label("total_cost"),
        ).where(*base_conditions).group_by(
            UsageRecord.model_platform,
            UsageRecord.model_type,
        )
        
        by_model_results = session.exec(by_model_stmt).all()
        by_model = [
            UsageSummaryByModel(
                model_platform=row.model_platform,
                model_type=row.model_type,
                total_calls=row.total_calls or 0,
                total_input_tokens=row.total_input_tokens or 0,
                total_output_tokens=row.total_output_tokens or 0,
                total_tokens=row.total_tokens or 0,
                total_cost=round(row.total_cost or 0, 6),
            )
            for row in by_model_results
        ]
        
        # Get usage by day
        by_day_stmt = select(
            cast(UsageRecord.created_at, Date).label("date"),
            func.count(UsageRecord.id).label("total_calls"),
            func.sum(UsageRecord.total_tokens).label("total_tokens"),
            func.sum(UsageRecord.estimated_cost).label("total_cost"),
        ).where(*base_conditions).group_by(
            cast(UsageRecord.created_at, Date)
        ).order_by(cast(UsageRecord.created_at, Date))
        
        by_day_results = session.exec(by_day_stmt).all()
        by_day = [
            UsageSummaryByDay(
                date=str(row.date),
                total_calls=row.total_calls or 0,
                total_tokens=row.total_tokens or 0,
                total_cost=round(row.total_cost or 0, 6),
            )
            for row in by_day_results
        ]
        
        logger.debug("Usage summary retrieved", extra={
            "user_id": user_id,
            "total_tokens": totals.total_tokens if totals else 0,
        })
        
        return UsageDashboardData(
            total_tokens=(totals.total_tokens or 0) if totals else 0,
            total_cost=round((totals.total_cost or 0), 6) if totals else 0,
            total_calls=(totals.total_calls or 0) if totals else 0,
            by_agent=by_agent,
            by_model=by_model,
            by_day=by_day,
            start_date=start_dt.strftime("%Y-%m-%d"),
            end_date=(end_dt or datetime.now()).strftime("%Y-%m-%d"),
        )
        
    except Exception as e:
        logger.error("Failed to retrieve usage summary", extra={
            "user_id": user_id,
            "error": str(e),
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve usage summary")


@router.get("/usage/task/{task_id}", name="get task usage", response_model=Dict[str, Any])
@traceroot.trace()
async def get_task_usage(
    task_id: str,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must),
) -> Dict[str, Any]:
    """
    Get detailed usage for a specific task.
    """
    user_id = auth.user.id
    
    # Get all records for this task
    stmt = select(UsageRecord).where(
        UsageRecord.user_id == user_id,
        UsageRecord.task_id == task_id,
        UsageRecord.deleted_at.is_(None),
    ).order_by(col(UsageRecord.created_at).asc())
    
    records = session.exec(stmt).all()
    
    if not records:
        return {
            "task_id": task_id,
            "total_tokens": 0,
            "total_cost": 0,
            "total_calls": 0,
            "records": [],
        }
    
    # Calculate totals
    total_tokens = sum(r.total_tokens for r in records)
    total_cost = sum(r.estimated_cost for r in records)
    
    return {
        "task_id": task_id,
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 6),
        "total_calls": len(records),
        "records": [UsageRecordOut.model_validate(r) for r in records],
    }
