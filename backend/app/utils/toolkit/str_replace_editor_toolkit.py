"""
String Replace Editor Toolkit

A CAMEL-compatible toolkit for viewing, creating and editing files.
Ported from backend-manus str_replace_editor with support for sandbox execution.

Features:
- View files and directories with line numbers
- Create new files
- String replacement with undo support
- Insert text at specific lines
- Undo last edit

Usage:
    toolkit = StrReplaceEditorToolkit(api_task_id)
    tools = toolkit.get_tools()
"""

import asyncio
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, List, Literal, Optional, Tuple, Union

from camel.toolkits.function_tool import FunctionTool

from app.service.task import Agents
from app.utils.toolkit.abstract_toolkit import AbstractToolkit
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("str_replace_editor_toolkit")


# Type aliases
PathLike = Union[str, Path]
Command = Literal["view", "create", "str_replace", "insert", "undo_edit"]

# Constants
SNIPPET_LINES: int = 4
MAX_RESPONSE_LEN: int = 16000
TRUNCATED_MESSAGE: str = (
    "<response clipped><NOTE>To save on context only part of this file has been shown to you. "
    "You should retry this tool after you have searched inside the file with `grep -n` "
    "in order to find the line numbers of what you are looking for.</NOTE>"
)


def maybe_truncate(content: str, truncate_after: Optional[int] = MAX_RESPONSE_LEN) -> str:
    """Truncate content and append a notice if content exceeds the specified length."""
    if not truncate_after or len(content) <= truncate_after:
        return content
    return content[:truncate_after] + TRUNCATED_MESSAGE


class FileOperator:
    """Interface for file operations. Can be extended for sandbox support."""
    
    encoding: str = "utf-8"
    
    async def read_file(self, path: PathLike) -> str:
        """Read content from a file."""
        try:
            return Path(path).read_text(encoding=self.encoding)
        except Exception as e:
            raise FileOperationError(f"Failed to read {path}: {str(e)}")

    async def write_file(self, path: PathLike, content: str) -> None:
        """Write content to a file."""
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content, encoding=self.encoding)
        except Exception as e:
            raise FileOperationError(f"Failed to write to {path}: {str(e)}")

    async def is_directory(self, path: PathLike) -> bool:
        """Check if path points to a directory."""
        return Path(path).is_dir()

    async def exists(self, path: PathLike) -> bool:
        """Check if path exists."""
        return Path(path).exists()

    async def run_command(
        self, cmd: str, timeout: Optional[float] = 120.0
    ) -> Tuple[int, str, str]:
        """Run a shell command and return (return_code, stdout, stderr)."""
        process = await asyncio.create_subprocess_shell(
            cmd, 
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            return (
                process.returncode or 0,
                stdout.decode(),
                stderr.decode(),
            )
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            raise TimeoutError(f"Command '{cmd}' timed out after {timeout} seconds")


class FileOperationError(Exception):
    """Error raised when a file operation fails."""
    pass


class StrReplaceEditorToolkit(AbstractToolkit):
    """
    A CAMEL-compatible toolkit for viewing, creating, and editing files.
    
    This provides a set of file manipulation tools that can be used by CAMEL agents
    for software engineering tasks.
    
    Features:
    - view: Display file contents with line numbers or list directory contents
    - create: Create new files with specified content
    - str_replace: Replace a unique string in a file
    - insert: Insert text at a specific line
    - undo_edit: Revert the last edit to a file
    """
    
    agent_name: str = Agents.developer_agent
    
    # File history for undo support (class-level to persist across instances)
    _file_history: DefaultDict[PathLike, List[str]] = defaultdict(list)
    
    def __init__(
        self,
        api_task_id: str,
        agent_name: Optional[str] = None,
        working_directory: Optional[str] = None,
        use_sandbox: bool = False,
    ):
        """
        Initialize the StrReplaceEditorToolkit.
        
        Args:
            api_task_id: The task ID for tracking
            agent_name: Optional agent name override
            working_directory: Optional working directory for relative paths
            use_sandbox: Whether to use sandbox execution (future feature)
        """
        self.api_task_id = api_task_id
        if agent_name:
            self.agent_name = agent_name
        self.working_directory = working_directory or os.getcwd()
        self.use_sandbox = use_sandbox
        self._operator = FileOperator()
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve path, making relative paths absolute."""
        p = Path(path)
        if not p.is_absolute():
            p = Path(self.working_directory) / p
        return p
    
    def view(
        self,
        path: str,
        view_range: Optional[List[int]] = None,
    ) -> str:
        """
        View file or directory contents.
        
        If path is a file, displays the content with line numbers (like cat -n).
        If path is a directory, lists non-hidden files up to 2 levels deep.
        
        Args:
            path: Absolute or relative path to file or directory
            view_range: Optional [start_line, end_line] to view specific lines.
                        Use -1 as end_line to view to end of file.
        
        Returns:
            Formatted file contents with line numbers or directory listing
        """
        return asyncio.get_event_loop().run_until_complete(
            self._async_view(path, view_range)
        )
    
    async def _async_view(
        self,
        path: str,
        view_range: Optional[List[int]] = None,
    ) -> str:
        """Async implementation of view."""
        resolved_path = self._resolve_path(path)
        
        if not await self._operator.exists(resolved_path):
            return f"Error: The path {resolved_path} does not exist."
        
        is_dir = await self._operator.is_directory(resolved_path)
        
        if is_dir:
            if view_range:
                return "Error: The view_range parameter is not allowed for directories."
            return await self._view_directory(resolved_path)
        else:
            return await self._view_file(resolved_path, view_range)
    
    async def _view_directory(self, path: PathLike) -> str:
        """Display directory contents."""
        try:
            # Use os.walk for cross-platform directory listing
            result_lines = []
            for root, dirs, files in os.walk(str(path)):
                # Calculate depth
                depth = str(root).replace(str(path), '').count(os.sep)
                if depth >= 2:
                    dirs[:] = []  # Don't recurse deeper
                    continue
                
                # Filter hidden items
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                files = [f for f in files if not f.startswith('.')]
                
                # Add to results
                for name in dirs:
                    result_lines.append(os.path.join(root, name) + '/')
                for name in files:
                    result_lines.append(os.path.join(root, name))
            
            output = (
                f"Here are the files and directories up to 2 levels deep in {path}, "
                f"excluding hidden items:\n" + "\n".join(sorted(result_lines)) + "\n"
            )
            return output
        except Exception as e:
            return f"Error listing directory {path}: {str(e)}"
    
    async def _view_file(
        self,
        path: PathLike,
        view_range: Optional[List[int]] = None,
    ) -> str:
        """Display file content with optional line range."""
        try:
            file_content = await self._operator.read_file(path)
            init_line = 1
            
            if view_range:
                if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
                    return "Error: Invalid view_range. It should be a list of two integers."
                
                file_lines = file_content.split("\n")
                n_lines_file = len(file_lines)
                init_line, final_line = view_range
                
                if init_line < 1 or init_line > n_lines_file:
                    return f"Error: Invalid view_range. First element {init_line} should be within [1, {n_lines_file}]"
                if final_line > n_lines_file:
                    return f"Error: Invalid view_range. Second element {final_line} should be <= {n_lines_file}"
                if final_line != -1 and final_line < init_line:
                    return f"Error: Invalid view_range. Second element {final_line} should be >= first element {init_line}"
                
                if final_line == -1:
                    file_content = "\n".join(file_lines[init_line - 1:])
                else:
                    file_content = "\n".join(file_lines[init_line - 1:final_line])
            
            return self._make_output(file_content, str(path), init_line=init_line)
        except Exception as e:
            return f"Error reading file {path}: {str(e)}"
    
    def create(
        self,
        path: str,
        file_text: str,
    ) -> str:
        """
        Create a new file with the specified content.
        
        Cannot overwrite existing files - use str_replace for editing.
        
        Args:
            path: Absolute or relative path for the new file
            file_text: Content to write to the file
        
        Returns:
            Success message or error description
        """
        return asyncio.get_event_loop().run_until_complete(
            self._async_create(path, file_text)
        )
    
    async def _async_create(self, path: str, file_text: str) -> str:
        """Async implementation of create."""
        resolved_path = self._resolve_path(path)
        
        if await self._operator.exists(resolved_path):
            return f"Error: File already exists at {resolved_path}. Cannot overwrite with create command."
        
        try:
            await self._operator.write_file(resolved_path, file_text)
            self._file_history[str(resolved_path)].append(file_text)
            return f"File created successfully at: {resolved_path}"
        except Exception as e:
            return f"Error creating file: {str(e)}"
    
    def str_replace(
        self,
        path: str,
        old_str: str,
        new_str: Optional[str] = None,
    ) -> str:
        """
        Replace a unique string in a file with a new string.
        
        The old_str must appear exactly once in the file. Include enough context
        to make the string unique.
        
        Args:
            path: Path to the file to edit
            old_str: The exact string to replace (must be unique in file)
            new_str: The replacement string (empty string if not provided)
        
        Returns:
            Success message with snippet of changes or error description
        """
        return asyncio.get_event_loop().run_until_complete(
            self._async_str_replace(path, old_str, new_str)
        )
    
    async def _async_str_replace(
        self,
        path: str,
        old_str: str,
        new_str: Optional[str] = None,
    ) -> str:
        """Async implementation of str_replace."""
        resolved_path = self._resolve_path(path)
        
        if not await self._operator.exists(resolved_path):
            return f"Error: File {resolved_path} does not exist."
        
        try:
            file_content = (await self._operator.read_file(resolved_path)).expandtabs()
            old_str = old_str.expandtabs()
            new_str = (new_str or "").expandtabs()
            
            # Check uniqueness
            occurrences = file_content.count(old_str)
            if occurrences == 0:
                return f"Error: No replacement performed. old_str not found in {resolved_path}:\n{old_str}"
            elif occurrences > 1:
                file_lines = file_content.split("\n")
                lines = [idx + 1 for idx, line in enumerate(file_lines) if old_str in line]
                return f"Error: Multiple occurrences of old_str in lines {lines}. Please make old_str unique."
            
            # Perform replacement
            new_file_content = file_content.replace(old_str, new_str)
            await self._operator.write_file(resolved_path, new_file_content)
            
            # Save to history for undo
            self._file_history[str(resolved_path)].append(file_content)
            
            # Create snippet
            replacement_line = file_content.split(old_str)[0].count("\n")
            start_line = max(0, replacement_line - SNIPPET_LINES)
            end_line = replacement_line + SNIPPET_LINES + new_str.count("\n")
            snippet = "\n".join(new_file_content.split("\n")[start_line:end_line + 1])
            
            success_msg = f"The file {resolved_path} has been edited. "
            success_msg += self._make_output(snippet, f"a snippet of {resolved_path}", start_line + 1)
            success_msg += "Review the changes and make sure they are as expected. Edit the file again if necessary."
            
            return success_msg
        except Exception as e:
            return f"Error during string replacement: {str(e)}"
    
    def insert(
        self,
        path: str,
        insert_line: int,
        new_str: str,
    ) -> str:
        """
        Insert text at a specific line in a file.
        
        The new text is inserted AFTER the specified line number.
        
        Args:
            path: Path to the file to edit
            insert_line: Line number after which to insert (0 for beginning)
            new_str: The text to insert
        
        Returns:
            Success message with snippet of changes or error description
        """
        return asyncio.get_event_loop().run_until_complete(
            self._async_insert(path, insert_line, new_str)
        )
    
    async def _async_insert(
        self,
        path: str,
        insert_line: int,
        new_str: str,
    ) -> str:
        """Async implementation of insert."""
        resolved_path = self._resolve_path(path)
        
        if not await self._operator.exists(resolved_path):
            return f"Error: File {resolved_path} does not exist."
        
        try:
            file_text = (await self._operator.read_file(resolved_path)).expandtabs()
            new_str = new_str.expandtabs()
            file_text_lines = file_text.split("\n")
            n_lines_file = len(file_text_lines)
            
            if insert_line < 0 or insert_line > n_lines_file:
                return f"Error: insert_line {insert_line} should be within [0, {n_lines_file}]"
            
            # Perform insertion
            new_str_lines = new_str.split("\n")
            new_file_text_lines = (
                file_text_lines[:insert_line]
                + new_str_lines
                + file_text_lines[insert_line:]
            )
            
            # Create snippet
            snippet_lines = (
                file_text_lines[max(0, insert_line - SNIPPET_LINES):insert_line]
                + new_str_lines
                + file_text_lines[insert_line:insert_line + SNIPPET_LINES]
            )
            
            new_file_text = "\n".join(new_file_text_lines)
            snippet = "\n".join(snippet_lines)
            
            await self._operator.write_file(resolved_path, new_file_text)
            self._file_history[str(resolved_path)].append(file_text)
            
            success_msg = f"The file {resolved_path} has been edited. "
            success_msg += self._make_output(
                snippet,
                "a snippet of the edited file",
                max(1, insert_line - SNIPPET_LINES + 1),
            )
            success_msg += "Review the changes and make sure they are as expected."
            
            return success_msg
        except Exception as e:
            return f"Error during insertion: {str(e)}"
    
    def undo_edit(self, path: str) -> str:
        """
        Undo the last edit made to a file.
        
        Args:
            path: Path to the file to undo
        
        Returns:
            Success message with restored content or error description
        """
        return asyncio.get_event_loop().run_until_complete(
            self._async_undo_edit(path)
        )
    
    async def _async_undo_edit(self, path: str) -> str:
        """Async implementation of undo_edit."""
        resolved_path = self._resolve_path(path)
        path_key = str(resolved_path)
        
        if not self._file_history[path_key]:
            return f"Error: No edit history found for {resolved_path}."
        
        try:
            old_text = self._file_history[path_key].pop()
            await self._operator.write_file(resolved_path, old_text)
            
            return f"Last edit to {resolved_path} undone successfully. " + self._make_output(old_text, str(resolved_path))
        except Exception as e:
            return f"Error during undo: {str(e)}"
    
    def _make_output(
        self,
        file_content: str,
        file_descriptor: str,
        init_line: int = 1,
        expand_tabs: bool = True,
    ) -> str:
        """Format file content for display with line numbers."""
        file_content = maybe_truncate(file_content)
        if expand_tabs:
            file_content = file_content.expandtabs()
        
        # Add line numbers
        file_content = "\n".join([
            f"{i + init_line:6}\t{line}"
            for i, line in enumerate(file_content.split("\n"))
        ])
        
        return (
            f"Here's the result of running `cat -n` on {file_descriptor}:\n"
            + file_content
            + "\n"
        )
    
    def get_tools(self) -> List[FunctionTool]:
        """
        Get all tools as CAMEL FunctionTools.
        
        Returns:
            List of FunctionTool instances for view, create, str_replace, insert, undo_edit
        """
        return [
            FunctionTool(
                func=self.view,
                name="view_file",
                description=(
                    "View file or directory contents. If path is a file, displays content with line numbers. "
                    "If path is a directory, lists files up to 2 levels deep. "
                    "Use view_range=[start, end] to view specific lines (-1 for end means to end of file)."
                ),
            ),
            FunctionTool(
                func=self.create,
                name="create_file",
                description=(
                    "Create a new file with specified content. Cannot overwrite existing files. "
                    "Use str_replace for editing existing files."
                ),
            ),
            FunctionTool(
                func=self.str_replace,
                name="str_replace",
                description=(
                    "Replace a unique string in a file. The old_str must appear exactly once in the file. "
                    "Include enough context (surrounding lines) in old_str to make it unique. "
                    "Supports undo via undo_edit."
                ),
            ),
            FunctionTool(
                func=self.insert,
                name="insert_text",
                description=(
                    "Insert text at a specific line in a file. The new_str is inserted AFTER the specified "
                    "insert_line number. Use 0 to insert at the beginning. Supports undo via undo_edit."
                ),
            ),
            FunctionTool(
                func=self.undo_edit,
                name="undo_edit",
                description=(
                    "Undo the last edit made to a file. Only affects files edited in this session "
                    "via str_replace, insert, or create."
                ),
            ),
        ]
