"""휴먼 인 더 루프 - 주요 단계에서 사용자 확인."""
import os


def human_approve(step_name: str, message: str, default_yes: bool = True) -> bool:
    """
    사용자 확인 대기. HUMAN_IN_THE_LOOP=true일 때만 활성화.
    Returns: True=계속, False=중단/재시도
    """
    if not os.environ.get("HUMAN_IN_THE_LOOP", "").lower() in ("true", "1", "yes"):
        return True
    prompt = f"\n>>> [{step_name}] {message}\n   Enter=계속, n=중단: "
    r = input(prompt).strip().lower()
    if r in ("n", "no"):
        return False
    return True


def human_input(step_name: str, message: str, default: str = "") -> str:
    """사용자 입력 수집. HUMAN_IN_THE_LOOP=true일 때만 활성화."""
    if not os.environ.get("HUMAN_IN_THE_LOOP", "").lower() in ("true", "1", "yes"):
        return default
    r = input(f"\n>>> [{step_name}] {message}\n   입력 (Enter=기본값 유지): ").strip()
    return r if r else default
