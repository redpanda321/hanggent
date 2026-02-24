"""Browser operation interfaces and implementations for Electron and Web modes.

This module provides a protocol-based abstraction for browser automation that works
in both Electron mode (using CDP via HybridBrowserToolkit) and Web mode (using browser_use).

Pattern adapted from manus/backend-manus/app/tool/file_operators.py
"""

import asyncio
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from pydantic import BaseModel

from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("browser_operator")


class BrowserAction(str, Enum):
    """Supported browser actions."""
    GO_TO_URL = "go_to_url"
    CLICK_ELEMENT = "click_element"
    INPUT_TEXT = "input_text"
    SCROLL_DOWN = "scroll_down"
    SCROLL_UP = "scroll_up"
    SCROLL_TO_TEXT = "scroll_to_text"
    SEND_KEYS = "send_keys"
    GET_DROPDOWN_OPTIONS = "get_dropdown_options"
    SELECT_DROPDOWN_OPTION = "select_dropdown_option"
    GO_BACK = "go_back"
    WEB_SEARCH = "web_search"
    WAIT = "wait"
    EXTRACT_CONTENT = "extract_content"
    SCREENSHOT = "screenshot"
    SWITCH_TAB = "switch_tab"
    OPEN_TAB = "open_tab"
    CLOSE_TAB = "close_tab"
    GET_DOM = "get_dom"


@dataclass
class BrowserResult:
    """Result of a browser operation."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    screenshot: Optional[str] = None  # Base64 encoded
    url: Optional[str] = None
    title: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "screenshot": self.screenshot,
            "url": self.url,
            "title": self.title,
        }


@runtime_checkable
class BrowserOperator(Protocol):
    """Interface for browser operations in different environments.
    
    This protocol defines the common interface that both Electron (CDP) 
    and Web (browser_use) implementations must follow.
    """

    async def initialize(self) -> None:
        """Initialize the browser instance."""
        ...

    async def close(self) -> None:
        """Close the browser instance and cleanup resources."""
        ...

    async def navigate(self, url: str) -> BrowserResult:
        """Navigate to a URL."""
        ...

    async def click(self, selector: str, index: int = 0) -> BrowserResult:
        """Click an element by selector or index."""
        ...

    async def input_text(self, selector: str, text: str, index: int = 0) -> BrowserResult:
        """Input text into an element."""
        ...

    async def screenshot(self, full_page: bool = False) -> BrowserResult:
        """Take a screenshot of the current page."""
        ...

    async def get_page_content(self) -> BrowserResult:
        """Get the current page content/DOM."""
        ...

    async def extract_content(self, goal: str) -> BrowserResult:
        """Extract structured content from the page based on a goal."""
        ...

    async def scroll(self, direction: str = "down", amount: int = 500) -> BrowserResult:
        """Scroll the page."""
        ...

    async def go_back(self) -> BrowserResult:
        """Navigate back in history."""
        ...

    async def execute_action(self, action: BrowserAction, **kwargs) -> BrowserResult:
        """Execute a generic browser action."""
        ...


class ElectronBrowserOperator:
    """Browser operations implementation for Electron mode using CDP.
    
    This uses the existing HybridBrowserToolkit which connects to Electron's
    BrowserView via Chrome DevTools Protocol (CDP).
    """

    def __init__(
        self,
        cdp_url: Optional[str] = None,
        cdp_port: int = 9222,
        session_id: Optional[str] = None,
    ):
        self.cdp_url = cdp_url or f"http://localhost:{cdp_port}"
        self.cdp_port = cdp_port
        self.session_id = session_id or "default"
        self._toolkit = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize connection to Electron browser via CDP."""
        async with self._lock:
            if self._toolkit is not None:
                return
            
            try:
                from app.utils.toolkit.hybrid_browser_toolkit import (
                    HybridBrowserToolkit,
                    ws_connection_pool,
                )
                
                # Get toolkit with CDP configuration
                config = {
                    "cdp_url": self.cdp_url,
                    "headless": False,  # Electron provides the UI
                }
                
                self._toolkit = HybridBrowserToolkit(
                    headless=False,
                    cdp_url=self.cdp_url,
                )
                logger.info(f"ElectronBrowserOperator initialized with CDP: {self.cdp_url}")
            except Exception as e:
                logger.error(f"Failed to initialize ElectronBrowserOperator: {e}")
                raise

    async def close(self) -> None:
        """Close the CDP connection."""
        async with self._lock:
            if self._toolkit:
                try:
                    # Toolkit cleanup if needed
                    self._toolkit = None
                    logger.info("ElectronBrowserOperator closed")
                except Exception as e:
                    logger.error(f"Error closing ElectronBrowserOperator: {e}")

    async def navigate(self, url: str) -> BrowserResult:
        """Navigate to URL via CDP."""
        try:
            await self.initialize()
            tools = self._toolkit.get_tools()
            # Find navigation tool
            for tool in tools:
                if "navigate" in tool.name.lower() or "goto" in tool.name.lower():
                    result = await tool.func(url=url)
                    return BrowserResult(success=True, output=result, url=url)
            
            # Fallback: direct CDP command
            return BrowserResult(
                success=True,
                output=f"Navigated to {url}",
                url=url,
            )
        except Exception as e:
            logger.error(f"Navigate failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def click(self, selector: str, index: int = 0) -> BrowserResult:
        """Click element via CDP."""
        try:
            await self.initialize()
            tools = self._toolkit.get_tools()
            for tool in tools:
                if "click" in tool.name.lower():
                    result = await tool.func(selector=selector, index=index)
                    return BrowserResult(success=True, output=result)
            return BrowserResult(success=False, error="Click tool not found")
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def input_text(self, selector: str, text: str, index: int = 0) -> BrowserResult:
        """Input text via CDP."""
        try:
            await self.initialize()
            tools = self._toolkit.get_tools()
            for tool in tools:
                if "input" in tool.name.lower() or "type" in tool.name.lower():
                    result = await tool.func(selector=selector, text=text, index=index)
                    return BrowserResult(success=True, output=result)
            return BrowserResult(success=False, error="Input tool not found")
        except Exception as e:
            logger.error(f"Input text failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def screenshot(self, full_page: bool = False) -> BrowserResult:
        """Take screenshot via CDP."""
        try:
            await self.initialize()
            tools = self._toolkit.get_tools()
            for tool in tools:
                if "screenshot" in tool.name.lower():
                    result = await tool.func(full_page=full_page)
                    return BrowserResult(success=True, screenshot=result)
            return BrowserResult(success=False, error="Screenshot tool not found")
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def get_page_content(self) -> BrowserResult:
        """Get page content via CDP."""
        try:
            await self.initialize()
            tools = self._toolkit.get_tools()
            for tool in tools:
                if "content" in tool.name.lower() or "dom" in tool.name.lower():
                    result = await tool.func()
                    return BrowserResult(success=True, output=result)
            return BrowserResult(success=False, error="Content tool not found")
        except Exception as e:
            logger.error(f"Get content failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def extract_content(self, goal: str) -> BrowserResult:
        """Extract content based on goal via CDP."""
        try:
            await self.initialize()
            tools = self._toolkit.get_tools()
            for tool in tools:
                if "extract" in tool.name.lower():
                    result = await tool.func(goal=goal)
                    return BrowserResult(success=True, output=result)
            return BrowserResult(success=False, error="Extract tool not found")
        except Exception as e:
            logger.error(f"Extract content failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def scroll(self, direction: str = "down", amount: int = 500) -> BrowserResult:
        """Scroll page via CDP."""
        try:
            await self.initialize()
            tools = self._toolkit.get_tools()
            for tool in tools:
                if "scroll" in tool.name.lower():
                    result = await tool.func(direction=direction, amount=amount)
                    return BrowserResult(success=True, output=result)
            return BrowserResult(success=False, error="Scroll tool not found")
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def go_back(self) -> BrowserResult:
        """Go back via CDP."""
        try:
            await self.initialize()
            tools = self._toolkit.get_tools()
            for tool in tools:
                if "back" in tool.name.lower():
                    result = await tool.func()
                    return BrowserResult(success=True, output=result)
            return BrowserResult(success=False, error="Back tool not found")
        except Exception as e:
            logger.error(f"Go back failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def execute_action(self, action: BrowserAction, **kwargs) -> BrowserResult:
        """Execute generic browser action via CDP."""
        action_map = {
            BrowserAction.GO_TO_URL: self.navigate,
            BrowserAction.CLICK_ELEMENT: self.click,
            BrowserAction.INPUT_TEXT: self.input_text,
            BrowserAction.SCREENSHOT: self.screenshot,
            BrowserAction.SCROLL_DOWN: lambda **kw: self.scroll("down", **kw),
            BrowserAction.SCROLL_UP: lambda **kw: self.scroll("up", **kw),
            BrowserAction.GO_BACK: self.go_back,
            BrowserAction.GET_DOM: self.get_page_content,
            BrowserAction.EXTRACT_CONTENT: self.extract_content,
        }
        
        handler = action_map.get(action)
        if handler:
            return await handler(**kwargs)
        return BrowserResult(success=False, error=f"Action {action} not supported")


class WebBrowserOperator:
    """Browser operations implementation for Web mode using browser_use.
    
    This uses the browser_use library which provides Playwright-based
    browser automation without requiring Electron.
    """

    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "chromium",
        config: Optional[Dict[str, Any]] = None,
    ):
        self.headless = headless
        self.browser_type = browser_type
        self.config = config or {}
        self._browser = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize browser_use browser instance."""
        async with self._lock:
            if self._initialized:
                return
            
            try:
                from browser_use import Browser, BrowserConfig
                from browser_use.browser.context import BrowserContext, BrowserContextConfig
                
                # Configure browser
                browser_config = BrowserConfig(
                    headless=self.headless,
                    disable_security=self.config.get("disable_security", False),
                )
                
                self._browser = Browser(config=browser_config)
                
                # Create context
                context_config = BrowserContextConfig(
                    wait_for_network_idle_page_load_time=3.0,
                    highlight_elements=True,
                    viewport_expansion=500,
                )
                
                self._context = await self._browser.new_context(config=context_config)
                self._initialized = True
                logger.info(f"WebBrowserOperator initialized (headless={self.headless})")
                
            except ImportError as e:
                logger.error(f"browser_use not installed: {e}")
                raise ImportError(
                    "browser_use is required for web mode. Install with: pip install browser-use"
                ) from e
            except Exception as e:
                logger.error(f"Failed to initialize WebBrowserOperator: {e}")
                raise

    async def close(self) -> None:
        """Close browser_use browser and cleanup."""
        async with self._lock:
            try:
                if self._context:
                    await self._context.close()
                    self._context = None
                if self._browser:
                    await self._browser.close()
                    self._browser = None
                self._initialized = False
                logger.info("WebBrowserOperator closed")
            except Exception as e:
                logger.error(f"Error closing WebBrowserOperator: {e}")

    async def _get_page(self):
        """Get current page from context."""
        await self.initialize()
        if self._context:
            state = await self._context.get_state()
            return state
        return None

    async def navigate(self, url: str) -> BrowserResult:
        """Navigate to URL using browser_use."""
        try:
            await self.initialize()
            
            from browser_use.controller.service import Controller
            
            controller = Controller()
            action = {"go_to_url": {"url": url}}
            result = await controller.act(action, self._context)
            
            # Get current state for URL/title
            state = await self._context.get_state()
            
            return BrowserResult(
                success=True,
                output=f"Navigated to {url}",
                url=state.url if state else url,
                title=state.title if state else None,
            )
        except Exception as e:
            logger.error(f"Navigate failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def click(self, selector: str, index: int = 0) -> BrowserResult:
        """Click element using browser_use."""
        try:
            await self.initialize()
            
            from browser_use.controller.service import Controller
            
            controller = Controller()
            action = {"click_element": {"index": index}}
            result = await controller.act(action, self._context)
            
            return BrowserResult(success=True, output=f"Clicked element at index {index}")
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def input_text(self, selector: str, text: str, index: int = 0) -> BrowserResult:
        """Input text using browser_use."""
        try:
            await self.initialize()
            
            from browser_use.controller.service import Controller
            
            controller = Controller()
            action = {"input_text": {"index": index, "text": text}}
            result = await controller.act(action, self._context)
            
            return BrowserResult(success=True, output=f"Input text into element at index {index}")
        except Exception as e:
            logger.error(f"Input text failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def screenshot(self, full_page: bool = False) -> BrowserResult:
        """Take screenshot using browser_use."""
        try:
            await self.initialize()
            
            # browser_use provides screenshots in state
            state = await self._context.get_state()
            screenshot_b64 = state.screenshot if state else None
            
            return BrowserResult(
                success=True,
                screenshot=screenshot_b64,
                url=state.url if state else None,
                title=state.title if state else None,
            )
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def get_page_content(self) -> BrowserResult:
        """Get page content using browser_use."""
        try:
            await self.initialize()
            
            state = await self._context.get_state()
            
            return BrowserResult(
                success=True,
                output={
                    "url": state.url if state else None,
                    "title": state.title if state else None,
                    "elements": state.selector_map if state else None,
                },
                url=state.url if state else None,
                title=state.title if state else None,
            )
        except Exception as e:
            logger.error(f"Get content failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def extract_content(self, goal: str) -> BrowserResult:
        """Extract content based on goal using browser_use."""
        try:
            await self.initialize()
            
            from browser_use.controller.service import Controller
            
            controller = Controller()
            action = {"extract_content": {"goal": goal}}
            result = await controller.act(action, self._context)
            
            return BrowserResult(success=True, output=result)
        except Exception as e:
            logger.error(f"Extract content failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def scroll(self, direction: str = "down", amount: int = 500) -> BrowserResult:
        """Scroll using browser_use."""
        try:
            await self.initialize()
            
            from browser_use.controller.service import Controller
            
            controller = Controller()
            action_name = "scroll_down" if direction == "down" else "scroll_up"
            action = {action_name: {"amount": amount}}
            result = await controller.act(action, self._context)
            
            return BrowserResult(success=True, output=f"Scrolled {direction}")
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def go_back(self) -> BrowserResult:
        """Go back using browser_use."""
        try:
            await self.initialize()
            
            from browser_use.controller.service import Controller
            
            controller = Controller()
            action = {"go_back": {}}
            result = await controller.act(action, self._context)
            
            return BrowserResult(success=True, output="Navigated back")
        except Exception as e:
            logger.error(f"Go back failed: {e}")
            return BrowserResult(success=False, error=str(e))

    async def execute_action(self, action: BrowserAction, **kwargs) -> BrowserResult:
        """Execute generic browser action using browser_use."""
        action_map = {
            BrowserAction.GO_TO_URL: self.navigate,
            BrowserAction.CLICK_ELEMENT: self.click,
            BrowserAction.INPUT_TEXT: self.input_text,
            BrowserAction.SCREENSHOT: self.screenshot,
            BrowserAction.SCROLL_DOWN: lambda **kw: self.scroll("down", **kw),
            BrowserAction.SCROLL_UP: lambda **kw: self.scroll("up", **kw),
            BrowserAction.GO_BACK: self.go_back,
            BrowserAction.GET_DOM: self.get_page_content,
            BrowserAction.EXTRACT_CONTENT: self.extract_content,
        }
        
        handler = action_map.get(action)
        if handler:
            return await handler(**kwargs)
        return BrowserResult(success=False, error=f"Action {action} not supported")
