"""
보고서 검증: Hallucination Check, Relevance Check, 근거 정합성 검사.

- hallucination_check: 출처 없는 숫자/주장 탐지
- relevance_check: 투자 보고서 목적 부합성 확인
"""
from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage


@dataclass
class VerificationResult:
    passed: bool
    reason: str
    details: str = ""


def hallucination_check(
    report: str,
    source_data: str,
    llm: ChatOpenAI,
) -> VerificationResult:
    """
    보고서 내 출처 없는 주장/숫자 탐지.
    - unsupported claim 금지
    - 출처 없는 숫자 금지
    """
    prompt = f"""당신은 투자 보고서 품질 검증자입니다.
보고서의 각 주장과 숫자가 아래 [구조화 데이터]에 근거가 있는지 검증하세요.

[구조화 데이터 (유일한 출처)]
{source_data[:12000]}

[생성된 보고서]
{report[:8000]}

검증 규칙:
1. 보고서에 나온 모든 숫자(금액, %, 시장규모 등)는 반드시 구조화 데이터에 존재해야 함
2. 추론·해석은 허용하되, 사실 주장은 데이터에 기반해야 함
3. 데이터에 없는 구체적 숫자를 만들면 안 됨

다음 JSON 형식으로만 응답:
{{"passed": true/false, "reason": "이유", "unsupported_claims": ["출처 없는 주장1", "출처 없는 주장2"]}}
passed=true는 모든 주장이 출처 있음. passed=false는 1개라도 출처 없음."""

    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        text = resp.content.strip()
        # JSON 추출
        import json
        import re
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            data = json.loads(m.group())
            passed = data.get("passed", False)
            reason = data.get("reason", "")
            claims = data.get("unsupported_claims", [])
            details = "; ".join(claims) if claims else reason
            return VerificationResult(passed=passed, reason=reason, details=details)
    except Exception as e:
        return VerificationResult(passed=False, reason=f"검증 예외: {e}", details=str(e))
    return VerificationResult(passed=False, reason="응답 파싱 실패", details="")


def relevance_check(
    report: str,
    question: str,
    target_domain: str,
    llm: ChatOpenAI,
) -> VerificationResult:
    """
    보고서가 투자 심사 목적에 부합하는지 검증.
    - human-readable
    - 투자 보고서 톤
    - 문장 자연성 및 근거 정합성
    """
    prompt = f"""당신은 투자 보고서 품질 검증자입니다.
보고서가 다음 질의와 도메인에 맞는 투자 심사 보고서인지 검증하세요.

질의: {question}
도메인: {target_domain}

[보고서]
{report[:6000]}

검증 항목:
1. 투자 검토 목적에 부합하는가 (회사 분석, 시장성, 투자 포인트, 리스크)?
2. 투자 보고서 톤으로 작성되었는가 (전문적, 간결)?
3. Executive Summary부터 종합 의견까지 논리적 흐름이 있는가?

다음 JSON 형식으로만 응답:
{{"passed": true/false, "reason": "이유"}}
passed=true는 위 3항목 모두 충족."""

    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        text = resp.content.strip()
        import json
        import re
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            data = json.loads(m.group())
            passed = data.get("passed", False)
            reason = data.get("reason", "")
            return VerificationResult(passed=passed, reason=reason)
    except Exception as e:
        return VerificationResult(passed=False, reason=f"검증 예외: {e}")
    return VerificationResult(passed=False, reason="응답 파싱 실패")
