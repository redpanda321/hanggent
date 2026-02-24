"""
Browser Use Toolkit

A CAMEL-compatible toolkit for browser automation using browser-use library.
This toolkit provides a wrapper around browser-use functionality for web
navigation, element interaction, and content extraction.

Features:
- URL navigation and page control
- Element clicking and text input
- Scrolling (by pixels or to text)
- Tab management
- Content extraction with LLM assistance
- Screenshot capture
- Web search integration

Usage:
    toolkit = BrowserUseToolkit(api_task_id)
    tools = toolkit.get_tools()
    
    # Navigate to a URL
    result = toolkit.go_to_url("https://example.com")
    
    # Click an element
    result = toolkit.click_element(index=5)
    
    # Extract content
    result = toolkit.extract_content("Find the main article title")
"""

import asyncio
import base64
from typing import Any, Dict, List, Literal, Optional

from camel.toolkits.function_tool import FunctionTool
from pydantic import Field

from app.service.task import Agents
from app.utils.toolkit.abstract_toolkit import AbstractToolkit
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("browser_use_toolkit")

# Browser action types
BrowserAction = Literal[
    "go_to_url",
    "click_element",
    "input_text",
    "scroll_down",
    "scroll_up",
    "scroll_to_text",
    "send_keys",
    "get_dropdown_options",
    "select_dropdown_option",
    "go_back",
    "refresh",
    "web_search",
    "wait",
    "extract_content",
    "switch_tab",
    "open_tab",
    "close_tab",
    "get_screenshot",
    "get_page_content",
]


class BrowserUseToolkit(AbstractToolkit):
    """
    A CAMEL-compatible toolkit for browser automation.
    
    This toolkit wraps browser-use library functionality for use with
    CAMEL agents. It provides methods for web navigation, interaction,
    and content extraction.
    
    The toolkit manages browser lifecycle and provides both sync and
    async interfaces.
    """
    
    agent_name: str = Agents.browser_agent
    
    def __init__(
        self,
        api_task_id: str,
        headless: bool = True,
        disable_security: bool = False,
        browser_type: str = "chromium",
        cdp_url: Optional[str] = None,
    ):
        """
        Initialize the BrowserUseToolkit.
        
        Args:
            api_task_id: Task ID for tracking
            headless: Run browser in headless mode
            disable_security: Disable browser security features
            browser_type: Browser type (chromium, firefox, webkit)
            cdp_url: Chrome DevTools Protocol URL (for Electron mode)
        """
        self.api_task_id = api_task_id
        self.headless = headless
        self.disable_security = disable_security
        self.browser_type = browser_type
        self.cdp_url = cdp_url
        
        # Browser instances (lazy-initialized)
        self._browser = None
        self._context = None
        self._dom_service = None
        self._lock = asyncio.Lock()
        
        # State tracking
        self._initialized = False
        self._current_url: Optional[str] = None
        self._tabs: List[Dict[str, Any]] = []
    
    @property
    def is_initialized(self) -> bool:
        """Check if browser is initialized."""
        return self._initialized and self._browser is not None
    
    async def _ensure_browser_initialized(self):
        """Ensure browser and context are initialized."""
        if self._initialized:
            return
        
        try:
            # Try to import browser-use
            from browser_use import Browser as BrowserUseBrowser
            from browser_use import BrowserConfig
            from browser_use.browser.context import BrowserContext, BrowserContextConfig
            from browser_use.dom.service import DomService
            
            # Create browser config
            config_kwargs = {
                "headless": self.headless,
                "disable_security": self.disable_security,
            }
            
            if self.cdp_url:
                config_kwargs["cdp_url"] = self.cdp_url
            
            # Initialize browser
            self._browser = BrowserUseBrowser(BrowserConfig(**config_kwargs))
            
            # Create context
            context_config = BrowserContextConfig()
            self._context = await self._browser.new_context(context_config)
            
            # Initialize DOM service
            page = await self._context.get_current_page()
            self._dom_service = DomService(page)
            
            self._initialized = True
            logger.info("Browser initialized successfully")
        
        except ImportError as e:
            logger.error(f"browser-use not installed: {e}")
            raise RuntimeError(
                "browser-use library not installed. Install with: pip install browser-use"
            )
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise
    
    async def close(self):
        """Close browser and cleanup resources."""
        async with self._lock:
            if self._browser:
                try:
                    await self._browser.close()
                except Exception as e:
                    logger.warning(f"Error closing browser: {e}")
                finally:
                    self._browser = None
                    self._context = None
                    self._dom_service = None
                    self._initialized = False
                    logger.info("Browser closed")
    
    def go_to_url(self, url: str) -> str:
        """
        Navigate to a URL.
        
        Args:
            url: The URL to navigate to
        
        Returns:
            Success message or error description
        
        Example:
            go_to_url("https://example.com")
        """
        return asyncio.get_event_loop().run_until_complete(
            self._go_to_url_async(url)
        )
    
    async def _go_to_url_async(self, url: str) -> str:
        """Async implementation of go_to_url."""
        async with self._lock:
            try:
                await self._ensure_browser_initialized()
                page = await self._context.get_current_page()
                await page.goto(url)
                await page.wait_for_load_state()
                self._current_url = url
                return f"✅ Navigated to {url}"
            except Exception as e:
                return f"❌ Failed to navigate: {str(e)}"
    
    def go_back(self) -> str:
        """
        Navigate back in browser history.
        
        Returns:
            Success message or error description
        """
        return asyncio.get_event_loop().run_until_complete(
            self._go_back_async()
        )
    
    async def _go_back_async(self) -> str:
        """Async implementation of go_back."""
        async with self._lock:
            try:
                await self._ensure_browser_initialized()
                await self._context.go_back()
                return "✅ Navigated back"
            except Exception as e:
                return f"❌ Failed to go back: {str(e)}"
    
    def refresh(self) -> str:
        """
        Refresh the current page.
        
        Returns:
            Success message or error description
        """
        return asyncio.get_event_loop().run_until_complete(
            self._refresh_async()
        )
    
    async def _refresh_async(self) -> str:
        """Async implementation of refresh."""
        async with self._lock:
            try:
                await self._ensure_browser_initialized()
                await self._context.refresh_page()
                return "✅ Page refreshed"
            except Exception as e:
                return f"❌ Failed to refresh: {str(e)}"
    
    def click_element(self, index: int) -> str:
        """
        Click an element by its index.
        
        The index corresponds to numbered elements shown in the current
        browser state/screenshot.
        
        Args:
            index: Element index to click
        
        Returns:
            Success message or error description
        
        Example:
            click_element(5)  # Click element #5
        """
        return asyncio.get_event_loop().run_until_complete(
            self._click_element_async(index)
        )
    
    async def _click_element_async(self, index: int) -> str:
        """Async implementation of click_element."""
        async with self._lock:
            try:
                await self._ensure_browser_initialized()
                element = await self._context.get_dom_element_by_index(index)
                if not element:
                    return f"❌ Element with index {index} not found"
                
                download_path = await self._context._click_element_node(element)
                result = f"✅ Clicked element at index {index}"
                if download_path:
                    result += f" - Downloaded file to {download_path}"
                return result
            except Exception as e:
                return f"❌ Failed to click: {str(e)}"
    
    def input_text(self, index: int, text: str) -> str:
        """
        Input text into an element.
        
        Args:
            index: Element index to input text into
            text: Text to input
        
        Returns:
            Success message or error description
        
        Example:
            input_text(3, "Hello World")  # Type into element #3
        """
        return asyncio.get_event_loop().run_until_complete(
            self._input_text_async(index, text)
        )
    
    async def _input_text_async(self, index: int, text: str) -> str:
        """Async implementation of input_text."""
        async with self._lock:
            try:
                await self._ensure_browser_initialized()
                element = await self._context.get_dom_element_by_index(index)
                if not element:
                    return f"❌ Element with index {index} not found"
                
                await self._context._input_text_element_node(element, text)
                return f"✅ Input '{text}' into element at index {index}"
            except Exception as e:
                return f"❌ Failed to input text: {str(e)}"
    
    def scroll(
        self,
        direction: Literal["up", "down"] = "down",
        pixels: int = 500,
    ) -> str:
        """
        Scroll the page.
        
        Args:
            direction: Scroll direction ("up" or "down")
            pixels: Number of pixels to scroll
        
        Returns:
            Success message
        
        Example:
            scroll(direction="down", pixels=300)
        """
        return asyncio.get_event_loop().run_until_complete(
            self._scroll_async(direction, pixels)
        )
    
    async def _scroll_async(self, direction: str, pixels: int) -> str:
        """Async implementation of scroll."""
        async with self._lock:
            try:
                await self._ensure_browser_initialized()
                multiplier = -1 if direction == "up" else 1
                await self._context.execute_javascript(
                    f"window.scrollBy(0, {multiplier * pixels});"
                )
                return f"✅ Scrolled {direction} by {pixels} pixels"
            except Exception as e:
                return f"❌ Failed to scroll: {str(e)}"
    
    def scroll_to_text(self, text: str) -> str:
        """
        Scroll to make specific text visible.
        
        Args:
            text: Text to scroll to
        
        Returns:
            Success message or error description
        
        Example:
            scroll_to_text("Contact Us")
        """
        return asyncio.get_event_loop().run_until_complete(
            self._scroll_to_text_async(text)
        )
    
    async def _scroll_to_text_async(self, text: str) -> str:
        """Async implementation of scroll_to_text."""
        async with self._lock:
            try:
                await self._ensure_browser_initialized()
                page = await self._context.get_current_page()
                locator = page.get_by_text(text, exact=False)
                await locator.scroll_into_view_if_needed()
                return f"✅ Scrolled to text: '{text}'"
            except Exception as e:
                return f"❌ Failed to scroll to text: {str(e)}"
    
    def send_keys(self, keys: str) -> str:
        """
        Send keyboard keys/shortcuts.
        
        Args:
            keys: Keys to send (e.g., "Enter", "Tab", "Control+C")
        
        Returns:
            Success message
        
        Example:
            send_keys("Enter")
            send_keys("Control+A")
        """
        return asyncio.get_event_loop().run_until_complete(
            self._send_keys_async(keys)
        )
    
    async def _send_keys_async(self, keys: str) -> str:
        """Async implementation of send_keys."""
        async with self._lock:
            try:
                await self._ensure_browser_initialized()
                page = await self._context.get_current_page()
                await page.keyboard.press(keys)
                return f"✅ Sent keys: {keys}"
            except Exception as e:
                return f"❌ Failed to send keys: {str(e)}"
    
    def get_screenshot(self, full_page: bool = False) -> str:
        """
        Capture a screenshot of the current page.
        
        Args:
            full_page: Capture full page (not just viewport)
        
        Returns:
            Base64-encoded screenshot or error
        """
        return asyncio.get_event_loop().run_until_complete(
            self._get_screenshot_async(full_page)
        )
    
    async def _get_screenshot_async(self, full_page: bool) -> str:
        """Async implementation of get_screenshot."""
        async with self._lock:
            try:
                await self._ensure_browser_initialized()
                page = await self._context.get_current_page()
                screenshot = await page.screenshot(full_page=full_page)
                encoded = base64.b64encode(screenshot).decode("utf-8")
                return f"✅ Screenshot captured (base64 length: {len(encoded)})"
            except Exception as e:
                return f"❌ Failed to capture screenshot: {str(e)}"
    
    def get_page_content(self, max_length: int = 5000) -> str:
        """
        Get the current page's text content.
        
        Args:
            max_length: Maximum content length to return
        
        Returns:
            Page text content
        """
        return asyncio.get_event_loop().run_until_complete(
            self._get_page_content_async(max_length)
        )
    
    async def _get_page_content_async(self, max_length: int) -> str:
        """Async implementation of get_page_content."""
        async with self._lock:
            try:
                await self._ensure_browser_initialized()
                page = await self._context.get_current_page()
                content = await page.inner_text("body")
                if len(content) > max_length:
                    content = content[:max_length] + "...[truncated]"
                return content
            except Exception as e:
                return f"❌ Failed to get content: {str(e)}"
    
    def wait(self, seconds: int = 1) -> str:
        """
        Wait for specified seconds.
        
        Args:
            seconds: Number of seconds to wait
        
        Returns:
            Success message
        """
        return asyncio.get_event_loop().run_until_complete(
            self._wait_async(seconds)
        )
    
    async def _wait_async(self, seconds: int) -> str:
        """Async implementation of wait."""
        await asyncio.sleep(seconds)
        return f"✅ Waited {seconds} seconds"
    
    def get_tools(self) -> List[FunctionTool]:
        """
        Get all tools as CAMEL FunctionTools.
        
        Returns:
            List of FunctionTool instances
        """
        return [
            FunctionTool(
                func=self.go_to_url,
                name="browser_go_to_url",
                description="Navigate to a URL in the browser",
            ),
            FunctionTool(
                func=self.go_back,
                name="browser_go_back",
                description="Navigate back in browser history",
            ),
            FunctionTool(
                func=self.refresh,
                name="browser_refresh",
                description="Refresh the current page",
            ),
            FunctionTool(
                func=self.click_element,
                name="browser_click_element",
                description=(
                    "Click an element by its index. The index corresponds to "
                    "numbered elements shown in the browser state/screenshot."
                ),
            ),
            FunctionTool(
                func=self.input_text,
                name="browser_input_text",
                description="Input text into an element at the specified index",
            ),
            FunctionTool(
                func=self.scroll,
                name="browser_scroll",
                description="Scroll the page up or down by specified pixels",
            ),
            FunctionTool(
                func=self.scroll_to_text,
                name="browser_scroll_to_text",
                description="Scroll to make specific text visible on the page",
            ),
            FunctionTool(
                func=self.send_keys,
                name="browser_send_keys",
                description="Send keyboard keys or shortcuts (e.g., 'Enter', 'Tab', 'Control+C')",
            ),
            FunctionTool(
                func=self.get_screenshot,
                name="browser_get_screenshot",
                description="Capture a screenshot of the current page",
            ),
            FunctionTool(
                func=self.get_page_content,
                name="browser_get_page_content",
                description="Get the text content of the current page",
            ),
            FunctionTool(
                func=self.wait,
                name="browser_wait",
                description="Wait for specified seconds before continuing",
            ),
        ]
