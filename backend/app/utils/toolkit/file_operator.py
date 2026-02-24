"""File operation interfaces and implementations for Electron and Web modes.

This module provides a protocol-based abstraction for file operations that works
in both Electron mode (direct filesystem) and Web mode (via server API).

Pattern adapted from manus/backend-manus/app/tool/file_operators.py
"""

import asyncio
import aiofiles
from pathlib import Path
from typing import List, Optional, Protocol, Tuple, Union, runtime_checkable

import httpx

from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("file_operator")


PathLike = Union[str, Path]


class FileOperatorError(Exception):
    """Base exception for file operator errors."""
    pass


@runtime_checkable
class FileOperator(Protocol):
    """Interface for file operations in different environments.
    
    This protocol defines the common interface that both Electron (local)
    and Web (API) implementations must follow.
    """

    async def read_file(self, path: PathLike) -> str:
        """Read content from a file."""
        ...

    async def write_file(self, path: PathLike, content: str) -> None:
        """Write content to a file."""
        ...

    async def read_file_bytes(self, path: PathLike) -> bytes:
        """Read file as bytes."""
        ...

    async def write_file_bytes(self, path: PathLike, content: bytes) -> None:
        """Write bytes to a file."""
        ...

    async def exists(self, path: PathLike) -> bool:
        """Check if path exists."""
        ...

    async def is_directory(self, path: PathLike) -> bool:
        """Check if path points to a directory."""
        ...

    async def is_file(self, path: PathLike) -> bool:
        """Check if path points to a file."""
        ...

    async def list_directory(self, path: PathLike) -> List[str]:
        """List contents of a directory."""
        ...

    async def create_directory(self, path: PathLike, parents: bool = True) -> None:
        """Create a directory."""
        ...

    async def delete(self, path: PathLike, recursive: bool = False) -> None:
        """Delete a file or directory."""
        ...

    async def run_command(
        self, cmd: str, cwd: Optional[PathLike] = None, timeout: Optional[float] = 120.0
    ) -> Tuple[int, str, str]:
        """Run a shell command and return (return_code, stdout, stderr)."""
        ...


class LocalFileOperator:
    """File operations implementation for local filesystem (Electron mode).
    
    Direct filesystem access using Python's pathlib and aiofiles.
    """

    encoding: str = "utf-8"

    async def read_file(self, path: PathLike) -> str:
        """Read content from a local file."""
        try:
            async with aiofiles.open(path, mode="r", encoding=self.encoding) as f:
                return await f.read()
        except FileNotFoundError:
            raise FileOperatorError(f"File not found: {path}")
        except Exception as e:
            raise FileOperatorError(f"Failed to read {path}: {str(e)}") from e

    async def write_file(self, path: PathLike, content: str) -> None:
        """Write content to a local file."""
        try:
            # Ensure parent directory exists
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(path, mode="w", encoding=self.encoding) as f:
                await f.write(content)
        except Exception as e:
            raise FileOperatorError(f"Failed to write to {path}: {str(e)}") from e

    async def read_file_bytes(self, path: PathLike) -> bytes:
        """Read file as bytes."""
        try:
            async with aiofiles.open(path, mode="rb") as f:
                return await f.read()
        except FileNotFoundError:
            raise FileOperatorError(f"File not found: {path}")
        except Exception as e:
            raise FileOperatorError(f"Failed to read {path}: {str(e)}") from e

    async def write_file_bytes(self, path: PathLike, content: bytes) -> None:
        """Write bytes to a file."""
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(path, mode="wb") as f:
                await f.write(content)
        except Exception as e:
            raise FileOperatorError(f"Failed to write to {path}: {str(e)}") from e

    async def exists(self, path: PathLike) -> bool:
        """Check if path exists."""
        return Path(path).exists()

    async def is_directory(self, path: PathLike) -> bool:
        """Check if path points to a directory."""
        return Path(path).is_dir()

    async def is_file(self, path: PathLike) -> bool:
        """Check if path points to a file."""
        return Path(path).is_file()

    async def list_directory(self, path: PathLike) -> List[str]:
        """List contents of a directory."""
        try:
            p = Path(path)
            if not p.is_dir():
                raise FileOperatorError(f"Not a directory: {path}")
            return [item.name for item in p.iterdir()]
        except Exception as e:
            raise FileOperatorError(f"Failed to list directory {path}: {str(e)}") from e

    async def create_directory(self, path: PathLike, parents: bool = True) -> None:
        """Create a directory."""
        try:
            Path(path).mkdir(parents=parents, exist_ok=True)
        except Exception as e:
            raise FileOperatorError(f"Failed to create directory {path}: {str(e)}") from e

    async def delete(self, path: PathLike, recursive: bool = False) -> None:
        """Delete a file or directory."""
        try:
            p = Path(path)
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                if recursive:
                    import shutil
                    shutil.rmtree(p)
                else:
                    p.rmdir()
            else:
                raise FileOperatorError(f"Path does not exist: {path}")
        except Exception as e:
            raise FileOperatorError(f"Failed to delete {path}: {str(e)}") from e

    async def run_command(
        self, cmd: str, cwd: Optional[PathLike] = None, timeout: Optional[float] = 120.0
    ) -> Tuple[int, str, str]:
        """Run a shell command locally."""
        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
                return (
                    process.returncode or 0,
                    stdout.decode(self.encoding, errors="replace"),
                    stderr.decode(self.encoding, errors="replace"),
                )
            except asyncio.TimeoutError as exc:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                raise TimeoutError(
                    f"Command '{cmd}' timed out after {timeout} seconds"
                ) from exc
        except TimeoutError:
            raise
        except Exception as e:
            raise FileOperatorError(f"Failed to run command '{cmd}': {str(e)}") from e


class APIFileOperator:
    """File operations implementation for Web mode via server API.
    
    Uses HTTP API calls to the Hanggent server for file operations.
    Files are stored on the server, not locally.
    """

    def __init__(
        self,
        server_url: str = "http://localhost:3001",
        api_prefix: str = "/api/files",
        timeout: float = 30.0,
    ):
        self.server_url = server_url.rstrip("/")
        self.api_prefix = api_prefix
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.server_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _api_call(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> httpx.Response:
        """Make an API call."""
        client = await self._get_client()
        url = f"{self.api_prefix}{endpoint}"
        response = await client.request(method, url, **kwargs)
        if response.status_code >= 400:
            raise FileOperatorError(
                f"API error {response.status_code}: {response.text}"
            )
        return response

    async def read_file(self, path: PathLike) -> str:
        """Read content from a file via API."""
        try:
            response = await self._api_call(
                "GET", 
                "/read",
                params={"path": str(path)},
            )
            data = response.json()
            return data.get("content", "")
        except Exception as e:
            raise FileOperatorError(f"Failed to read {path}: {str(e)}") from e

    async def write_file(self, path: PathLike, content: str) -> None:
        """Write content to a file via API."""
        try:
            await self._api_call(
                "POST",
                "/write",
                json={"path": str(path), "content": content},
            )
        except Exception as e:
            raise FileOperatorError(f"Failed to write to {path}: {str(e)}") from e

    async def read_file_bytes(self, path: PathLike) -> bytes:
        """Read file as bytes via API."""
        try:
            response = await self._api_call(
                "GET",
                "/read-bytes",
                params={"path": str(path)},
            )
            return response.content
        except Exception as e:
            raise FileOperatorError(f"Failed to read {path}: {str(e)}") from e

    async def write_file_bytes(self, path: PathLike, content: bytes) -> None:
        """Write bytes to a file via API."""
        try:
            await self._api_call(
                "POST",
                "/write-bytes",
                content=content,
                params={"path": str(path)},
            )
        except Exception as e:
            raise FileOperatorError(f"Failed to write to {path}: {str(e)}") from e

    async def exists(self, path: PathLike) -> bool:
        """Check if path exists via API."""
        try:
            response = await self._api_call(
                "GET",
                "/exists",
                params={"path": str(path)},
            )
            return response.json().get("exists", False)
        except FileOperatorError:
            return False

    async def is_directory(self, path: PathLike) -> bool:
        """Check if path is a directory via API."""
        try:
            response = await self._api_call(
                "GET",
                "/stat",
                params={"path": str(path)},
            )
            return response.json().get("is_directory", False)
        except FileOperatorError:
            return False

    async def is_file(self, path: PathLike) -> bool:
        """Check if path is a file via API."""
        try:
            response = await self._api_call(
                "GET",
                "/stat",
                params={"path": str(path)},
            )
            return response.json().get("is_file", False)
        except FileOperatorError:
            return False

    async def list_directory(self, path: PathLike) -> List[str]:
        """List directory contents via API."""
        try:
            response = await self._api_call(
                "GET",
                "/list",
                params={"path": str(path)},
            )
            return response.json().get("items", [])
        except Exception as e:
            raise FileOperatorError(f"Failed to list directory {path}: {str(e)}") from e

    async def create_directory(self, path: PathLike, parents: bool = True) -> None:
        """Create a directory via API."""
        try:
            await self._api_call(
                "POST",
                "/mkdir",
                json={"path": str(path), "parents": parents},
            )
        except Exception as e:
            raise FileOperatorError(f"Failed to create directory {path}: {str(e)}") from e

    async def delete(self, path: PathLike, recursive: bool = False) -> None:
        """Delete a file or directory via API."""
        try:
            await self._api_call(
                "DELETE",
                "/delete",
                params={"path": str(path), "recursive": str(recursive).lower()},
            )
        except Exception as e:
            raise FileOperatorError(f"Failed to delete {path}: {str(e)}") from e

    async def run_command(
        self, cmd: str, cwd: Optional[PathLike] = None, timeout: Optional[float] = 120.0
    ) -> Tuple[int, str, str]:
        """Run a shell command via API (sandboxed on server)."""
        try:
            response = await self._api_call(
                "POST",
                "/exec",
                json={
                    "command": cmd,
                    "cwd": str(cwd) if cwd else None,
                    "timeout": timeout,
                },
                timeout=timeout + 5 if timeout else None,  # Extra time for HTTP overhead
            )
            data = response.json()
            return (
                data.get("return_code", 0),
                data.get("stdout", ""),
                data.get("stderr", ""),
            )
        except TimeoutError:
            raise
        except Exception as e:
            raise FileOperatorError(f"Failed to run command '{cmd}': {str(e)}") from e
