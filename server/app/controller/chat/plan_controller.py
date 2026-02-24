"""
Plan Controller

REST API endpoints for plan persistence and management.
This controller handles CRUD operations for plans created by the planning flow.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlmodel import paginate
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlmodel import Session, select, desc

from app.component.auth import Auth, auth_must
from app.component.database import session
from app.model.plan.plan import PlanModel, PlanStepModel, PlanStepLogModel, PlanStatus, PlanStepStatus
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("server_plan")

router = APIRouter(prefix="/plan", tags=["Plan"])


# ==================== Request/Response Models ====================

class PlanStepIn(BaseModel):
    """Input model for plan step."""
    index: int
    title: str
    description: Optional[str] = None
    agent_type: Optional[str] = None
    status: Optional[int] = PlanStepStatus.not_started.value


class PlanCreateIn(BaseModel):
    """Input model for creating a plan."""
    project_id: str
    task_id: str
    plan_id: str
    title: str
    steps: List[PlanStepIn]


class PlanUpdateIn(BaseModel):
    """Input model for updating a plan."""
    status: Optional[int] = None
    current_step_index: Optional[int] = None
    completed_steps: Optional[int] = None


class PlanStepUpdateIn(BaseModel):
    """Input model for updating a plan step."""
    step_index: int
    status: int
    notes: Optional[str] = None


class PlanOut(BaseModel):
    """Output model for plan."""
    id: int
    user_id: int
    project_id: str
    task_id: str
    plan_id: str
    title: str
    status: int
    steps: List[Dict[str, Any]]
    current_step_index: int
    total_steps: int
    completed_steps: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Endpoints ====================

@router.post("", name="create plan", response_model=PlanOut)
@traceroot.trace()
def create_plan(
    data: PlanCreateIn,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Create a new plan."""
    user_id = auth.user.id
    
    try:
        plan = PlanModel(
            user_id=user_id,
            project_id=data.project_id,
            task_id=data.task_id,
            plan_id=data.plan_id,
            title=data.title,
            status=PlanStatus.created.value,
            steps=[step.model_dump() for step in data.steps],
            current_step_index=0,
            total_steps=len(data.steps),
            completed_steps=0,
        )
        session.add(plan)
        session.commit()
        session.refresh(plan)
        
        logger.info("Plan created", extra={
            "user_id": user_id,
            "plan_id": data.plan_id,
            "total_steps": len(data.steps),
        })
        
        return plan.to_dict()
    except Exception as e:
        session.rollback()
        logger.error("Plan creation failed", extra={
            "user_id": user_id,
            "plan_id": data.plan_id,
            "error": str(e),
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create plan")


@router.get("/by-task/{task_id}", name="get plan by task", response_model=Optional[PlanOut])
@traceroot.trace()
def get_plan_by_task(
    task_id: str,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Get the active plan for a task."""
    user_id = auth.user.id
    
    stmt = (
        select(PlanModel)
        .where(PlanModel.user_id == user_id)
        .where(PlanModel.task_id == task_id)
        .where(PlanModel.deleted_at.is_(None))
        .order_by(desc(PlanModel.created_at))
    )
    plan = session.exec(stmt).first()
    
    if not plan:
        return None
    
    return plan.to_dict()


@router.get("/incomplete", name="get incomplete plans", response_model=List[PlanOut])
@traceroot.trace()
def get_incomplete_plans(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Get all incomplete plans (CREATED, RUNNING, or PAUSED) for the current user."""
    user_id = auth.user.id
    
    incomplete_statuses = [
        PlanStatus.created.value,
        PlanStatus.running.value,
        PlanStatus.paused.value,
    ]
    
    stmt = (
        select(PlanModel)
        .where(PlanModel.user_id == user_id)
        .where(PlanModel.status.in_(incomplete_statuses))
        .where(PlanModel.deleted_at.is_(None))
        .order_by(desc(PlanModel.created_at))
    )
    
    if project_id:
        stmt = stmt.where(PlanModel.project_id == project_id)
    
    plans = session.exec(stmt).all()
    
    logger.info("Fetched incomplete plans", extra={
        "user_id": user_id,
        "count": len(plans),
        "project_id": project_id,
    })
    
    return [plan.to_dict() for plan in plans]


@router.get("/project/{project_id}", name="list plans by project")
@traceroot.trace()
def list_plans_by_project(
    project_id: str,
    status_filter: Optional[str] = Query(None, description="Filter by status: completed, failed, incomplete, all"),
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
) -> Page[PlanOut]:
    """List all plans for a project."""
    user_id = auth.user.id
    
    stmt = (
        select(PlanModel)
        .where(PlanModel.user_id == user_id)
        .where(PlanModel.project_id == project_id)
        .where(PlanModel.deleted_at.is_(None))
        .order_by(desc(PlanModel.created_at))
    )
    
    # Apply status filter
    if status_filter == "completed":
        stmt = stmt.where(PlanModel.status == PlanStatus.completed.value)
    elif status_filter == "failed":
        stmt = stmt.where(PlanModel.status == PlanStatus.failed.value)
    elif status_filter == "incomplete":
        stmt = stmt.where(PlanModel.status.in_([
            PlanStatus.created.value,
            PlanStatus.running.value,
            PlanStatus.paused.value,
        ]))
    # "all" or None means no filter
    
    return paginate(session, stmt)


@router.get("/all", name="list all plans")
@traceroot.trace()
def list_all_plans(
    status_filter: Optional[str] = Query(None, description="Filter by status: completed, failed, incomplete, all"),
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
) -> Page[PlanOut]:
    """List all plans across all projects for the current user."""
    user_id = auth.user.id
    
    stmt = (
        select(PlanModel)
        .where(PlanModel.user_id == user_id)
        .where(PlanModel.deleted_at.is_(None))
        .order_by(desc(PlanModel.created_at))
    )
    
    # Apply status filter
    if status_filter == "completed":
        stmt = stmt.where(PlanModel.status == PlanStatus.completed.value)
    elif status_filter == "failed":
        stmt = stmt.where(PlanModel.status == PlanStatus.failed.value)
    elif status_filter == "incomplete":
        stmt = stmt.where(PlanModel.status.in_([
            PlanStatus.created.value,
            PlanStatus.running.value,
            PlanStatus.paused.value,
        ]))
    
    return paginate(session, stmt)


# NOTE: This catch-all route MUST be after all static-prefix GET routes
# (/by-task, /incomplete, /project, /all) to avoid shadowing them.
@router.get("/{plan_db_id}", name="get plan", response_model=PlanOut)
@traceroot.trace()
def get_plan(
    plan_db_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Get a plan by database ID."""
    user_id = auth.user.id
    
    plan = session.get(PlanModel, plan_db_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    return plan.to_dict()


@router.put("/{plan_db_id}", name="update plan", response_model=PlanOut)
@traceroot.trace()
def update_plan(
    plan_db_id: int,
    data: PlanUpdateIn,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Update a plan."""
    user_id = auth.user.id
    
    plan = session.get(PlanModel, plan_db_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    try:
        if data.status is not None:
            plan.status = data.status
        if data.current_step_index is not None:
            plan.current_step_index = data.current_step_index
        if data.completed_steps is not None:
            plan.completed_steps = data.completed_steps
        
        session.add(plan)
        session.commit()
        session.refresh(plan)
        
        logger.info("Plan updated", extra={
            "user_id": user_id,
            "plan_id": plan.plan_id,
            "status": plan.status,
        })
        
        return plan.to_dict()
    except Exception as e:
        session.rollback()
        logger.error("Plan update failed", extra={
            "user_id": user_id,
            "plan_id": plan.plan_id,
            "error": str(e),
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update plan")


@router.put("/{plan_db_id}/step", name="update plan step", response_model=PlanOut)
@traceroot.trace()
def update_plan_step(
    plan_db_id: int,
    data: PlanStepUpdateIn,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Update a specific step in a plan."""
    user_id = auth.user.id
    
    plan = session.get(PlanModel, plan_db_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    try:
        plan.mark_step(data.step_index, data.status, data.notes)
        
        session.add(plan)
        session.commit()
        session.refresh(plan)
        
        logger.debug("Plan step updated", extra={
            "user_id": user_id,
            "plan_id": plan.plan_id,
            "step_index": data.step_index,
            "status": data.status,
        })
        
        return plan.to_dict()
    except Exception as e:
        session.rollback()
        logger.error("Plan step update failed", extra={
            "user_id": user_id,
            "plan_id": plan.plan_id,
            "step_index": data.step_index,
            "error": str(e),
        }, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update plan step")


@router.post("/{plan_db_id}/start", name="start plan", response_model=PlanOut)
@traceroot.trace()
def start_plan(
    plan_db_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Mark a plan as started/running."""
    user_id = auth.user.id
    
    plan = session.get(PlanModel, plan_db_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    try:
        plan.status = PlanStatus.running.value
        session.add(plan)
        session.commit()
        session.refresh(plan)
        
        return plan.to_dict()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Failed to start plan")


@router.post("/{plan_db_id}/complete", name="complete plan", response_model=PlanOut)
@traceroot.trace()
def complete_plan(
    plan_db_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Mark a plan as completed."""
    user_id = auth.user.id
    
    plan = session.get(PlanModel, plan_db_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    try:
        plan.status = PlanStatus.completed.value
        session.add(plan)
        session.commit()
        session.refresh(plan)
        
        logger.info("Plan completed", extra={
            "user_id": user_id,
            "plan_id": plan.plan_id,
            "completed_steps": plan.completed_steps,
            "total_steps": plan.total_steps,
        })
        
        return plan.to_dict()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Failed to complete plan")


@router.post("/{plan_db_id}/fail", name="fail plan", response_model=PlanOut)
@traceroot.trace()
def fail_plan(
    plan_db_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Mark a plan as failed."""
    user_id = auth.user.id
    
    plan = session.get(PlanModel, plan_db_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    try:
        plan.status = PlanStatus.failed.value
        session.add(plan)
        session.commit()
        session.refresh(plan)
        
        logger.info("Plan failed", extra={
            "user_id": user_id,
            "plan_id": plan.plan_id,
            "completed_steps": plan.completed_steps,
            "total_steps": plan.total_steps,
        })
        
        return plan.to_dict()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Failed to mark plan as failed")


@router.post("/{plan_db_id}/pause", name="pause plan", response_model=PlanOut)
@traceroot.trace()
def pause_plan(
    plan_db_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Mark a plan as paused."""
    user_id = auth.user.id
    
    plan = session.get(PlanModel, plan_db_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    try:
        plan.status = PlanStatus.paused.value
        session.add(plan)
        session.commit()
        session.refresh(plan)
        
        return plan.to_dict()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Failed to pause plan")


@router.delete("/{plan_db_id}", name="delete plan")
@traceroot.trace()
def delete_plan(
    plan_db_id: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Soft delete a plan."""
    user_id = auth.user.id
    
    plan = session.get(PlanModel, plan_db_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    try:
        from datetime import datetime
        plan.deleted_at = datetime.utcnow()
        session.add(plan)
        session.commit()
        
        return {"status": "deleted", "plan_id": plan.plan_id}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete plan")


# ==================== Step Log Endpoints ====================

class StepLogIn(BaseModel):
    """Input model for creating a step log."""
    step_index: int
    log_index: int = 0
    toolkit: str
    method: str
    summary: str
    status: str = "completed"
    full_output: Optional[str] = None


class StepLogOut(BaseModel):
    """Output model for step log."""
    id: int
    plan_id: int
    step_index: int
    log_index: int
    toolkit: str
    method: str
    summary: str
    status: str
    full_output: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/{plan_db_id}/logs", name="create step log", response_model=StepLogOut)
@traceroot.trace()
def create_step_log(
    plan_db_id: int,
    data: StepLogIn,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Create a new execution log for a step."""
    user_id = auth.user.id
    
    plan = session.get(PlanModel, plan_db_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    try:
        log = PlanStepLogModel(
            plan_id=plan_db_id,
            step_index=data.step_index,
            log_index=data.log_index,
            toolkit=data.toolkit,
            method=data.method,
            summary=data.summary,
            status=data.status,
            full_output=data.full_output,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        
        return log.to_dict()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create step log: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create step log")


@router.get("/{plan_db_id}/step/{step_index}/logs", name="get step logs", response_model=List[StepLogOut])
@traceroot.trace()
def get_step_logs(
    plan_db_id: int,
    step_index: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Get all execution logs for a specific step."""
    user_id = auth.user.id
    
    plan = session.get(PlanModel, plan_db_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    stmt = (
        select(PlanStepLogModel)
        .where(PlanStepLogModel.plan_id == plan_db_id)
        .where(PlanStepLogModel.step_index == step_index)
        .order_by(PlanStepLogModel.log_index)
    )
    
    logs = session.exec(stmt).all()
    return [log.to_dict() for log in logs]


@router.get("/{plan_db_id}/step/{step_index}/logs/{log_index}", name="get log full output")
@traceroot.trace()
def get_log_full_output(
    plan_db_id: int,
    step_index: int,
    log_index: int,
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Get full output for a specific log entry (on-demand fetch)."""
    user_id = auth.user.id
    
    plan = session.get(PlanModel, plan_db_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    stmt = (
        select(PlanStepLogModel)
        .where(PlanStepLogModel.plan_id == plan_db_id)
        .where(PlanStepLogModel.step_index == step_index)
        .where(PlanStepLogModel.log_index == log_index)
    )
    
    log = session.exec(stmt).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    
    return {
        "full_output": log.full_output,
        "toolkit": log.toolkit,
        "method": log.method,
    }


@router.put("/{plan_db_id}/step/{step_index}/logs/{log_index}", name="update step log")
@traceroot.trace()
def update_step_log(
    plan_db_id: int,
    step_index: int,
    log_index: int,
    data: Dict[str, Any],
    session: Session = Depends(session),
    auth: Auth = Depends(auth_must)
):
    """Update a step log (e.g., add full_output after completion)."""
    user_id = auth.user.id
    
    plan = session.get(PlanModel, plan_db_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    stmt = (
        select(PlanStepLogModel)
        .where(PlanStepLogModel.plan_id == plan_db_id)
        .where(PlanStepLogModel.step_index == step_index)
        .where(PlanStepLogModel.log_index == log_index)
    )
    
    log = session.exec(stmt).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    
    try:
        if "full_output" in data:
            log.full_output = data["full_output"]
        if "status" in data:
            log.status = data["status"]
        if "summary" in data:
            log.summary = data["summary"]
        
        session.add(log)
        session.commit()
        session.refresh(log)
        
        return log.to_dict()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Failed to update step log")
