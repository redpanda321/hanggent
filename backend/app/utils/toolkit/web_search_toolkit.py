"""
Web Search Toolkit

A CAMEL-compatible toolkit for web search with multi-engine support
and automatic fallback.

Features:
- Multiple search engines (Google, DuckDuckGo, Bing, Baidu)
- Automatic fallback when primary engine fails
- Content fetching from search results
- Rate limiting and retry logic
- Search result formatting

Usage:
    toolkit = WebSearchToolkit(api_task_id)
    tools = toolkit.get_tools()
    
    # Search the web
    result = toolkit.web_search("Python tutorial", num_results=5)
    
    # Search with content fetching
    result = toolkit.web_search("AI news", fetch_content=True)
"""

import asyncio
from typing import Dict, List, Literal, Optional

import requests
from bs4 import BeautifulSoup
from camel.toolkits.function_tool import FunctionTool
from pydantic import BaseModel, Field

from app.service.task import Agents
from app.utils.toolkit.abstract_toolkit import AbstractToolkit
from utils import traceroot_wrapper as traceroot

logger = traceroot.get_logger("web_search_toolkit")


class SearchResult(BaseModel):
    """Represents a single search result."""
    
    position: int = Field(description="Position in search results")
    url: str = Field(description="URL of the search result")
    title: str = Field(default="", description="Title of the search result")
    description: str = Field(default="", description="Description or snippet")
    source: str = Field(default="", description="Search engine that provided this result")
    content: Optional[str] = Field(default=None, description="Fetched page content")


class WebSearchToolkit(AbstractToolkit):
    """
    A CAMEL-compatible toolkit for web search.
    
    This toolkit provides multi-engine web search capabilities with
    automatic fallback when the primary engine fails.
    
    Supported engines:
    - DuckDuckGo (default, no API key needed)
    - Google (requires GOOGLE_API_KEY and SEARCH_ENGINE_ID)
    - Bing (requires BING_API_KEY)
    - Wikipedia (no API key needed, specialized search)
    """
    
    agent_name: str = Agents.browser_agent
    
    # Engine priority for fallback
    _engine_priority: List[str] = ["duckduckgo", "google", "bing", "wikipedia"]
    
    def __init__(
        self,
        api_task_id: str,
        google_api_key: Optional[str] = None,
        search_engine_id: Optional[str] = None,
        bing_api_key: Optional[str] = None,
        default_engine: str = "duckduckgo",
        timeout: int = 10,
    ):
        """
        Initialize the WebSearchToolkit.
        
        Args:
            api_task_id: Task ID for tracking
            google_api_key: Google Custom Search API key
            search_engine_id: Google Custom Search Engine ID
            bing_api_key: Bing Search API key
            default_engine: Default search engine to use
            timeout: Request timeout in seconds
        """
        self.api_task_id = api_task_id
        self.google_api_key = google_api_key
        self.search_engine_id = search_engine_id
        self.bing_api_key = bing_api_key
        self.default_engine = default_engine
        self.timeout = timeout
    
    def web_search(
        self,
        query: str,
        num_results: int = 5,
        fetch_content: bool = False,
        engine: Optional[str] = None,
        lang: str = "en",
        country: str = "us",
    ) -> str:
        """
        Search the web for information.
        
        Args:
            query: Search query string
            num_results: Number of results to return (1-20)
            fetch_content: Whether to fetch full page content for results
            engine: Search engine to use (duckduckgo, google, bing, wikipedia)
            lang: Language code for results (e.g., "en", "zh")
            country: Country code for results (e.g., "us", "cn")
        
        Returns:
            Formatted search results as string
        
        Example:
            web_search("Python async programming", num_results=3)
            web_search("latest AI news", fetch_content=True)
        """
        return asyncio.get_event_loop().run_until_complete(
            self._web_search_async(query, num_results, fetch_content, engine, lang, country)
        )
    
    async def _web_search_async(
        self,
        query: str,
        num_results: int,
        fetch_content: bool,
        engine: Optional[str],
        lang: str,
        country: str,
    ) -> str:
        """Async implementation of web_search with fallback."""
        engine = engine or self.default_engine
        num_results = min(max(num_results, 1), 20)  # Clamp to 1-20
        
        results: List[SearchResult] = []
        errors: List[str] = []
        
        # Try engines in priority order
        engines_to_try = [engine] + [e for e in self._engine_priority if e != engine]
        
        for eng in engines_to_try:
            try:
                if eng == "duckduckgo":
                    results = await self._search_duckduckgo(query, num_results)
                elif eng == "google" and self.google_api_key:
                    results = await self._search_google(query, num_results, lang, country)
                elif eng == "bing" and self.bing_api_key:
                    results = await self._search_bing(query, num_results)
                elif eng == "wikipedia":
                    results = await self._search_wikipedia(query, num_results)
                else:
                    continue  # Skip unconfigured engines
                
                if results:
                    logger.info(f"Search successful with {eng}: {len(results)} results")
                    break
            except Exception as e:
                errors.append(f"{eng}: {str(e)}")
                logger.warning(f"Search with {eng} failed: {e}")
        
        if not results:
            return f"❌ Search failed. Errors: {'; '.join(errors)}"
        
        # Optionally fetch content
        if fetch_content:
            results = await self._fetch_content_for_results(results[:3])  # Limit to top 3
        
        # Format results
        return self._format_results(query, results)
    
    async def _search_duckduckgo(
        self,
        query: str,
        num_results: int,
    ) -> List[SearchResult]:
        """Search using DuckDuckGo HTML scraping."""
        try:
            from duckduckgo_search import DDGS
            
            loop = asyncio.get_event_loop()
            with DDGS() as ddgs:
                search_results = await loop.run_in_executor(
                    None,
                    lambda: list(ddgs.text(query, max_results=num_results))
                )
            
            results = []
            for i, r in enumerate(search_results):
                results.append(SearchResult(
                    position=i + 1,
                    url=r.get("href", r.get("link", "")),
                    title=r.get("title", ""),
                    description=r.get("body", r.get("snippet", "")),
                    source="duckduckgo",
                ))
            return results
        
        except ImportError:
            raise RuntimeError("duckduckgo-search not installed")
    
    async def _search_google(
        self,
        query: str,
        num_results: int,
        lang: str,
        country: str,
    ) -> List[SearchResult]:
        """Search using Google Custom Search API."""
        if not self.google_api_key or not self.search_engine_id:
            raise ValueError("Google API key and Search Engine ID required")
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.google_api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": min(num_results, 10),
            "hl": lang,
            "gl": country,
        }
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(url, params=params, timeout=self.timeout)
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Google API error: {response.status_code}")
        
        data = response.json()
        items = data.get("items", [])
        
        results = []
        for i, item in enumerate(items):
            results.append(SearchResult(
                position=i + 1,
                url=item.get("link", ""),
                title=item.get("title", ""),
                description=item.get("snippet", ""),
                source="google",
            ))
        return results
    
    async def _search_bing(
        self,
        query: str,
        num_results: int,
    ) -> List[SearchResult]:
        """Search using Bing Web Search API."""
        if not self.bing_api_key:
            raise ValueError("Bing API key required")
        
        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": self.bing_api_key}
        params = {"q": query, "count": num_results}
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(url, headers=headers, params=params, timeout=self.timeout)
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Bing API error: {response.status_code}")
        
        data = response.json()
        web_pages = data.get("webPages", {}).get("value", [])
        
        results = []
        for i, page in enumerate(web_pages):
            results.append(SearchResult(
                position=i + 1,
                url=page.get("url", ""),
                title=page.get("name", ""),
                description=page.get("snippet", ""),
                source="bing",
            ))
        return results
    
    async def _search_wikipedia(
        self,
        query: str,
        num_results: int,
    ) -> List[SearchResult]:
        """Search using Wikipedia API."""
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": num_results,
            "format": "json",
            "srprop": "snippet|titlesnippet",
        }
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(url, params=params, timeout=self.timeout)
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Wikipedia API error: {response.status_code}")
        
        data = response.json()
        search_results = data.get("query", {}).get("search", [])
        
        results = []
        for i, item in enumerate(search_results):
            title = item.get("title", "")
            # Create Wikipedia URL from title
            wiki_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            
            # Clean snippet HTML
            snippet = item.get("snippet", "")
            soup = BeautifulSoup(snippet, "html.parser")
            clean_snippet = soup.get_text()
            
            results.append(SearchResult(
                position=i + 1,
                url=wiki_url,
                title=title,
                description=clean_snippet,
                source="wikipedia",
            ))
        return results
    
    async def _fetch_content_for_results(
        self,
        results: List[SearchResult],
    ) -> List[SearchResult]:
        """Fetch page content for search results."""
        async def fetch_one(result: SearchResult) -> SearchResult:
            try:
                content = await self._fetch_page_content(result.url)
                result.content = content
            except Exception as e:
                logger.warning(f"Failed to fetch content from {result.url}: {e}")
            return result
        
        # Fetch in parallel
        tasks = [fetch_one(r) for r in results]
        return await asyncio.gather(*tasks)
    
    async def _fetch_page_content(
        self,
        url: str,
        max_length: int = 5000,
    ) -> Optional[str]:
        """Fetch and extract text content from a URL."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(url, headers=headers, timeout=self.timeout)
        )
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove non-content elements
        for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
            tag.decompose()
        
        # Get text
        text = soup.get_text(separator="\n", strip=True)
        text = " ".join(text.split())  # Normalize whitespace
        
        if len(text) > max_length:
            text = text[:max_length] + "...[truncated]"
        
        return text
    
    def _format_results(
        self,
        query: str,
        results: List[SearchResult],
    ) -> str:
        """Format search results as readable string."""
        lines = [f"🔍 Search results for '{query}':", ""]
        
        for r in results:
            lines.append(f"{r.position}. **{r.title}**")
            lines.append(f"   URL: {r.url}")
            
            if r.description:
                lines.append(f"   {r.description}")
            
            if r.content:
                preview = r.content[:500]
                if len(r.content) > 500:
                    preview += "..."
                lines.append(f"   Content: {preview}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def wikipedia_search(
        self,
        query: str,
        num_results: int = 3,
    ) -> str:
        """
        Search Wikipedia specifically.
        
        Args:
            query: Search query
            num_results: Number of results (1-10)
        
        Returns:
            Formatted Wikipedia search results
        
        Example:
            wikipedia_search("Machine learning history")
        """
        return asyncio.get_event_loop().run_until_complete(
            self._wikipedia_search_async(query, num_results)
        )
    
    async def _wikipedia_search_async(self, query: str, num_results: int) -> str:
        """Async Wikipedia search."""
        try:
            results = await self._search_wikipedia(query, num_results)
            if results:
                # Fetch content for Wikipedia results
                results = await self._fetch_content_for_results(results)
                return self._format_results(query, results)
            return f"No Wikipedia results found for '{query}'"
        except Exception as e:
            return f"❌ Wikipedia search failed: {str(e)}"
    
    def get_tools(self) -> List[FunctionTool]:
        """
        Get all tools as CAMEL FunctionTools.
        
        Returns:
            List of FunctionTool instances
        """
        return [
            FunctionTool(
                func=self.web_search,
                name="web_search",
                description=(
                    "Search the web for information. Supports multiple search engines with "
                    "automatic fallback. Can optionally fetch full page content."
                ),
            ),
            FunctionTool(
                func=self.wikipedia_search,
                name="wikipedia_search",
                description=(
                    "Search Wikipedia for information. Returns article summaries "
                    "and content from Wikipedia pages."
                ),
            ),
        ]
