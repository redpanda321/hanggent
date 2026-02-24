"""
Usage tracking service for backend.

Sends usage records to the server for persistence and analytics.
"""

import os
import asyncio
import httpx
from typing import Optional, Dict, Any
from pydantic import BaseModel
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("usage_service")


class UsageData(BaseModel):
    """Usage data to be sent to the server."""
    task_id: str
    project_id: Optional[str] = None
    agent_name: str
    agent_step: Optional[int] = None
    model_platform: str
    model_type: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    execution_time_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UsageService:
    """Service for tracking and reporting usage to the server."""
    
    _instance: Optional["UsageService"] = None
    _client: Optional[httpx.AsyncClient] = None
    
    def __init__(self):
        # Get server URL from environment or default
        self.server_url = os.environ.get("SERVER_URL", "http://localhost:3001")
        self._pending_records: list[UsageData] = []
        self._flush_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    @classmethod
    def get_instance(cls) -> "UsageService":
        """Get singleton instance of UsageService."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.server_url,
                timeout=30.0,
            )
        return self._client
    
    async def record_usage(
        self,
        task_id: str,
        agent_name: str,
        model_platform: str,
        model_type: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        project_id: Optional[str] = None,
        agent_step: Optional[int] = None,
        execution_time_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        token: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record usage data asynchronously.
        
        This method adds usage data to a buffer and flushes it to the server
        periodically or when the buffer is full.
        
        Args:
            task_id: The task identifier
            agent_name: Name of the agent that consumed tokens
            model_platform: The model platform (e.g., "openai", "anthropic")
            model_type: The model type (e.g., "gpt-4o", "claude-3-5-sonnet")
            input_tokens: Number of input/prompt tokens
            output_tokens: Number of output/completion tokens
            total_tokens: Total tokens (input + output)
            project_id: Optional project identifier
            agent_step: Optional step number in task execution
            execution_time_ms: Optional execution time in milliseconds
            success: Whether the agent step was successful
            error_message: Optional error message if not successful
            token: Authorization token for the server
            metadata: Optional additional metadata
        """
        if not token:
            logger.warning("No auth token provided for usage tracking, skipping")
            return
            
        usage_data = UsageData(
            task_id=task_id,
            project_id=project_id,
            agent_name=agent_name,
            agent_step=agent_step,
            model_platform=model_platform,
            model_type=model_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens or (input_tokens + output_tokens),
            execution_time_ms=execution_time_ms,
            success=success,
            error_message=error_message,
            metadata=metadata,
        )
        
        # Send immediately in a background task
        asyncio.create_task(self._send_usage(usage_data, token))
    
    async def _send_usage(self, usage_data: UsageData, token: str) -> None:
        """Send usage data to the server."""
        try:
            client = await self._get_client()
            
            response = await client.post(
                "/api/usage/record",
                json=usage_data.model_dump(),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            
            if response.status_code == 200:
                logger.debug(
                    f"Usage recorded: {usage_data.agent_name} - {usage_data.total_tokens} tokens"
                )
            else:
                logger.warning(
                    f"Failed to record usage: {response.status_code} - {response.text}"
                )
                
        except Exception as e:
            # Don't fail the agent execution if usage tracking fails
            logger.error(f"Error recording usage: {e}", exc_info=True)
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Global function for easy access
async def record_agent_usage(
    task_id: str,
    agent_name: str,
    model_platform: str,
    model_type: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    project_id: Optional[str] = None,
    agent_step: Optional[int] = None,
    execution_time_ms: Optional[int] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    token: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Record agent usage data.
    
    This is a convenience function that uses the singleton UsageService.
    """
    service = UsageService.get_instance()
    await service.record_usage(
        task_id=task_id,
        agent_name=agent_name,
        model_platform=model_platform,
        model_type=model_type,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        project_id=project_id,
        agent_step=agent_step,
        execution_time_ms=execution_time_ms,
        success=success,
        error_message=error_message,
        token=token,
        metadata=metadata,
    )
