"""Tavily 웹 검색 - 정보 보강용."""
import os

try:
    from langchain_tavily import TavilySearch
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False


def web_search(query: str, max_results: int = 5) -> str:
    """
    Tavily API로 웹 검색. TAVILY_API_KEY 필요.
    정보 없음 섹션 보강 시 사용.
    """
    if not TAVILY_AVAILABLE or not os.environ.get("TAVILY_API_KEY"):
        return ""
    try:
        tool = TavilySearch(max_results=max_results)
        result = tool.invoke({"query": query})
        if isinstance(result, list):
            texts = []
            for r in result[:max_results]:
                if isinstance(r, dict):
                    t = r.get("content") or r.get("raw_content") or r.get("title", "") + " " + r.get("snippet", "")
                    if t:
                        texts.append(t)
                else:
                    texts.append(str(r))
            return "\n\n".join(texts)
        if isinstance(result, dict) and "error" not in result:
            return str(result.get("results", result))
        return str(result) if not isinstance(result, dict) else ""
    except Exception:
        return ""
