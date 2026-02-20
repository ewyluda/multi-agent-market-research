"""Tavily AI search client wrapper for enhanced market research.

Provides async search capabilities with fallbacks for news aggregation,
company research, and market context gathering.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

try:
    from tavily import AsyncTavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    AsyncTavilyClient = None


class TavilyClient:
    """Wrapper for Tavily AI search with async support and error handling."""
    
    def __init__(self, api_key: str):
        """
        Initialize Tavily client.
        
        Args:
            api_key: Tavily API key
        """
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        self._client: Optional[Any] = None
        
        if TAVILY_AVAILABLE and api_key:
            try:
                self._client = AsyncTavilyClient(api_key=api_key)
            except Exception as e:
                self.logger.warning(f"Failed to initialize Tavily client: {e}")
    
    @property
    def is_available(self) -> bool:
        """Check if Tavily client is available and initialized."""
        return TAVILY_AVAILABLE and self._client is not None
    
    async def search_news(
        self,
        query: str,
        max_results: int = 20,
        days: int = 7,
        include_answer: bool = True,
        include_raw_content: bool = True,
        search_depth: str = "advanced"
    ) -> Dict[str, Any]:
        """
        Search for news articles with Tavily.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            days: Number of days to look back
            include_answer: Include AI-generated answer
            include_raw_content: Include full article content
            search_depth: "basic" or "advanced"
            
        Returns:
            Dict with search results and metadata
        """
        if not self.is_available:
            return {"success": False, "error": "Tavily not available", "results": []}
        
        try:
            # Calculate time cutoff
            time_cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            response = await self._client.search(
                query=query,
                search_type="news",
                topic="finance",
                time_range=f"{days}d",
                max_results=max_results,
                include_answer=include_answer,
                include_raw_content=include_raw_content,
                search_depth=search_depth
            )
            
            # Normalize response format
            articles = []
            for result in response.get("results", []):
                article = {
                    "title": result.get("title", ""),
                    "source": result.get("source", ""),
                    "url": result.get("url", ""),
                    "published_at": result.get("published_date", ""),
                    "content": result.get("raw_content", result.get("content", "")),
                    "description": result.get("content", ""),  # Snippet
                    "relevance_score": result.get("score", 0.5),
                    "author": "",  # Tavily doesn't consistently provide author
                }
                articles.append(article)
            
            return {
                "success": True,
                "articles": articles,
                "total_count": len(articles),
                "ai_summary": response.get("answer"),
                "query": query,
                "source": "tavily"
            }
            
        except Exception as e:
            self.logger.error(f"Tavily news search failed: {e}")
            return {"success": False, "error": str(e), "results": []}
    
    async def search_company_context(
        self,
        company_name: str,
        ticker: str,
        context_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Search for recent company developments across multiple dimensions.
        
        Args:
            company_name: Full company name
            ticker: Stock ticker symbol
            context_types: List of context types to search (earnings, products, leadership, risks)
            
        Returns:
            Dict with categorized context results
        """
        if not self.is_available:
            return {"success": False, "error": "Tavily not available"}
        
        context_types = context_types or ["earnings", "products", "leadership", "risks"]
        
        # Build queries for each context type
        query_map = {
            "earnings": f"{company_name} {ticker} earnings call transcript latest results",
            "products": f"{company_name} {ticker} product launch announcement news",
            "leadership": f"{company_name} {ticker} CEO CFO management changes executive",
            "risks": f"{company_name} {ticker} risks challenges regulatory SEC investigation",
            "competition": f"{company_name} {ticker} vs competitors market share competition",
            "guidance": f"{company_name} {ticker} forward guidance forecast outlook",
        }
        
        # Run searches in parallel
        tasks = []
        for ctx_type in context_types:
            query = query_map.get(ctx_type, f"{company_name} {ticker} {ctx_type}")
            task = self._search_single_context(ctx_type, query)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        context_data = {}
        for i, ctx_type in enumerate(context_types):
            result = results[i]
            if isinstance(result, Exception):
                self.logger.warning(f"Tavily search failed for {ctx_type}: {result}")
                context_data[ctx_type] = {"success": False, "error": str(result), "items": []}
            else:
                context_data[ctx_type] = result
        
        return {
            "success": True,
            "context_data": context_data,
            "company": company_name,
            "ticker": ticker
        }
    
    async def _search_single_context(self, context_type: str, query: str) -> Dict[str, Any]:
        """Search for a single context type."""
        try:
            response = await self._client.search(
                query=query,
                max_results=10,
                time_range="30d",
                include_answer=True,
                include_raw_content=False,  # Snippets only for context
                search_depth="basic"
            )
            
            items = []
            for result in response.get("results", []):
                items.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", ""),
                    "source": result.get("source", ""),
                    "published_date": result.get("published_date", "")
                })
            
            return {
                "success": True,
                "type": context_type,
                "items": items,
                "ai_summary": response.get("answer"),
                "count": len(items)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e), "items": [], "type": context_type}
    
    async def get_market_narrative(
        self,
        ticker: str,
        company_name: str = ""
    ) -> Dict[str, Any]:
        """
        Get current market narrative and analyst sentiment for a ticker.
        
        Args:
            ticker: Stock ticker
            company_name: Optional company name
            
        Returns:
            Dict with market narrative data
        """
        if not self.is_available:
            return {"success": False, "error": "Tavily not available"}
        
        # Build search query
        name_part = f"{company_name} " if company_name else ""
        queries = [
            f"{name_part}{ticker} stock analyst upgrade downgrade rating today",
            f"{name_part}{ticker} stock why up down today news",
            f"{name_part}{ticker} price target analyst consensus"
        ]
        
        # Run searches
        all_items = []
        answers = []
        
        for query in queries:
            try:
                response = await self._client.search(
                    query=query,
                    max_results=10,
                    time_range="7d",
                    include_answer=True,
                    include_raw_content=False,
                    search_depth="advanced"
                )
                
                for result in response.get("results", []):
                    all_items.append({
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "snippet": result.get("content", ""),
                        "source": result.get("source", "")
                    })
                
                if response.get("answer"):
                    answers.append(response["answer"])
                    
            except Exception as e:
                self.logger.warning(f"Market narrative query failed: {e}")
        
        # Combine answers into narrative
        narrative = "\n\n".join(answers) if answers else ""
        
        return {
            "success": True,
            "ticker": ticker,
            "narrative": narrative,
            "recent_items": all_items[:15],
            "item_count": len(all_items)
        }
    
    async def extract_article_content(self, url: str) -> Dict[str, Any]:
        """
        Extract full content from a specific URL using Tavily extract.
        
        Args:
            url: Article URL to extract
            
        Returns:
            Dict with extracted content
        """
        if not self.is_available:
            return {"success": False, "error": "Tavily not available"}
        
        try:
            # Tavily's extract feature
            response = await self._client.extract(urls=[url])
            
            results = response.get("results", [])
            if results:
                return {
                    "success": True,
                    "url": url,
                    "content": results[0].get("content", ""),
                    "title": results[0].get("title", ""),
                    "source": "tavily_extract"
                }
            else:
                return {"success": False, "error": "No content extracted", "url": url}
                
        except Exception as e:
            self.logger.error(f"Tavily extract failed for {url}: {e}")
            return {"success": False, "error": str(e), "url": url}


def get_tavily_client(config: Dict[str, Any]) -> TavilyClient:
    """
    Factory function to create Tavily client from config.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        TavilyClient instance
    """
    api_key = config.get("TAVILY_API_KEY", "")
    return TavilyClient(api_key)
