"""
Planning Toolkit

A CAMEL-compatible toolkit for creating and managing task execution plans.
Supports explicit step tracking with status updates for the planning flow
orchestration mode.

Features:
- Create plans with multiple steps
- Mark steps as in_progress, completed, or blocked
- Update plan steps dynamically
- Track plan progress
- Support for agent-type annotations per step

Usage:
    toolkit = PlanningToolkit(api_task_id)
    tools = toolkit.get_tools()
    
    # Create a plan
    result = toolkit.create_plan(
        plan_id="plan_001",
        title="Build a website",
        steps=["Design mockup", "Write HTML", "Add CSS", "Test"]
    )
"""

import re
import time
from typing import Dict, List, Literal, Optional

from camel.toolkits.function_tool import FunctionTool

from app.model.plan import Plan, PlanStep, PlanStepStatus, PlanningState
from app.service.task import Agents
from app.utils.toolkit.abstract_toolkit import AbstractToolkit
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("planning_toolkit")


class PlanningToolkit(AbstractToolkit):
    """
    A CAMEL-compatible toolkit for creating and managing task execution plans.
    
    This toolkit provides agents with the ability to create structured plans,
    track progress through steps, and update plan status during execution.
    
    The planning toolkit is designed to work with the PlanningFlow for
    explicit step-by-step task execution with progress tracking.
    """
    
    agent_name: str = Agents.developer_agent  # Used by coordinator agent
    
    # Shared planning state (class-level for persistence across instances)
    _state: PlanningState = PlanningState()
    
    def __init__(
        self,
        api_task_id: str,
        agent_name: Optional[str] = None,
        state: Optional[PlanningState] = None,
    ):
        """
        Initialize the PlanningToolkit.
        
        Args:
            api_task_id: The task ID for tracking
            agent_name: Optional agent name override
            state: Optional shared planning state (for testing or isolation)
        """
        self.api_task_id = api_task_id
        if agent_name:
            self.agent_name = agent_name
        if state:
            self._state = state
    
    @property
    def plans(self) -> Dict[str, Plan]:
        """Get all plans (for compatibility with backend-manus interface)."""
        return self._state.plans
    
    @property
    def active_plan_id(self) -> Optional[str]:
        """Get the active plan ID."""
        return self._state.active_plan_id
    
    @property
    def active_plan(self) -> Optional[Plan]:
        """Get the currently active plan."""
        return self._state.active_plan
    
    def create_plan(
        self,
        plan_id: str,
        title: str,
        steps: List[str],
    ) -> str:
        """
        Create a new plan with the given steps.
        
        The plan becomes the active plan automatically.
        
        Args:
            plan_id: Unique identifier for the plan
            title: Human-readable title for the plan
            steps: List of step descriptions (can include [AGENT_TYPE] annotations)
        
        Returns:
            Success message with plan summary
        
        Example:
            create_plan(
                plan_id="web_project",
                title="Build Company Website",
                steps=[
                    "[BROWSER] Research competitor websites",
                    "[DEVELOPER] Create HTML structure",
                    "[DEVELOPER] Add CSS styling",
                    "[BROWSER] Test in browser"
                ]
            )
        """
        if plan_id in self._state.plans:
            return f"Error: Plan with ID '{plan_id}' already exists. Use update_plan to modify it."
        
        # Parse steps for agent type annotations
        parsed_steps = []
        for i, step_text in enumerate(steps):
            step = PlanStep(index=i, text=step_text)
            
            # Extract agent type from [AGENT_TYPE] annotation
            type_match = re.search(r"\[([A-Z_]+)\]", step_text)
            if type_match:
                step.agent_type = type_match.group(1).lower()
            
            parsed_steps.append(step)
        
        plan = Plan(
            plan_id=plan_id,
            title=title,
            steps=parsed_steps,
        )
        
        self._state.add_plan(plan, set_active=True)
        
        logger.info(f"Created plan '{plan_id}' with {len(steps)} steps")
        
        return f"✅ Plan created successfully!\n\n{plan.to_display_string()}"
    
    def get_plan(
        self,
        plan_id: Optional[str] = None,
    ) -> str:
        """
        Get the details of a plan.
        
        Args:
            plan_id: ID of the plan to get. If not provided, returns the active plan.
        
        Returns:
            Plan details as formatted string, or error message
        """
        target_id = plan_id or self._state.active_plan_id
        
        if not target_id:
            return "Error: No plan ID provided and no active plan set."
        
        plan = self._state.get_plan(target_id)
        if not plan:
            return f"Error: Plan with ID '{target_id}' not found."
        
        return plan.to_display_string(include_notes=True)
    
    def list_plans(self) -> str:
        """
        List all available plans with their progress.
        
        Returns:
            Formatted list of all plans
        """
        if not self._state.plans:
            return "No plans available. Use create_plan to create one."
        
        lines = ["📋 Available Plans:", ""]
        
        for plan_id, plan in self._state.plans.items():
            active_marker = " ← ACTIVE" if plan_id == self._state.active_plan_id else ""
            lines.append(
                f"  • {plan.title} (ID: {plan_id}){active_marker}"
            )
            lines.append(
                f"    Progress: {plan.progress:.0f}% ({plan.completed_steps}/{plan.total_steps})"
            )
        
        return "\n".join(lines)
    
    def set_active_plan(
        self,
        plan_id: str,
    ) -> str:
        """
        Set the active plan for subsequent operations.
        
        Args:
            plan_id: ID of the plan to set as active
        
        Returns:
            Success message or error
        """
        if self._state.set_active_plan(plan_id):
            plan = self._state.active_plan
            return f"✅ Active plan set to '{plan_id}': {plan.title}"
        else:
            return f"Error: Plan with ID '{plan_id}' not found."
    
    def mark_step(
        self,
        step_index: int,
        status: Literal["not_started", "in_progress", "completed", "blocked"],
        notes: str = "",
        plan_id: Optional[str] = None,
    ) -> str:
        """
        Mark a step with the given status.
        
        Args:
            step_index: Index of the step to mark (0-based)
            status: New status for the step
            notes: Optional notes about the status change
            plan_id: ID of the plan. If not provided, uses active plan.
        
        Returns:
            Success message with updated step info, or error
        
        Example:
            mark_step(step_index=0, status="completed", notes="Found 5 competitor sites")
        """
        target_id = plan_id or self._state.active_plan_id
        
        if not target_id:
            return "Error: No plan ID provided and no active plan set."
        
        plan = self._state.get_plan(target_id)
        if not plan:
            return f"Error: Plan with ID '{target_id}' not found."
        
        try:
            step_status = PlanStepStatus(status)
        except ValueError:
            valid = ", ".join(PlanStepStatus.get_all_statuses())
            return f"Error: Invalid status '{status}'. Valid values: {valid}"
        
        if not plan.mark_step(step_index, step_status, notes):
            return f"Error: Step index {step_index} not found in plan. Plan has {len(plan.steps)} steps (0-{len(plan.steps)-1})."
        
        step = plan.steps[step_index]
        emoji = PlanStepStatus.get_status_emoji().get(status, "")
        
        logger.info(f"Marked step {step_index} as {status} in plan '{target_id}'")
        
        result = f"{emoji} Step {step_index} marked as {status}"
        if notes:
            result += f"\n   Notes: {notes}"
        result += f"\n\nPlan progress: {plan.progress:.0f}% ({plan.completed_steps}/{plan.total_steps})"
        
        return result
    
    def update_plan(
        self,
        title: Optional[str] = None,
        steps: Optional[List[str]] = None,
        plan_id: Optional[str] = None,
    ) -> str:
        """
        Update an existing plan's title and/or steps.
        
        When updating steps, completed status is preserved for steps with matching text.
        
        Args:
            title: New title for the plan (optional)
            steps: New list of steps (optional, preserves status where possible)
            plan_id: ID of the plan to update. If not provided, uses active plan.
        
        Returns:
            Success message with updated plan info, or error
        """
        target_id = plan_id or self._state.active_plan_id
        
        if not target_id:
            return "Error: No plan ID provided and no active plan set."
        
        plan = self._state.get_plan(target_id)
        if not plan:
            return f"Error: Plan with ID '{target_id}' not found."
        
        if title:
            plan.title = title
        
        if steps:
            plan.update_steps(steps)
        
        plan.updated_at = time.time()
        
        logger.info(f"Updated plan '{target_id}'")
        
        return f"✅ Plan updated successfully!\n\n{plan.to_display_string()}"
    
    def delete_plan(
        self,
        plan_id: str,
    ) -> str:
        """
        Delete a plan.
        
        Args:
            plan_id: ID of the plan to delete
        
        Returns:
            Success message or error
        """
        if self._state.delete_plan(plan_id):
            logger.info(f"Deleted plan '{plan_id}'")
            return f"✅ Plan '{plan_id}' deleted successfully."
        else:
            return f"Error: Plan with ID '{plan_id}' not found."
    
    def get_current_step(
        self,
        plan_id: Optional[str] = None,
    ) -> str:
        """
        Get information about the current (first active) step.
        
        Args:
            plan_id: ID of the plan. If not provided, uses active plan.
        
        Returns:
            Current step info or completion message
        """
        target_id = plan_id or self._state.active_plan_id
        
        if not target_id:
            return "Error: No plan ID provided and no active plan set."
        
        plan = self._state.get_plan(target_id)
        if not plan:
            return f"Error: Plan with ID '{target_id}' not found."
        
        current = plan.current_step
        if not current:
            return f"✅ All steps completed! Plan '{plan.title}' is finished."
        
        lines = [
            f"📍 Current Step (Index: {current.index}):",
            f"   {current.to_display_string()}",
            "",
            f"Plan Progress: {plan.progress:.0f}% ({plan.completed_steps}/{plan.total_steps})"
        ]
        
        if current.agent_type:
            lines.insert(2, f"   Suggested Agent: {current.agent_type.upper()}")
        
        return "\n".join(lines)
    
    def get_tools(self) -> List[FunctionTool]:
        """
        Get all tools as CAMEL FunctionTools.
        
        Returns:
            List of FunctionTool instances for planning operations
        """
        return [
            FunctionTool(
                func=self.create_plan,
                name="create_plan",
                description=(
                    "Create a new task execution plan with steps. Steps can include [AGENT_TYPE] "
                    "annotations like '[BROWSER] Research' or '[DEVELOPER] Write code'. "
                    "The plan becomes active automatically."
                ),
            ),
            FunctionTool(
                func=self.get_plan,
                name="get_plan",
                description=(
                    "Get the details of a plan including all steps and their status. "
                    "If plan_id is not provided, returns the active plan."
                ),
            ),
            FunctionTool(
                func=self.list_plans,
                name="list_plans",
                description=(
                    "List all available plans with their progress. Shows which plan is active."
                ),
            ),
            FunctionTool(
                func=self.set_active_plan,
                name="set_active_plan",
                description=(
                    "Set a plan as the active plan for subsequent operations."
                ),
            ),
            FunctionTool(
                func=self.mark_step,
                name="mark_step",
                description=(
                    "Mark a step with a status: 'not_started', 'in_progress', 'completed', or 'blocked'. "
                    "Step index is 0-based. Optionally add notes about the execution result."
                ),
            ),
            FunctionTool(
                func=self.update_plan,
                name="update_plan",
                description=(
                    "Update a plan's title and/or steps. When updating steps, status is preserved "
                    "for steps with matching text."
                ),
            ),
            FunctionTool(
                func=self.delete_plan,
                name="delete_plan",
                description="Delete a plan by ID.",
            ),
            FunctionTool(
                func=self.get_current_step,
                name="get_current_step",
                description=(
                    "Get information about the current step that needs to be executed. "
                    "Returns the first step that is not completed."
                ),
            ),
        ]
    
    # Compatibility methods for backend-manus interface
    
    def to_param(self) -> Dict:
        """
        Get OpenAI function calling format for the planning tool.
        Compatible with backend-manus interface.
        """
        return {
            "type": "function",
            "function": {
                "name": "planning",
                "description": (
                    "A planning tool for creating and managing task execution plans. "
                    "Supports commands: create, update, list, get, set_active, mark_step, delete."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "description": "The command to execute",
                            "enum": ["create", "update", "list", "get", "set_active", "mark_step", "delete"],
                            "type": "string",
                        },
                        "plan_id": {
                            "description": "Unique identifier for the plan",
                            "type": "string",
                        },
                        "title": {
                            "description": "Title for the plan",
                            "type": "string",
                        },
                        "steps": {
                            "description": "List of plan steps",
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "step_index": {
                            "description": "Index of the step to update (0-based)",
                            "type": "integer",
                        },
                        "step_status": {
                            "description": "Status to set for a step",
                            "enum": ["not_started", "in_progress", "completed", "blocked"],
                            "type": "string",
                        },
                        "step_notes": {
                            "description": "Additional notes for a step",
                            "type": "string",
                        },
                    },
                    "required": ["command"],
                },
            },
        }
    
    async def execute(
        self,
        *,
        command: Literal["create", "update", "list", "get", "set_active", "mark_step", "delete"],
        plan_id: Optional[str] = None,
        title: Optional[str] = None,
        steps: Optional[List[str]] = None,
        step_index: Optional[int] = None,
        step_status: Optional[str] = None,
        step_notes: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Execute planning command. Compatible with backend-manus interface.
        
        This method provides the same interface as backend-manus PlanningTool
        for compatibility.
        """
        if command == "create":
            if not plan_id or not title or not steps:
                return "Error: create command requires plan_id, title, and steps"
            return self.create_plan(plan_id, title, steps)
        
        elif command == "update":
            return self.update_plan(title=title, steps=steps, plan_id=plan_id)
        
        elif command == "list":
            return self.list_plans()
        
        elif command == "get":
            return self.get_plan(plan_id)
        
        elif command == "set_active":
            if not plan_id:
                return "Error: set_active command requires plan_id"
            return self.set_active_plan(plan_id)
        
        elif command == "mark_step":
            if step_index is None or not step_status:
                return "Error: mark_step command requires step_index and step_status"
            return self.mark_step(step_index, step_status, step_notes or "", plan_id)
        
        elif command == "delete":
            if not plan_id:
                return "Error: delete command requires plan_id"
            return self.delete_plan(plan_id)
        
        else:
            return f"Error: Unknown command '{command}'"
