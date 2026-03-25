"""컨텍스트 토큰 절감 유틸리티"""


def trim_context(text: str, max_chars: int = 3000) -> str:
    """텍스트를 max_chars 이하로 트리밍 (끝에 잘린 표시 추가)"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...(이하 생략)"


def trim_list_context(parts: list[str], max_total_chars: int = 4000) -> str:
    """
    여러 컨텍스트 파트를 병합하되 총 max_total_chars 이하로 트리밍.
    앞쪽 파트에 더 많은 토큰 배분.
    """
    if not parts:
        return ""
    per_part = max_total_chars // len(parts)
    trimmed = [trim_context(p, per_part) for p in parts]
    return "\n\n---\n\n".join(trimmed)


def trim_candidates_str(candidates: list, max_per: int = 120) -> str:
    """후보 목록을 간결하게 직렬화"""
    lines = []
    for c in candidates:
        desc = getattr(c, "description", "")[:max_per]
        lines.append(f"- {c.name} ({getattr(c, 'domain', '')}): {desc}")
    return "\n".join(lines)
