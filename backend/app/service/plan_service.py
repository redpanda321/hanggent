"""
Plan Persistence Service

Handles saving, updating, and resuming plans from the database.
Used by PlanningFlow to persist state for resume capability.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx

from app.component.environment import env
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("plan_service")


class PlanService:
    """
    Service for persisting plans to the server database.
    
    Communicates with the server API to store plan state,
    enabling plan resumption after interruption.
    """
    
    def __init__(self, api_key: str, server_url: Optional[str] = None):
        """
        Initialize the plan service.
        
        Args:
            api_key: API key for server authentication
            server_url: Server API URL (defaults to env setting)
        """
        self.api_key = api_key
        self.server_url = server_url or env.get("HANGGENT_SERVER_URL", "http://localhost:3001")
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.server_url,
                headers=self.headers,
                timeout=30.0,
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def create_plan(
        self,
        plan_id: str,
        project_id: str,
        task_id: str,
        user_id: int,
        title: str,
        steps: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new plan in the database.
        
        Args:
            plan_id: Unique plan identifier
            project_id: Project this plan belongs to
            task_id: Task this plan is for
            user_id: User who created the plan
            title: Plan title
            steps: List of step dictionaries
        
        Returns:
            Created plan data or None on failure
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/plan",
                json={
                    "plan_id": plan_id,
                    "project_id": project_id,
                    "task_id": task_id,
                    "user_id": user_id,
                    "title": title,
                    "steps": steps,
                    "total_steps": len(steps),
                    "status": 1,  # PlanStatus.created
                },
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Plan created: {plan_id}")
                return data
            else:
                logger.error(f"Failed to create plan: {response.status_code} {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating plan: {e}")
            return None
    
    async def update_plan(
        self,
        plan_id: str,
        **updates: Any,
    ) -> bool:
        """
        Update a plan in the database.
        
        Args:
            plan_id: Plan identifier
            **updates: Fields to update (status, steps, current_step_index, etc.)
        
        Returns:
            True if successful
        """
        try:
            client = await self._get_client()
            response = await client.patch(
                f"/api/plan/{plan_id}",
                json=updates,
            )
            
            if response.status_code == 200:
                logger.debug(f"Plan updated: {plan_id}")
                return True
            else:
                logger.error(f"Failed to update plan: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating plan: {e}")
            return False
    
    async def update_step(
        self,
        plan_id: str,
        step_index: int,
        status: str,
        notes: str = "",
        result: str = "",
    ) -> bool:
        """
        Update a specific step in a plan.
        
        Args:
            plan_id: Plan identifier
            step_index: Index of step to update
            status: New status (not_started, in_progress, completed, blocked)
            notes: Optional notes about the step
            result: Optional result from step execution
        
        Returns:
            True if successful
        """
        try:
            client = await self._get_client()
            response = await client.patch(
                f"/api/plan/{plan_id}/step/{step_index}",
                json={
                    "status": status,
                    "notes": notes,
                    "result": result,
                },
            )
            
            if response.status_code == 200:
                logger.debug(f"Step {step_index} updated in plan {plan_id}")
                return True
            else:
                logger.error(f"Failed to update step: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating step: {e}")
            return False
    
    async def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a plan by ID.
        
        Args:
            plan_id: Plan identifier
        
        Returns:
            Plan data or None if not found
        """
        try:
            client = await self._get_client()
            response = await client.get(f"/api/plan/{plan_id}")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            else:
                logger.error(f"Failed to get plan: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting plan: {e}")
            return None
    
    async def get_active_plan(
        self,
        project_id: str,
        task_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the active (non-completed) plan for a project/task.
        
        Args:
            project_id: Project identifier
            task_id: Optional task identifier
        
        Returns:
            Active plan data or None
        """
        try:
            client = await self._get_client()
            params = {"project_id": project_id}
            if task_id:
                params["task_id"] = task_id
            
            response = await client.get("/api/plan/active", params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data if data else None
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting active plan: {e}")
            return None
    
    async def list_plans(
        self,
        project_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List plans for a project.
        
        Args:
            project_id: Project identifier
            limit: Maximum number of plans to return
            offset: Offset for pagination
        
        Returns:
            List of plan data
        """
        try:
            client = await self._get_client()
            response = await client.get(
                "/api/plan/list",
                params={
                    "project_id": project_id,
                    "limit": limit,
                    "offset": offset,
                },
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error listing plans: {e}")
            return []
    
    async def mark_plan_started(self, plan_id: str) -> bool:
        """Mark a plan as started (running)."""
        return await self.update_plan(
            plan_id,
            status=2,  # PlanStatus.running
            started_at=datetime.now().isoformat(),
        )
    
    async def mark_plan_completed(self, plan_id: str, summary: str = "") -> bool:
        """Mark a plan as completed."""
        return await self.update_plan(
            plan_id,
            status=4,  # PlanStatus.completed
            completed_at=datetime.now().isoformat(),
        )
    
    async def mark_plan_failed(self, plan_id: str, error_message: str) -> bool:
        """Mark a plan as failed."""
        return await self.update_plan(
            plan_id,
            status=5,  # PlanStatus.failed
            error_message=error_message,
        )
    
    async def mark_plan_paused(self, plan_id: str) -> bool:
        """Mark a plan as paused."""
        return await self.update_plan(
            plan_id,
            status=3,  # PlanStatus.paused
        )


# Convenience functions for sync usage

def create_plan_sync(
    api_key: str,
    plan_id: str,
    project_id: str,
    task_id: str,
    user_id: int,
    title: str,
    steps: List[Dict[str, Any]],
    server_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Sync wrapper for create_plan."""
    service = PlanService(api_key, server_url)
    try:
        return asyncio.get_event_loop().run_until_complete(
            service.create_plan(plan_id, project_id, task_id, user_id, title, steps)
        )
    finally:
        asyncio.get_event_loop().run_until_complete(service.close())


def update_plan_sync(
    api_key: str,
    plan_id: str,
    server_url: Optional[str] = None,
    **updates: Any,
) -> bool:
    """Sync wrapper for update_plan."""
    service = PlanService(api_key, server_url)
    try:
        return asyncio.get_event_loop().run_until_complete(
            service.update_plan(plan_id, **updates)
        )
    finally:
        asyncio.get_event_loop().run_until_complete(service.close())


def get_plan_sync(
    api_key: str,
    plan_id: str,
    server_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Sync wrapper for get_plan."""
    service = PlanService(api_key, server_url)
    try:
        return asyncio.get_event_loop().run_until_complete(
            service.get_plan(plan_id)
        )
    finally:
        asyncio.get_event_loop().run_until_complete(service.close())
