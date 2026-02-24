"""
Manus Tool Adapter

Adapter to convert Manus/Backend-Manus BaseTool classes to CAMEL FunctionTool instances.
This allows using backend-manus tools within the hanggent CAMEL-based agent system.

Usage:
    from app.utils.toolkit.manus_tool_adapter import ManusToolAdapter, ManusToolResult
    
    # Wrap a single manus tool
    adapter = ManusToolAdapter(api_task_id, manus_tool_instance)
    camel_tools = adapter.get_tools()
    
    # Or use the collection adapter for multiple tools
    collection_adapter = ManusToolCollectionAdapter(api_task_id, [tool1, tool2])
    all_tools = collection_adapter.get_tools()
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type, Union

from camel.toolkits.function_tool import FunctionTool
from pydantic import BaseModel, Field

from app.service.task import Agents
from app.utils.toolkit.abstract_toolkit import AbstractToolkit
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("manus_tool_adapter")


class ManusToolResult(BaseModel):
    """
    Represents the result of a Manus tool execution.
    Compatible with backend-manus ToolResult format.
    """
    output: Any = Field(default=None)
    error: Optional[str] = Field(default=None)
    base64_image: Optional[str] = Field(default=None)
    system: Optional[str] = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

    def __bool__(self):
        return any(getattr(self, field) for field in self.model_fields)

    def __str__(self):
        if self.error:
            return f"Error: {self.error}"
        if isinstance(self.output, str):
            return self.output
        return json.dumps(self.output, indent=2) if self.output else ""

    def to_camel_result(self) -> str:
        """Convert to string format expected by CAMEL agents."""
        return str(self)


class ManusBaseTool(ABC, BaseModel):
    """
    Base class for Manus-style tools that can be adapted to CAMEL format.
    
    This provides the interface expected by backend-manus tools while allowing
    them to be wrapped as CAMEL FunctionTools.
    """
    name: str
    description: str
    parameters: Optional[dict] = None

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    async def __call__(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""
        return await self.execute(**kwargs)

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters. Must be implemented by subclasses."""
        pass

    def to_param(self) -> Dict:
        """Convert tool to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {
                    "type": "object",
                    "properties": {},
                    "required": []
                },
            },
        }

    def success_response(self, data: Union[Dict[str, Any], str]) -> ManusToolResult:
        """Create a successful tool result."""
        if isinstance(data, str):
            text = data
        else:
            text = json.dumps(data, indent=2)
        return ManusToolResult(output=text)

    def fail_response(self, msg: str) -> ManusToolResult:
        """Create a failed tool result."""
        return ManusToolResult(error=msg)


class ManusToolAdapter(AbstractToolkit):
    """
    Adapter that wraps a single Manus BaseTool as a CAMEL toolkit.
    
    This allows using backend-manus tools within the hanggent CAMEL agent system
    by converting them to FunctionTool instances.
    
    Example:
        manus_tool = StrReplaceEditor()
        adapter = ManusToolAdapter(api_task_id, manus_tool)
        tools = adapter.get_tools()  # Returns list[FunctionTool]
    """
    agent_name: str = Agents.developer_agent

    def __init__(
        self, 
        api_task_id: str, 
        manus_tool: ManusBaseTool,
        agent_name: Optional[str] = None
    ):
        self.api_task_id = api_task_id
        self._manus_tool = manus_tool
        if agent_name:
            self.agent_name = agent_name

    def _create_sync_wrapper(self) -> Callable:
        """
        Create a synchronous wrapper function for the async manus tool.
        CAMEL FunctionTool expects sync functions, so we need to wrap async execution.
        """
        manus_tool = self._manus_tool
        api_task_id = self.api_task_id

        def sync_execute(**kwargs) -> str:
            """Synchronous wrapper that runs the async tool in an event loop."""
            try:
                # Try to get existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, create a new one in a thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run, 
                            manus_tool.execute(**kwargs)
                        )
                        result = future.result()
                else:
                    result = loop.run_until_complete(manus_tool.execute(**kwargs))
            except RuntimeError:
                # No event loop, create one
                result = asyncio.run(manus_tool.execute(**kwargs))
            
            # Convert result to string for CAMEL
            if isinstance(result, ManusToolResult):
                return result.to_camel_result()
            elif isinstance(result, str):
                return result
            else:
                return json.dumps(result, indent=2) if result else ""

        # Set function metadata for CAMEL
        sync_execute.__name__ = manus_tool.name
        sync_execute.__doc__ = manus_tool.description

        return sync_execute

    def get_tools(self) -> List[FunctionTool]:
        """
        Convert the Manus tool to a list of CAMEL FunctionTools.
        
        Returns:
            List containing a single FunctionTool wrapping the Manus tool.
        """
        wrapper = self._create_sync_wrapper()
        
        # Get the OpenAI tool schema from the manus tool
        tool_param = self._manus_tool.to_param()
        
        return [
            FunctionTool(
                func=wrapper,
                name=self._manus_tool.name,
                description=self._manus_tool.description,
                openai_tool_schema=tool_param,
            )
        ]


class ManusToolCollectionAdapter(AbstractToolkit):
    """
    Adapter that wraps multiple Manus tools as a single CAMEL toolkit.
    
    This is useful when you have a collection of related tools that should
    be provided together to an agent.
    
    Example:
        tools = [StrReplaceEditor(), BashTool(), PythonExecute()]
        adapter = ManusToolCollectionAdapter(api_task_id, tools)
        all_tools = adapter.get_tools()  # Returns list[FunctionTool] for all tools
    """
    agent_name: str = Agents.developer_agent

    def __init__(
        self, 
        api_task_id: str, 
        manus_tools: List[ManusBaseTool],
        agent_name: Optional[str] = None
    ):
        self.api_task_id = api_task_id
        self._manus_tools = manus_tools
        self._tool_map = {tool.name: tool for tool in manus_tools}
        if agent_name:
            self.agent_name = agent_name

    def get_tools(self) -> List[FunctionTool]:
        """
        Convert all Manus tools to CAMEL FunctionTools.
        
        Returns:
            List of FunctionTools for all wrapped Manus tools.
        """
        all_tools = []
        for manus_tool in self._manus_tools:
            adapter = ManusToolAdapter(
                self.api_task_id, 
                manus_tool, 
                self.agent_name
            )
            all_tools.extend(adapter.get_tools())
        return all_tools

    async def execute(self, *, name: str, tool_input: Dict[str, Any] = None) -> ManusToolResult:
        """
        Execute a tool by name with given inputs.
        
        This provides compatibility with the backend-manus ToolCollection interface.
        
        Args:
            name: Name of the tool to execute
            tool_input: Dictionary of parameters to pass to the tool
            
        Returns:
            ManusToolResult with the execution result or error
        """
        tool = self._tool_map.get(name)
        if not tool:
            return ManusToolResult(error=f"Tool '{name}' not found in collection")
        
        try:
            result = await tool.execute(**(tool_input or {}))
            if isinstance(result, ManusToolResult):
                return result
            return ManusToolResult(output=str(result))
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            return ManusToolResult(error=str(e))

    def add_tool(self, tool: ManusBaseTool) -> "ManusToolCollectionAdapter":
        """Add a tool to the collection."""
        self._manus_tools.append(tool)
        self._tool_map[tool.name] = tool
        return self

    def to_params(self) -> List[Dict[str, Any]]:
        """Get OpenAI function call parameters for all tools."""
        return [tool.to_param() for tool in self._manus_tools]
