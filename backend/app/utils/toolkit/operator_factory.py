"""Operator factory for mode-based operator selection.

Provides factory functions to get the appropriate operators based on
the application mode (Electron vs Web).

Pattern adapted from manus/backend-manus/app/tool/file_operators.py
"""

from typing import Optional

from app.config import AppConfig, AppMode, get_config
from app.utils.toolkit.browser_operator import (
    BrowserOperator,
    ElectronBrowserOperator,
    WebBrowserOperator,
)
from app.utils.toolkit.file_operator import (
    FileOperator,
    LocalFileOperator,
    APIFileOperator,
)

from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("operator_factory")


# Singleton instances for operators
_browser_operator: Optional[BrowserOperator] = None
_file_operator: Optional[FileOperator] = None


def get_browser_operator(
    config: Optional[AppConfig] = None,
    session_id: Optional[str] = None,
    force_new: bool = False,
) -> BrowserOperator:
    """Get the appropriate browser operator based on app mode.
    
    Args:
        config: Application configuration. Uses global config if not provided.
        session_id: Session ID for connection pooling (Electron mode).
        force_new: Force creation of a new operator instance.
        
    Returns:
        BrowserOperator: Either ElectronBrowserOperator or WebBrowserOperator.
        
    Example:
        ```python
        operator = get_browser_operator()
        await operator.initialize()
        result = await operator.navigate("https://example.com")
        await operator.close()
        ```
    """
    global _browser_operator
    
    if _browser_operator is not None and not force_new:
        return _browser_operator
    
    cfg = config or get_config()
    
    if cfg.is_electron_mode:
        logger.info(f"Creating ElectronBrowserOperator (CDP: {cfg.browser.cdp_endpoint})")
        _browser_operator = ElectronBrowserOperator(
            cdp_url=cfg.browser.cdp_endpoint,
            cdp_port=cfg.browser.cdp_port,
            session_id=session_id or "default",
        )
    else:
        logger.info(f"Creating WebBrowserOperator (headless: {cfg.browser.headless})")
        _browser_operator = WebBrowserOperator(
            headless=cfg.browser.headless,
            browser_type=cfg.browser.browser_type,
            config={
                "disable_security": cfg.browser.disable_security,
                "enable_vnc": cfg.browser.enable_vnc,
                "vnc_port": cfg.browser.vnc_port,
            },
        )
    
    return _browser_operator


def get_file_operator(
    config: Optional[AppConfig] = None,
    force_new: bool = False,
) -> FileOperator:
    """Get the appropriate file operator based on app mode.
    
    Args:
        config: Application configuration. Uses global config if not provided.
        force_new: Force creation of a new operator instance.
        
    Returns:
        FileOperator: Either LocalFileOperator or APIFileOperator.
        
    Example:
        ```python
        operator = get_file_operator()
        content = await operator.read_file("/path/to/file.txt")
        await operator.write_file("/path/to/output.txt", content)
        ```
    """
    global _file_operator
    
    if _file_operator is not None and not force_new:
        return _file_operator
    
    cfg = config or get_config()
    
    if cfg.is_electron_mode:
        logger.info("Creating LocalFileOperator (direct filesystem access)")
        _file_operator = LocalFileOperator()
    else:
        logger.info(f"Creating APIFileOperator (server: {cfg.server.server_url})")
        _file_operator = APIFileOperator(
            server_url=cfg.server.server_url,
            timeout=cfg.server.api_timeout,
        )
    
    return _file_operator


async def cleanup_operators() -> None:
    """Cleanup all operator instances.
    
    Should be called on application shutdown.
    """
    global _browser_operator, _file_operator
    
    if _browser_operator is not None:
        try:
            await _browser_operator.close()
        except Exception as e:
            logger.error(f"Error closing browser operator: {e}")
        _browser_operator = None
    
    if _file_operator is not None:
        # APIFileOperator has a close method
        if hasattr(_file_operator, 'close'):
            try:
                await _file_operator.close()
            except Exception as e:
                logger.error(f"Error closing file operator: {e}")
        _file_operator = None
    
    logger.info("All operators cleaned up")


def reset_operators() -> None:
    """Reset operator instances (for testing or reconfiguration)."""
    global _browser_operator, _file_operator
    _browser_operator = None
    _file_operator = None
    logger.debug("Operators reset")


class OperatorContext:
    """Context manager for operator lifecycle management.
    
    Example:
        ```python
        async with OperatorContext() as ctx:
            browser = ctx.browser
            files = ctx.files
            await browser.navigate("https://example.com")
            await files.write_file("output.txt", "content")
        # Operators are automatically cleaned up
        ```
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or get_config()
        self._browser: Optional[BrowserOperator] = None
        self._files: Optional[FileOperator] = None
    
    async def __aenter__(self) -> "OperatorContext":
        self._browser = get_browser_operator(self.config, force_new=True)
        self._files = get_file_operator(self.config, force_new=True)
        await self._browser.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.error(f"Error closing browser in context: {e}")
        
        if self._files and hasattr(self._files, 'close'):
            try:
                await self._files.close()
            except Exception as e:
                logger.error(f"Error closing files in context: {e}")
    
    @property
    def browser(self) -> BrowserOperator:
        """Get the browser operator."""
        if self._browser is None:
            raise RuntimeError("OperatorContext not entered")
        return self._browser
    
    @property
    def files(self) -> FileOperator:
        """Get the file operator."""
        if self._files is None:
            raise RuntimeError("OperatorContext not entered")
        return self._files
