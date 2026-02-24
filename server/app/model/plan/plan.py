"""
Plan Database Models

SQLModel-based database models for persisting execution plans.
Supports plan resumption after interruption.
"""

from datetime import datetime
from enum import IntEnum
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, Integer, Text
from sqlalchemy_utils import ChoiceType
from sqlmodel import Field, JSON, SmallInteger, String
from pydantic import BaseModel

from app.model.abstract.model import AbstractModel, DefaultTimes


class PlanStatus(IntEnum):
    """Status of a plan."""
    created = 1      # Plan created, not started
    running = 2      # Plan is actively executing
    paused = 3       # Plan paused by user
    completed = 4    # All steps completed successfully
    failed = 5       # Plan failed (blocked steps)
    cancelled = 6    # Plan cancelled by user


class PlanStepStatus(IntEnum):
    """Status of a plan step."""
    not_started = 0
    in_progress = 1
    completed = 2
    blocked = 3


class PlanModel(AbstractModel, DefaultTimes, table=True):
    """
    Persisted execution plan.
    
    Stores plan metadata and step states for resume capability.
    Steps are stored as JSON for flexibility.
    """
    __tablename__ = "execution_plan"
    
    id: int = Field(default=None, primary_key=True)
    
    # References
    user_id: int = Field(index=True)
    project_id: str = Field(sa_column=Column(String(64), index=True))
    task_id: str = Field(sa_column=Column(String(64), index=True))
    plan_id: str = Field(sa_column=Column(String(128), index=True, unique=True))
    
    # Plan metadata
    title: str = Field(sa_column=Column(String(512)))
    status: int = Field(
        default=PlanStatus.created.value,
        sa_column=Column(ChoiceType(PlanStatus, SmallInteger()))
    )
    
    # Steps stored as JSON array
    # Each step: {"index": 0, "text": "...", "status": 0, "notes": "", "agent_type": "developer"}
    steps: List[Dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    
    # Progress tracking
    current_step_index: int = Field(default=0)
    total_steps: int = Field(default=0)
    completed_steps: int = Field(default=0)
    
    # Execution metadata
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "plan_id": self.plan_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "steps": self.steps,
            "current_step_index": self.current_step_index,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "progress": (self.completed_steps / self.total_steps * 100) if self.total_steps > 0 else 0,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def get_current_step(self) -> Optional[Dict[str, Any]]:
        """Get the current step to execute."""
        for step in self.steps:
            if step.get("status", 0) in [PlanStepStatus.not_started.value, PlanStepStatus.in_progress.value]:
                return step
        return None
    
    def mark_step(self, index: int, status: PlanStepStatus, notes: str = "") -> bool:
        """Mark a step with a status."""
        if 0 <= index < len(self.steps):
            self.steps[index]["status"] = status.value
            if notes:
                self.steps[index]["notes"] = notes
            
            # Update completed count
            self.completed_steps = sum(
                1 for s in self.steps if s.get("status") == PlanStepStatus.completed.value
            )
            
            # Update current step index
            for i, step in enumerate(self.steps):
                if step.get("status", 0) in [PlanStepStatus.not_started.value, PlanStepStatus.in_progress.value]:
                    self.current_step_index = i
                    break
            else:
                self.current_step_index = len(self.steps)
            
            return True
        return False


class PlanStepModel(AbstractModel, DefaultTimes, table=True):
    """
    Individual plan step history/audit trail.
    
    Optional - can be used for detailed step execution logging.
    """
    __tablename__ = "plan_step"
    
    id: int = Field(default=None, primary_key=True)
    
    # References
    plan_id: str = Field(sa_column=Column(String(128), index=True))
    step_index: int = Field(default=0)
    
    # Step content
    text: str = Field(sa_column=Column(Text))
    agent_type: Optional[str] = Field(default=None, sa_column=Column(String(64), nullable=True))
    
    # Execution
    status: int = Field(
        default=PlanStepStatus.not_started.value,
        sa_column=Column(ChoiceType(PlanStepStatus, SmallInteger()))
    )
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    result: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    
    # Timing
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    duration_seconds: Optional[float] = Field(default=None)


class PlanStepLogModel(AbstractModel, DefaultTimes, table=True):
    """
    Execution log for a plan step.
    
    Stores individual tool execution logs for detailed tracking.
    Full output is stored here and fetched on-demand.
    """
    __tablename__ = "plan_step_log"
    
    id: int = Field(default=None, primary_key=True)
    
    # References
    plan_id: int = Field(sa_column=Column(Integer, index=True))
    step_index: int = Field(sa_column=Column(Integer, index=True))
    log_index: int = Field(default=0)  # Order within step
    
    # Log metadata
    toolkit: str = Field(sa_column=Column(String(128)))
    method: str = Field(sa_column=Column(String(128)))
    summary: str = Field(sa_column=Column(Text))
    status: str = Field(default="completed", sa_column=Column(String(32)))
    
    # Full output (fetched on-demand)
    full_output: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "step_index": self.step_index,
            "log_index": self.log_index,
            "toolkit": self.toolkit,
            "method": self.method,
            "summary": self.summary,
            "status": self.status,
            "full_output": self.full_output,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Pydantic schemas for API

class PlanCreate(BaseModel):
    """Schema for creating a plan."""
    plan_id: str
    project_id: str
    task_id: str
    title: str
    steps: List[Dict[str, Any]]


class PlanUpdate(BaseModel):
    """Schema for updating a plan."""
    title: Optional[str] = None
    status: Optional[int] = None
    steps: Optional[List[Dict[str, Any]]] = None
    current_step_index: Optional[int] = None
    error_message: Optional[str] = None


class PlanStepUpdate(BaseModel):
    """Schema for updating a step."""
    status: int
    notes: Optional[str] = None
    result: Optional[str] = None


class PlanOut(BaseModel):
    """Schema for plan output."""
    id: int
    plan_id: str
    project_id: str
    task_id: str
    title: str
    status: int
    steps: List[Dict[str, Any]]
    current_step_index: int
    total_steps: int
    completed_steps: int
    progress: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
