"""
Planning Data Models

Pydantic models for the planning system, supporting explicit step tracking
and plan management for the planning flow orchestration mode.

Models:
- PlanStepStatus: Enum for step states (not_started, in_progress, completed, blocked)
- PlanStep: Individual step with text, status, notes, and optional agent type
- Plan: Complete plan with steps, title, and progress tracking
"""

import time
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PlanStepStatus(str, Enum):
    """
    Enum defining possible statuses of a plan step.
    
    States:
    - NOT_STARTED: Step has not been started yet
    - IN_PROGRESS: Step is currently being executed
    - COMPLETED: Step finished successfully
    - BLOCKED: Step cannot proceed (dependency or error)
    """
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"

    @classmethod
    def get_all_statuses(cls) -> List[str]:
        """Return a list of all possible step status values."""
        return [status.value for status in cls]

    @classmethod
    def get_active_statuses(cls) -> List[str]:
        """Return statuses that indicate pending work (not started or in progress)."""
        return [cls.NOT_STARTED.value, cls.IN_PROGRESS.value]

    @classmethod
    def get_status_marks(cls) -> Dict[str, str]:
        """Return a mapping of statuses to their marker symbols for display."""
        return {
            cls.COMPLETED.value: "[✓]",
            cls.IN_PROGRESS.value: "[→]",
            cls.BLOCKED.value: "[!]",
            cls.NOT_STARTED.value: "[ ]",
        }

    @classmethod
    def get_status_emoji(cls) -> Dict[str, str]:
        """Return a mapping of statuses to emoji for rich display."""
        return {
            cls.COMPLETED.value: "✅",
            cls.IN_PROGRESS.value: "🔄",
            cls.BLOCKED.value: "⚠️",
            cls.NOT_STARTED.value: "⏳",
        }


class PlanStep(BaseModel):
    """
    Represents a single step in a plan.
    
    Attributes:
        index: Zero-based index of the step in the plan
        text: Description of what needs to be done
        status: Current status of the step
        notes: Optional notes about execution or results
        agent_type: Optional agent type to use (e.g., "browser", "developer")
        started_at: Timestamp when step was started
        completed_at: Timestamp when step was completed
    """
    index: int = Field(..., description="Zero-based index of the step")
    text: str = Field(..., description="Description of what needs to be done")
    status: PlanStepStatus = Field(
        default=PlanStepStatus.NOT_STARTED,
        description="Current status of the step"
    )
    notes: str = Field(default="", description="Notes about execution or results")
    agent_type: Optional[str] = Field(
        default=None, 
        description="Optional agent type to use (e.g., 'browser', 'developer', 'swe')"
    )
    started_at: Optional[float] = Field(
        default=None,
        description="Timestamp when step was started"
    )
    completed_at: Optional[float] = Field(
        default=None,
        description="Timestamp when step was completed"
    )

    def mark_in_progress(self) -> None:
        """Mark this step as in progress."""
        self.status = PlanStepStatus.IN_PROGRESS
        self.started_at = time.time()

    def mark_completed(self, notes: str = "") -> None:
        """Mark this step as completed with optional notes."""
        self.status = PlanStepStatus.COMPLETED
        self.completed_at = time.time()
        if notes:
            self.notes = notes

    def mark_blocked(self, reason: str = "") -> None:
        """Mark this step as blocked with optional reason."""
        self.status = PlanStepStatus.BLOCKED
        if reason:
            self.notes = f"Blocked: {reason}"

    @property
    def is_active(self) -> bool:
        """Check if this step is pending (not started or in progress)."""
        return self.status in [PlanStepStatus.NOT_STARTED, PlanStepStatus.IN_PROGRESS]

    @property
    def is_completed(self) -> bool:
        """Check if this step is completed."""
        return self.status == PlanStepStatus.COMPLETED

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get the duration in seconds if step has completed."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def to_display_string(self) -> str:
        """Format step for display with status marker."""
        marks = PlanStepStatus.get_status_marks()
        mark = marks.get(self.status.value, "[ ]")
        agent_info = f" [{self.agent_type.upper()}]" if self.agent_type else ""
        return f"{mark} Step {self.index + 1}{agent_info}: {self.text}"


class Plan(BaseModel):
    """
    Represents a complete plan with multiple steps.
    
    Attributes:
        plan_id: Unique identifier for the plan
        title: Human-readable title for the plan
        steps: List of plan steps
        created_at: Timestamp when plan was created
        updated_at: Timestamp when plan was last updated
        metadata: Optional additional metadata
    """
    plan_id: str = Field(..., description="Unique identifier for the plan")
    title: str = Field(..., description="Human-readable title")
    steps: List[PlanStep] = Field(default_factory=list, description="List of plan steps")
    created_at: float = Field(
        default_factory=lambda: time.time(),
        description="Timestamp when plan was created"
    )
    updated_at: float = Field(
        default_factory=lambda: time.time(),
        description="Timestamp when plan was last updated"
    )
    metadata: Dict = Field(
        default_factory=dict,
        description="Optional additional metadata"
    )

    @classmethod
    def create(
        cls, 
        plan_id: str, 
        title: str, 
        step_texts: List[str],
        metadata: Optional[Dict] = None
    ) -> "Plan":
        """
        Create a new plan from a list of step descriptions.
        
        Args:
            plan_id: Unique identifier for the plan
            title: Human-readable title
            step_texts: List of step descriptions
            metadata: Optional additional metadata
            
        Returns:
            New Plan instance with initialized steps
        """
        steps = [
            PlanStep(index=i, text=text)
            for i, text in enumerate(step_texts)
        ]
        return cls(
            plan_id=plan_id,
            title=title,
            steps=steps,
            metadata=metadata or {}
        )

    @property
    def progress(self) -> float:
        """
        Calculate completion progress as a percentage.
        
        Returns:
            Progress percentage (0-100)
        """
        if not self.steps:
            return 100.0
        completed = sum(1 for s in self.steps if s.status == PlanStepStatus.COMPLETED)
        return (completed / len(self.steps)) * 100

    @property
    def completed_steps(self) -> int:
        """Get count of completed steps."""
        return sum(1 for s in self.steps if s.status == PlanStepStatus.COMPLETED)

    @property
    def total_steps(self) -> int:
        """Get total number of steps."""
        return len(self.steps)

    @property
    def current_step(self) -> Optional[PlanStep]:
        """
        Get the current step (first active step).
        
        Returns:
            The first non-completed step, or None if all completed
        """
        for step in self.steps:
            if step.is_active:
                return step
        return None

    @property
    def current_step_index(self) -> Optional[int]:
        """Get the index of the current active step."""
        step = self.current_step
        return step.index if step else None

    @property
    def is_completed(self) -> bool:
        """Check if all steps are completed."""
        return all(s.status == PlanStepStatus.COMPLETED for s in self.steps)

    @property
    def has_blocked_steps(self) -> bool:
        """Check if any steps are blocked."""
        return any(s.status == PlanStepStatus.BLOCKED for s in self.steps)

    def get_step(self, index: int) -> Optional[PlanStep]:
        """Get step by index."""
        if 0 <= index < len(self.steps):
            return self.steps[index]
        return None

    def mark_step(
        self, 
        step_index: int, 
        status: PlanStepStatus, 
        notes: str = ""
    ) -> bool:
        """
        Mark a step with the given status.
        
        Args:
            step_index: Index of the step to mark
            status: New status for the step
            notes: Optional notes about the status change
            
        Returns:
            True if successful, False if step not found
        """
        step = self.get_step(step_index)
        if not step:
            return False
        
        step.status = status
        if notes:
            step.notes = notes
        
        if status == PlanStepStatus.IN_PROGRESS and not step.started_at:
            step.started_at = time.time()
        elif status == PlanStepStatus.COMPLETED:
            step.completed_at = time.time()
        
        self.updated_at = time.time()
        return True

    def update_steps(self, new_step_texts: List[str]) -> None:
        """
        Update the steps, preserving status of existing steps where possible.
        
        Args:
            new_step_texts: New list of step descriptions
        """
        old_steps = {s.text: s for s in self.steps}
        new_steps = []
        
        for i, text in enumerate(new_step_texts):
            if text in old_steps:
                # Preserve existing step with updated index
                old_step = old_steps[text]
                old_step.index = i
                new_steps.append(old_step)
            else:
                # Create new step
                new_steps.append(PlanStep(index=i, text=text))
        
        self.steps = new_steps
        self.updated_at = time.time()

    def to_display_string(self, include_notes: bool = False) -> str:
        """
        Format the plan for display.
        
        Args:
            include_notes: Whether to include step notes
            
        Returns:
            Formatted string representation of the plan
        """
        lines = [
            f"📋 Plan: {self.title}",
            f"   ID: {self.plan_id}",
            f"   Progress: {self.progress:.0f}% ({self.completed_steps}/{self.total_steps})",
            "",
            "Steps:"
        ]
        
        for step in self.steps:
            lines.append(f"  {step.to_display_string()}")
            if include_notes and step.notes:
                lines.append(f"     Notes: {step.notes}")
        
        return "\n".join(lines)

    def to_summary_dict(self) -> Dict:
        """
        Convert plan to a summary dictionary for API responses.
        
        Returns:
            Dictionary with plan summary information
        """
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "progress": self.progress,
            "completed_steps": self.completed_steps,
            "total_steps": self.total_steps,
            "is_completed": self.is_completed,
            "has_blocked_steps": self.has_blocked_steps,
            "current_step_index": self.current_step_index,
            "steps": [
                {
                    "index": s.index,
                    "text": s.text,
                    "status": s.status.value,
                    "notes": s.notes,
                    "agent_type": s.agent_type,
                }
                for s in self.steps
            ]
        }


class PlanningState(BaseModel):
    """
    Manages multiple plans and tracks the active plan.
    
    This is used by the PlanningToolkit to store and manage plans
    across a session.
    """
    plans: Dict[str, Plan] = Field(
        default_factory=dict,
        description="Dictionary of plans by plan_id"
    )
    active_plan_id: Optional[str] = Field(
        default=None,
        description="ID of the currently active plan"
    )

    @property
    def active_plan(self) -> Optional[Plan]:
        """Get the currently active plan."""
        if self.active_plan_id and self.active_plan_id in self.plans:
            return self.plans[self.active_plan_id]
        return None

    def add_plan(self, plan: Plan, set_active: bool = True) -> None:
        """Add a plan to the state."""
        self.plans[plan.plan_id] = plan
        if set_active:
            self.active_plan_id = plan.plan_id

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID."""
        return self.plans.get(plan_id)

    def delete_plan(self, plan_id: str) -> bool:
        """Delete a plan by ID."""
        if plan_id in self.plans:
            del self.plans[plan_id]
            if self.active_plan_id == plan_id:
                self.active_plan_id = None
            return True
        return False

    def set_active_plan(self, plan_id: str) -> bool:
        """Set the active plan by ID."""
        if plan_id in self.plans:
            self.active_plan_id = plan_id
            return True
        return False

    def list_plans(self) -> List[Dict]:
        """Get a list of all plan summaries."""
        return [plan.to_summary_dict() for plan in self.plans.values()]
