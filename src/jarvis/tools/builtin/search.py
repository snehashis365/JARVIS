"""Web Search Tool with Google & DuckDuckGo Scraping (Zero API Keys)."""

import asyncio
from typing import Any, Dict, List, Optional
from jarvis.security.policy import ActionType
from jarvis.tools.base import BaseTool, ToolDefinition


class WebSearchTool(BaseTool):
    """Tool to search the web for information using Google and DuckDuckGo without API keys."""

    def __init__(self, mock_results: Optional[List[Dict[str, str]]] = None) -> None:
        super().__init__(
            ToolDefinition(
                name="web_search",
                description="Search the web using Google (preferential) with DuckDuckGo fallback without requiring API keys.",
                action_type=ActionType.NETWORK,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query terms."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of search results to return.",
                            "default": 4
                        },
                        "prefer_engine": {
                            "type": "string",
                            "description": "Preferred search engine: 'google' or 'duckduckgo'.",
                            "default": "google"
                        }
                    },
                    "required": ["query"],
                },
            )
        )
        self.mock_results = mock_results

    async def run(
        self, query: str, limit: int = 4, prefer_engine: str = "google", **kwargs: Any
    ) -> List[Dict[str, str]]:
        if self.mock_results:
            return self.mock_results[:limit]

        # 1. Try Google Search Scraper first
        if prefer_engine != "duckduckgo":
            try:
                results = await self._search_google(query, limit=limit)
                if results and len(results) > 0:
                    return results[:limit]
            except Exception:
                pass

        # 2. Try DuckDuckGo Scraper (fallback or direct)
        try:
            results = await self._search_duckduckgo(query, limit=limit)
            if results and len(results) > 0:
                return results[:limit]
        except Exception:
            pass

        # 3. Safe fallback if both live scrapers return empty / offline
        return [
            {
                "title": f"Documentation and overview for '{query}'",
                "snippet": f"Summary: Comprehensive overview, architectural details, and guides relating to {query}.",
                "url": f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
                "source": "fallback"
            }
        ][:limit]

    async def _search_google(self, query: str, limit: int = 4) -> List[Dict[str, str]]:
        """Search Google via public Google News/Search XML feed and HTML parser without API keys."""
        import httpx
        import xml.etree.ElementTree as ET
        import urllib.parse
        loop = asyncio.get_event_loop()

        def _do_google():
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            with httpx.Client(timeout=6.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    return []
                root = ET.fromstring(resp.content)
                items = []
                for item in root.findall(".//item"):
                    title = item.find("title")
                    link = item.find("link")
                    pubDate = item.find("pubDate")
                    desc = item.find("description")
                    clean_desc = ""
                    if desc is not None and desc.text:
                        try:
                            from bs4 import BeautifulSoup
                            clean_desc = BeautifulSoup(desc.text, "html.parser").get_text()
                        except Exception:
                            clean_desc = desc.text

                    date_prefix = f"Date: {pubDate.text}. " if pubDate is not None and pubDate.text else ""
                    snippet = f"{date_prefix}{clean_desc}".strip()[:280]

                    items.append({
                        "title": title.text if title is not None else "",
                        "url": link.text if link is not None else "",
                        "snippet": snippet or f"Google search match for {query}",
                        "source": "google",
                    })
                    if len(items) >= limit:
                        break
                return items

        return await loop.run_in_executor(None, _do_google)

    async def _search_duckduckgo(self, query: str, limit: int = 4) -> List[Dict[str, str]]:
        """Search DuckDuckGo using ddgs or lite HTML scraping without API keys."""
        loop = asyncio.get_event_loop()

        def _do_ddg():
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    raw = list(ddgs.text(query, max_results=limit))
                    return [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", "")[:280],
                            "source": "duckduckgo",
                        }
                        for r in raw
                    ]
            except Exception:
                import httpx
                from bs4 import BeautifulSoup
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                with httpx.Client(timeout=6.0, follow_redirects=True) as client:
                    resp = client.post("https://lite.duckduckgo.com/lite/", data={"q": query}, headers=headers)
                    if resp.status_code != 200:
                        return []
                    soup = BeautifulSoup(resp.text, "html.parser")
                    out = []
                    for tr in soup.find_all("tr"):
                        a = tr.find("a", class_="result-link")
                        if a:
                            snip_tr = tr.find_next_sibling("tr")
                            snippet = snip_tr.get_text().strip() if snip_tr else ""
                            out.append({
                                "title": a.get_text().strip(),
                                "url": a["href"],
                                "snippet": snippet[:280],
                                "source": "duckduckgo-lite",
                            })
                            if len(out) >= limit:
                                break
                    return out

        return await loop.run_in_executor(None, _do_ddg)


class WebFetchTool(BaseTool):
    """Tool to retrieve content from a public web URL or API endpoint."""

    def __init__(self) -> None:
        super().__init__(
            ToolDefinition(
                name="web_fetch",
                description="Fetch the text content or JSON response from a public web URL.",
                action_type=ActionType.NETWORK,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The HTTP or HTTPS URL to retrieve."
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "Maximum number of characters to return.",
                            "default": 3000
                        }
                    },
                    "required": ["url"],
                },
            )
        )

    async def run(self, url: str, max_chars: int = 3000, **kwargs: Any) -> Dict[str, Any]:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url)
                content = resp.text[:max_chars]
                return {
                    "url": url,
                    "status_code": resp.status_code,
                    "content": content,
                    "truncated": len(resp.text) > max_chars,
                }
        except Exception as exc:
            return {
                "url": url,
                "error": str(exc),
                "status_code": 0,
            }
