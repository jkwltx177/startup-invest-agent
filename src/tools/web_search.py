import os
from typing import List, Tuple


class TavilyWebSearch:
    """Tavily 기반 웹 검색 래퍼"""

    def __init__(self, max_results: int = 5):
        self.max_results = max_results
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from tavily import TavilyClient
                api_key = os.getenv("TAVILY_API_KEY")
                if not api_key:
                    raise ValueError("TAVILY_API_KEY environment variable not set")
                self._client = TavilyClient(api_key=api_key)
            except ImportError:
                raise ImportError("tavily-python package not installed. Run: uv add tavily-python")
        return self._client

    def search(self, query: str, max_results: int = None) -> List[dict]:
        """
        Tavily로 웹 검색 수행.
        Returns: List of {title, url, content, score}
        """
        k = max_results or self.max_results
        try:
            client = self._get_client()
            response = client.search(
                query=query,
                max_results=k,
                search_depth="advanced",
                include_raw_content=False,
            )
            results = []
            for r in response.get("results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0.0),
                })
            return results
        except Exception as e:
            print(f"[TavilyWebSearch] search error: {e}")
            return []

    def get_context(self, query: str, max_results: int = None) -> Tuple[str, List[str]]:
        """
        검색 결과를 컨텍스트 문자열 + 소스 URL 리스트로 반환
        Returns: (context_str, source_urls)
        """
        results = self.search(query, max_results=max_results)
        if not results:
            return "", []

        parts = []
        urls = []
        for r in results:
            url = r.get("url", "")
            title = r.get("title", "")
            content = r.get("content", "")
            if url and url not in urls:
                urls.append(url)
            parts.append(f"[Web: {title}] ({url})\n{content}")

        context = "\n\n".join(parts)
        return context, urls
