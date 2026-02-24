"""
Planning Flow

A step-by-step task execution flow that provides explicit planning and progress tracking.
This flow integrates with CAMEL's Workforce pattern while adding:

1. Explicit plan creation with steps
2. Step-by-step execution with status tracking  
3. Agent-type annotations for step routing
4. Progress visibility throughout execution
5. SSE streaming for real-time frontend updates
6. Database persistence for plan resumption

The PlanningFlow is an alternative execution mode to the default Workforce pattern,
providing more explicit control over task decomposition and execution order.

Usage:
    flow = PlanningFlow(
        api_task_id=task_id,
        project_id=project_id,
        task_lock=task_lock,
        agents={"developer": dev_agent, "browser": browser_agent},
        primary_agent_key="developer",
    )
    result = await flow.execute("Build a website with authentication")
"""

import asyncio
import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Union, TYPE_CHECKING

from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.types import ModelType
from pydantic import BaseModel, Field

from app.model.plan import Plan, PlanStep, PlanStepStatus, PlanningState
from app.model.chat import sse_json
from app.utils.toolkit.planning_toolkit import PlanningToolkit
from app.service.task import (
    Action,
    ActionPlanCreatedData,
    ActionPlanStepStartedData,
    ActionPlanStepCompletedData,
    ActionPlanStepBlockedData,
    ActionPlanCompletedData,
    ActionPlanResumedData,
    ActionPlanStepLogData,
    PlanStepData,
)
from utils import traceroot_wrapper as traceroot

if TYPE_CHECKING:
    from app.service.task import TaskLock
    from app.service.plan_service import PlanService
    from app.service.plan_service import PlanService

logger = traceroot.get_logger("planning_flow")


class PlanningFlowConfig(BaseModel):
    """Configuration for PlanningFlow behavior."""
    
    # Plan creation
    max_plan_iterations: int = Field(default=3, description="Max LLM calls to create a valid plan")
    default_plan_steps: List[str] = Field(
        default_factory=lambda: ["Analyze request", "Execute task", "Verify results"],
        description="Fallback steps if plan creation fails"
    )
    
    # Execution
    max_step_retries: int = Field(default=2, description="Max retries per step on failure")
    step_timeout_seconds: float = Field(default=300, description="Timeout per step execution")
    
    # Agent routing
    default_agent_key: str = Field(default="opencode", description="Default agent for untyped steps")
    
    # Summary
    generate_summary: bool = Field(default=True, description="Generate summary after completion")
    
    # SSE streaming
    emit_sse_events: bool = Field(default=True, description="Emit SSE events for frontend")
    
    # Database persistence
    persist_to_db: bool = Field(default=True, description="Persist plan to database")
    enable_resume: bool = Field(default=True, description="Enable plan resumption")


class PlanningFlow:
    """
    A flow that manages planning and execution of tasks using CAMEL agents.
    
    Unlike Workforce which uses implicit task decomposition, PlanningFlow
    creates explicit plans with numbered steps and tracks progress through
    status updates.
    
    Features:
    - Explicit step-by-step planning
    - Agent routing based on [AGENT_TYPE] annotations
    - Real-time progress tracking via SSE
    - Database persistence for resume capability
    - Step completion verification
    """
    
    def __init__(
        self,
        api_task_id: str,
        agents: Dict[str, ChatAgent],
        primary_agent_key: str = "developer",
        config: Optional[PlanningFlowConfig] = None,
        task_lock: Optional["TaskLock"] = None,
        project_id: Optional[str] = None,
        user_id: Optional[int] = None,
        api_key: Optional[str] = None,
        plan_service: Optional["PlanService"] = None,
        on_plan_created: Optional[Callable[[Plan], None]] = None,
        on_step_started: Optional[Callable[[int, PlanStep], None]] = None,
        on_step_completed: Optional[Callable[[int, PlanStep, str], None]] = None,
        on_progress_update: Optional[Callable[[Plan], None]] = None,
    ):
        """
        Initialize PlanningFlow.
        
        Args:
            api_task_id: Task ID for tracking
            agents: Dictionary of agent_key -> ChatAgent instances
            primary_agent_key: Key of the primary/default agent
            config: Optional flow configuration
            task_lock: TaskLock for SSE event emission
            project_id: Project ID for persistence
            user_id: User ID for persistence
            api_key: API key for plan service
            plan_service: Optional pre-configured plan service
            on_plan_created: Callback when plan is created
            on_step_started: Callback when step execution starts
            on_step_completed: Callback when step completes
            on_progress_update: Callback for progress updates
        """
        self.api_task_id = api_task_id
        self.agents = agents
        self.primary_agent_key = primary_agent_key
        self.config = config or PlanningFlowConfig()
        
        # SSE and persistence
        self.task_lock = task_lock
        self.project_id = project_id
        self.user_id = user_id
        self.api_key = api_key
        self._plan_service = plan_service
        
        # Callbacks
        self.on_plan_created = on_plan_created
        self.on_step_started = on_step_started
        self.on_step_completed = on_step_completed
        self.on_progress_update = on_progress_update
        
        # Planning state
        self._state = PlanningState()
        self._planning_toolkit = PlanningToolkit(
            api_task_id=api_task_id,
            state=self._state,
        )
        
        # Execution state
        self._current_step_index: Optional[int] = None
        self._is_running = False
        self._should_stop = False
        self._current_plan_id: Optional[str] = None
        self._current_step_log_index: int = 0  # Track log index per step
        
        logger.info(f"PlanningFlow initialized with {len(agents)} agents", extra={
            "api_task_id": api_task_id,
            "agents": list(agents.keys()),
            "primary_agent": primary_agent_key,
            "sse_enabled": task_lock is not None,
            "persistence_enabled": self.config.persist_to_db,
        })
    
    # ==================== SSE Emission Methods ====================
    
    async def _emit_sse(self, action: Action, data: Any) -> None:
        """Emit an SSE event if task_lock is available."""
        if not self.config.emit_sse_events or self.task_lock is None:
            return
        
        try:
            await self.task_lock.put_queue(sse_json(action, data))
        except Exception as e:
            logger.warning(f"Failed to emit SSE event: {e}", extra={
                "action": action.value if hasattr(action, 'value') else action,
                "api_task_id": self.api_task_id,
            })
    
    async def _emit_plan_created(self, plan: Plan) -> None:
        """Emit plan_created SSE event."""
        plan_data = ActionPlanCreatedData(
            task_id=self.api_task_id,
            plan_id=plan.id,
            title=plan.title,
            total_steps=len(plan.steps),
            steps=[
                PlanStepData(
                    index=step.index,
                    title=step.title,
                    description=step.description,
                    agent_type=step.agent_type,
                    status=step.status.name.lower(),
                )
                for step in plan.steps
            ],
        )
        await self._emit_sse(Action.plan_created, plan_data)
    
    async def _emit_step_started(self, step: PlanStep) -> None:
        """Emit plan_step_started SSE event."""
        step_data = ActionPlanStepStartedData(
            task_id=self.api_task_id,
            plan_id=self.active_plan.id if self.active_plan else "",
            step_index=step.index,
            step_title=step.title,
            agent_type=step.agent_type,
        )
        await self._emit_sse(Action.plan_step_started, step_data)
    
    async def _emit_step_completed(self, step: PlanStep, result: str) -> None:
        """Emit plan_step_completed SSE event."""
        plan = self.active_plan
        step_data = ActionPlanStepCompletedData(
            task_id=self.api_task_id,
            plan_id=plan.id if plan else "",
            step_index=step.index,
            step_title=step.title,
            result_preview=result[:500] if len(result) > 500 else result,
            completed_steps=plan.completed_steps if plan else 0,
            total_steps=plan.total_steps if plan else 0,
        )
        await self._emit_sse(Action.plan_step_completed, step_data)
    
    async def _emit_step_blocked(self, step: PlanStep, reason: str) -> None:
        """Emit plan_step_blocked SSE event."""
        step_data = ActionPlanStepBlockedData(
            task_id=self.api_task_id,
            plan_id=self.active_plan.id if self.active_plan else "",
            step_index=step.index,
            step_title=step.title,
            reason=reason,
        )
        await self._emit_sse(Action.plan_step_blocked, step_data)
    
    async def _emit_plan_completed(self, success: bool, summary: str) -> None:
        """Emit plan_completed SSE event."""
        plan = self.active_plan
        plan_data = ActionPlanCompletedData(
            task_id=self.api_task_id,
            plan_id=plan.id if plan else "",
            success=success,
            total_steps=plan.total_steps if plan else 0,
            completed_steps=plan.completed_steps if plan else 0,
            summary=summary[:1000] if len(summary) > 1000 else summary,
        )
        await self._emit_sse(Action.plan_completed, plan_data)
    
    async def _emit_plan_resumed(self, plan: Plan, step_index: int) -> None:
        """Emit plan_resumed SSE event."""
        plan_data = ActionPlanResumedData(
            task_id=self.api_task_id,
            plan_id=plan.id,
            resumed_from_step=step_index,
            total_steps=plan.total_steps,
            completed_steps=plan.completed_steps,
        )
        await self._emit_sse(Action.plan_resumed, plan_data)
    
    async def _emit_step_log(
        self,
        step_index: int,
        toolkit: str,
        method: str,
        summary: str,
        status: str = "running",
    ) -> None:
        """
        Emit plan_step_log SSE event for tool execution.
        
        Args:
            step_index: Current step index
            toolkit: Toolkit name (e.g., "file_toolkit", "browser_toolkit")
            method: Method name being called
            summary: Brief summary of what's happening
            status: Log status - "running", "completed", or "failed"
        """
        log_data = ActionPlanStepLogData(
            task_id=self.api_task_id,
            plan_id=self.active_plan.id if self.active_plan else "",
            step_index=step_index,
            toolkit=toolkit,
            method=method,
            summary=summary,
            status=status,
            log_index=self._current_step_log_index,
        )
        self._current_step_log_index += 1
        await self._emit_sse(Action.plan_step_log, log_data)
    
    # ==================== Persistence Methods ====================
    
    async def _persist_plan_created(self, plan: Plan) -> None:
        """Persist plan creation to database."""
        if not self.config.persist_to_db or not self._plan_service:
            return
        
        try:
            result = await self._plan_service.create_plan(
                project_id=self.project_id or "",
                task_id=self.api_task_id,
                plan_id=plan.id,
                title=plan.title,
                steps=[
                    {
                        "index": step.index,
                        "title": step.title,
                        "description": step.description,
                        "agent_type": step.agent_type,
                        "status": step.status.value,
                    }
                    for step in plan.steps
                ],
            )
            self._current_plan_id = result.get("id") if result else None
            logger.info(f"Plan persisted to database", extra={
                "plan_id": plan.id,
                "db_id": self._current_plan_id,
            })
        except Exception as e:
            logger.error(f"Failed to persist plan: {e}", extra={
                "plan_id": plan.id,
            })
    
    async def _persist_step_update(self, step: PlanStep, result: Optional[str] = None) -> None:
        """Persist step status update to database."""
        if not self.config.persist_to_db or not self._plan_service:
            return
        
        try:
            await self._plan_service.update_step(
                plan_id=self._current_plan_id or "",
                step_index=step.index,
                status=step.status.value,
                notes=result[:500] if result and len(result) > 500 else result,
            )
        except Exception as e:
            logger.error(f"Failed to persist step update: {e}", extra={
                "step_index": step.index,
            })
    
    async def _persist_plan_completed(self, success: bool) -> None:
        """Persist plan completion to database."""
        if not self.config.persist_to_db or not self._plan_service or not self._current_plan_id:
            return
        
        try:
            if success:
                await self._plan_service.mark_plan_completed(self._current_plan_id)
            else:
                await self._plan_service.mark_plan_failed(self._current_plan_id)
        except Exception as e:
            logger.error(f"Failed to persist plan completion: {e}", extra={
                "plan_id": self._current_plan_id,
            })
    
    # ==================== Properties ====================
    
    @property
    def primary_agent(self) -> ChatAgent:
        """Get the primary agent."""
        return self.agents[self.primary_agent_key]
    
    @property
    def active_plan(self) -> Optional[Plan]:
        """Get the currently active plan."""
        return self._state.active_plan
    
    @property
    def is_running(self) -> bool:
        """Check if the flow is currently executing."""
        return self._is_running
    
    @property
    def current_step_index(self) -> Optional[int]:
        """Get the current step index being executed."""
        return self._current_step_index
    
    async def emit_tool_log(
        self,
        toolkit: str,
        method: str,
        summary: str,
        status: str = "running",
    ) -> None:
        """
        Public method to emit a tool execution log during step execution.
        Called by agents during tool execution to stream logs to frontend.
        
        Args:
            toolkit: Toolkit name (e.g., "file_toolkit", "browser_toolkit")
            method: Method name being called
            summary: Brief summary of what's happening
            status: Log status - "running", "completed", or "failed"
        """
        if self._current_step_index is not None:
            await self._emit_step_log(
                step_index=self._current_step_index,
                toolkit=toolkit,
                method=method,
                summary=summary,
                status=status,
            )
    
    def get_agent(self, agent_type: Optional[str] = None) -> ChatAgent:
        """
        Get an appropriate agent for execution.
        
        Args:
            agent_type: Optional agent type from step annotation (e.g., "browser", "developer")
        
        Returns:
            ChatAgent instance for execution
        """
        if agent_type:
            # Normalize agent type to lowercase
            normalized_type = agent_type.lower()
            
            # Try direct match
            if normalized_type in self.agents:
                return self.agents[normalized_type]
            
            # Try partial match
            for key, agent in self.agents.items():
                if normalized_type in key.lower() or key.lower() in normalized_type:
                    return self.agents[key]
        
        # Fall back to default agent from config
        if self.config.default_agent_key in self.agents:
            return self.agents[self.config.default_agent_key]
        
        # Ultimate fallback to primary agent
        return self.primary_agent
    
    async def execute(
        self,
        input_text: str,
        plan_id: Optional[str] = None,
        context: str = "",
    ) -> str:
        """
        Execute the planning flow.
        
        Args:
            input_text: The task/request to execute
            plan_id: Optional custom plan ID (auto-generated if not provided)
            context: Optional context/history to include
        
        Returns:
            Execution result summary
        """
        if self._is_running:
            raise RuntimeError("PlanningFlow is already running")
        
        self._is_running = True
        self._should_stop = False
        plan_id = plan_id or f"plan_{int(time.time())}"
        
        logger.info(f"Starting PlanningFlow execution", extra={
            "api_task_id": self.api_task_id,
            "plan_id": plan_id,
            "input_preview": input_text[:100],
        })
        
        try:
            # Step 1: Create the plan
            await self._create_plan(input_text, plan_id, context)
            
            if self.active_plan is None:
                logger.error("Plan creation failed - no active plan")
                return f"Failed to create plan for: {input_text}"
            
            # Emit plan created event and persist
            await self._emit_plan_created(self.active_plan)
            await self._persist_plan_created(self.active_plan)
            
            if self.on_plan_created:
                self.on_plan_created(self.active_plan)
            
            # Step 2: Execute steps one by one
            result_parts = []
            
            while not self._should_stop:
                # Get current step
                current_step = self.active_plan.current_step
                
                if current_step is None:
                    # All steps completed
                    break
                
                self._current_step_index = current_step.index
                self._current_step_log_index = 0  # Reset log index for new step
                
                # Notify step started
                if self.on_step_started:
                    self.on_step_started(current_step.index, current_step)
                
                # Emit step started SSE event
                await self._emit_step_started(current_step)
                
                # Mark step as in progress
                self.active_plan.mark_step(current_step.index, PlanStepStatus.IN_PROGRESS)
                await self._persist_step_update(current_step)
                
                if self.on_progress_update:
                    self.on_progress_update(self.active_plan)
                
                # Execute the step
                try:
                    step_result = await self._execute_step(current_step)
                    result_parts.append(step_result)
                    
                    # Mark step as completed
                    self.active_plan.mark_step(
                        current_step.index,
                        PlanStepStatus.COMPLETED,
                        notes=step_result[:200] if len(step_result) > 200 else step_result
                    )
                    
                    # Emit step completed SSE event and persist
                    await self._emit_step_completed(current_step, step_result)
                    await self._persist_step_update(current_step, step_result)
                    
                    if self.on_step_completed:
                        self.on_step_completed(current_step.index, current_step, step_result)
                    
                except Exception as e:
                    logger.error(f"Step {current_step.index} failed: {e}")
                    self.active_plan.mark_step(
                        current_step.index,
                        PlanStepStatus.BLOCKED,
                        notes=str(e)[:200]
                    )
                    
                    # Emit step blocked SSE event and persist
                    await self._emit_step_blocked(current_step, str(e))
                    await self._persist_step_update(current_step, str(e))
                    
                    result_parts.append(f"Step {current_step.index} failed: {str(e)}")
                
                if self.on_progress_update:
                    self.on_progress_update(self.active_plan)
            
            # Step 3: Generate summary
            if self.config.generate_summary:
                summary = await self._generate_summary()
                result_parts.append(f"\n\n=== Summary ===\n{summary}")
            
            final_result = "\n\n".join(result_parts)
            
            # Emit plan completed event and persist
            await self._emit_plan_completed(success=True, summary=final_result[:500])
            await self._persist_plan_completed(success=True)
            
            return final_result
        
        except Exception as e:
            logger.error(f"PlanningFlow execution failed: {e}", exc_info=True)
            
            # Emit plan failed event and persist
            await self._emit_plan_completed(success=False, summary=str(e))
            await self._persist_plan_completed(success=False)
            
            return f"Execution failed: {str(e)}"
        
        finally:
            self._is_running = False
            self._current_step_index = None
    
    def stop(self):
        """Request the flow to stop after current step."""
        self._should_stop = True
        logger.info("PlanningFlow stop requested")
    
    async def _create_plan(
        self,
        request: str,
        plan_id: str,
        context: str = "",
    ):
        """
        Create a plan for the given request using LLM.
        
        Args:
            request: The task request
            plan_id: Plan identifier
            context: Optional context to include
        """
        logger.info(f"Creating plan with ID: {plan_id}")
        
        # Build system prompt for plan creation
        agents_info = []
        for key, agent in self.agents.items():
            agents_info.append({
                "name": key.upper(),
                "description": getattr(agent, 'description', f"Agent: {key}"),
            })
        
        system_prompt = (
            "You are a planning assistant. Create a concise, actionable plan with clear steps.\n"
            "Focus on key milestones rather than detailed sub-steps.\n"
            "Optimize for clarity and efficiency.\n"
        )
        
        if len(agents_info) > 1:
            system_prompt += (
                f"\nAvailable agents: {json.dumps(agents_info)}\n"
                "When creating steps, specify the agent using format '[AGENT_NAME]' at the start.\n"
                "For example: '[BROWSER] Research competitor websites'\n"
            )
        
        # Build user prompt
        user_prompt = f"Create a reasonable plan with clear steps to accomplish the task:\n\n{request}"
        if context:
            user_prompt = f"Context:\n{context}\n\n{user_prompt}"
        
        # Use primary agent to create plan
        planning_agent = self.primary_agent
        
        for attempt in range(self.config.max_plan_iterations):
            try:
                # Get tools for plan creation
                tools = self._planning_toolkit.get_tools()
                
                # Create message
                user_msg = BaseMessage.make_user_message(
                    role_name="User",
                    content=user_prompt,
                )
                
                # Call agent with planning tools
                response = planning_agent.step(
                    user_msg,
                    tools=tools,
                )
                
                # Process tool calls
                if response.info.get("tool_calls"):
                    for tool_call in response.info["tool_calls"]:
                        func_name = tool_call.get("function", {}).get("name")
                        if func_name == "create_plan":
                            args = tool_call.get("function", {}).get("arguments", {})
                            if isinstance(args, str):
                                args = json.loads(args)
                            
                            # Override plan_id
                            args["plan_id"] = plan_id
                            
                            # Execute plan creation
                            result = self._planning_toolkit.create_plan(**args)
                            logger.info(f"Plan created: {result[:200]}")
                            return
                
                # If no tool call, try to extract plan from response
                if response.msg and response.msg.content:
                    # Try to parse steps from natural language response
                    steps = self._extract_steps_from_response(response.msg.content)
                    if steps:
                        self._planning_toolkit.create_plan(
                            plan_id=plan_id,
                            title=f"Plan for: {request[:50]}{'...' if len(request) > 50 else ''}",
                            steps=steps,
                        )
                        logger.info(f"Plan created from response text with {len(steps)} steps")
                        return
            
            except Exception as e:
                logger.warning(f"Plan creation attempt {attempt + 1} failed: {e}")
                if attempt < self.config.max_plan_iterations - 1:
                    await asyncio.sleep(1)
        
        # Fallback to default plan
        logger.warning("Using default plan steps")
        self._planning_toolkit.create_plan(
            plan_id=plan_id,
            title=f"Plan for: {request[:50]}{'...' if len(request) > 50 else ''}",
            steps=self.config.default_plan_steps,
        )
    
    def _extract_steps_from_response(self, response: str) -> List[str]:
        """
        Extract step list from a natural language response.
        
        Args:
            response: LLM response text
        
        Returns:
            List of extracted steps
        """
        steps = []
        
        # Try numbered list pattern: "1. Step one" or "1) Step one"
        numbered_pattern = re.findall(r'^\s*\d+[\.\)]\s*(.+)$', response, re.MULTILINE)
        if numbered_pattern:
            steps = [s.strip() for s in numbered_pattern if s.strip()]
        
        # Try bullet list pattern: "- Step" or "* Step"
        if not steps:
            bullet_pattern = re.findall(r'^\s*[-\*]\s*(.+)$', response, re.MULTILINE)
            if bullet_pattern:
                steps = [s.strip() for s in bullet_pattern if s.strip()]
        
        return steps
    
    async def _execute_step(self, step: PlanStep) -> str:
        """
        Execute a single step.
        
        Args:
            step: The step to execute
        
        Returns:
            Step execution result
        """
        logger.info(f"Executing step {step.index}: {step.text[:50]}...")
        
        # Get appropriate agent
        agent = self.get_agent(step.agent_type)
        
        # Build step execution prompt
        plan_status = self.active_plan.to_display_string() if self.active_plan else ""
        
        step_prompt = f"""
CURRENT PLAN STATUS:
{plan_status}

YOUR CURRENT TASK:
You are now working on step {step.index}: "{step.text}"

Please execute this step using appropriate tools. When done, provide a summary of what you accomplished.
"""
        
        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                self._run_agent(agent, step_prompt),
                timeout=self.config.step_timeout_seconds,
            )
            return result
        
        except asyncio.TimeoutError:
            logger.warning(f"Step {step.index} timed out")
            raise TimeoutError(f"Step {step.index} timed out after {self.config.step_timeout_seconds}s")
    
    async def _run_agent(self, agent: ChatAgent, prompt: str) -> str:
        """
        Run an agent with the given prompt.
        
        Args:
            agent: ChatAgent to run
            prompt: Prompt to send
        
        Returns:
            Agent response content
        """
        user_msg = BaseMessage.make_user_message(
            role_name="User",
            content=prompt,
        )
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: agent.step(user_msg)
        )
        
        if response.msg and response.msg.content:
            return response.msg.content
        
        return "Step completed without explicit output."
    
    async def _generate_summary(self) -> str:
        """
        Generate execution summary.
        
        Returns:
            Summary text
        """
        if not self.active_plan:
            return "No plan to summarize."
        
        plan_text = self.active_plan.to_display_string(include_notes=True)
        
        summary_prompt = f"""
The plan has been completed. Here is the final plan status:

{plan_text}

Please provide a brief summary of what was accomplished.
"""
        
        try:
            result = await self._run_agent(self.primary_agent, summary_prompt)
            return result
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return f"Plan completed with {self.active_plan.completed_steps}/{self.active_plan.total_steps} steps."


class PlanningFlowBuilder:
    """Builder for creating PlanningFlow instances with fluent API."""
    
    def __init__(self, api_task_id: str):
        self.api_task_id = api_task_id
        self._agents: Dict[str, ChatAgent] = {}
        self._primary_agent_key: Optional[str] = None
        self._config = PlanningFlowConfig()
        self._callbacks: Dict[str, Any] = {}
    
    def add_agent(self, key: str, agent: ChatAgent, is_primary: bool = False) -> "PlanningFlowBuilder":
        """Add an agent to the flow."""
        self._agents[key] = agent
        if is_primary or self._primary_agent_key is None:
            self._primary_agent_key = key
        return self
    
    def with_config(self, config: PlanningFlowConfig) -> "PlanningFlowBuilder":
        """Set flow configuration."""
        self._config = config
        return self
    
    def on_plan_created(self, callback: Callable[[Plan], None]) -> "PlanningFlowBuilder":
        """Set plan created callback."""
        self._callbacks["on_plan_created"] = callback
        return self
    
    def on_step_started(self, callback: Callable[[int, PlanStep], None]) -> "PlanningFlowBuilder":
        """Set step started callback."""
        self._callbacks["on_step_started"] = callback
        return self
    
    def on_step_completed(self, callback: Callable[[int, PlanStep, str], None]) -> "PlanningFlowBuilder":
        """Set step completed callback."""
        self._callbacks["on_step_completed"] = callback
        return self
    
    def on_progress_update(self, callback: Callable[[Plan], None]) -> "PlanningFlowBuilder":
        """Set progress update callback."""
        self._callbacks["on_progress_update"] = callback
        return self
    
    def build(self) -> PlanningFlow:
        """Build the PlanningFlow instance."""
        if not self._agents:
            raise ValueError("At least one agent must be added")
        
        return PlanningFlow(
            api_task_id=self.api_task_id,
            agents=self._agents,
            primary_agent_key=self._primary_agent_key or list(self._agents.keys())[0],
            config=self._config,
            **self._callbacks,
        )
