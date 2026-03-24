"""Tavily 웹 검색 - 정보 보강용."""
import os
from typing import Any, List

try:
    from langchain_tavily import TavilySearch
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False


def _parse_tavily_to_items(result: Any, max_results: int) -> List[dict]:
    """Tavily 응답을 {title, url, content} 리스트로 정규화."""
    items: List[dict] = []
    if isinstance(result, list):
        for r in result[:max_results]:
            if isinstance(r, dict):
                items.append(
                    {
                        "title": str(r.get("title", "") or ""),
                        "url": str(r.get("url", "") or ""),
                        "content": str(
                            r.get("content")
                            or r.get("raw_content")
                            or r.get("snippet")
                            or ""
                        )[:2500],
                    }
                )
        return items
    if isinstance(result, dict) and "error" not in result:
        rows = result.get("results") or result.get("answer") or []
        if isinstance(rows, list):
            for r in rows[:max_results]:
                if isinstance(r, dict):
                    items.append(
                        {
                            "title": str(r.get("title", "") or ""),
                            "url": str(r.get("url", "") or ""),
                            "content": str(
                                r.get("content")
                                or r.get("raw_content")
                                or r.get("snippet")
                                or ""
                            )[:2500],
                        }
                    )
    return items


def web_search_structured(query: str, max_results: int = 5) -> List[dict]:
    """Tavily 검색. [{title, url, content}, ...] 반환."""
    if not TAVILY_AVAILABLE or not os.environ.get("TAVILY_API_KEY"):
        return []
    try:
        tool = TavilySearch(max_results=max_results)
        result = tool.invoke({"query": query})
        return _parse_tavily_to_items(result, max_results)
    except Exception:
        return []


def web_search(query: str, max_results: int = 5) -> str:
    """
    Tavily API로 웹 검색. TAVILY_API_KEY 필요.
    하위 호환: 본문만 이어붙인 문자열.
    """
    items = web_search_structured(query, max_results=max_results)
    if not items:
        return ""
    parts = []
    for it in items:
        line = f"{it.get('title', '')}\n{it.get('url', '')}\n{it.get('content', '')}"
        parts.append(line.strip())
    return "\n\n---\n\n".join(parts)


def format_web_items_for_prompt(items: List[dict]) -> str:
    """LLM 프롬프트용: 출처 추적 가능한 블록."""
    if not items:
        return ""
    lines = []
    for i, it in enumerate(items, 1):
        lines.append(
            f"[보조자료 {i}] 제목: {it.get('title', '')}\n"
            f"URL: {it.get('url', '')}\n"
            f"요약: {it.get('content', '')}"
        )
    return "\n\n".join(lines)
