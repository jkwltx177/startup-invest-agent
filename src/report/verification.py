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
보고서의 각 주장과 숫자가 아래 [허용 출처] 중 하나에 근거하는지 검증하세요.

[허용 출처: 내부 구조화 데이터 + 웹 검색 보조 맥락(있을 경우)]
{source_data[:16000]}

[생성된 보고서]
{report[:8000]}

검증 규칙:
1. 구체적 숫자는 허용 출처에 있거나, 보고서에 '가정·추정·시나리오·검토용'으로 명시된 표·문장에 한정되는가.
2. 허용 출처에 없는 수치를 사실처럼 단정(※ 없이)했으면 실패.
3. Markdown 표 자체는 허용. SUMMARY·목차·REFERENCE 구조는 실패 조건 아님.

다음 JSON 형식으로만 응답:
{{"passed": true/false, "reason": "이유", "unsupported_claims": ["출처 없는 주장1", "출처 없는 주장2"]}}
passed=true는 위 기준 충족. passed=false는 명백한 날조/무출처 숫자."""

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
1. 문서 맨 위에 투자 보고서 **문서 대제목**(`# 투자 검토 보고서` 등 `#` 한 줄)이 있고, 그 다음에 `# SUMMARY` → `# 목차` → 본문 → `# REFERENCE` 순을 대체로 따르는가? (대제목만 있고 SUMMARY가 바로 없으면 실패)
2. 투자 검토 목적에 부합하는가 (회사·시장·리스크·의견)?
3. 전문적 한국어 투자 보고서 톤인가. JSON·원시 dict·코드 블록이 본문에 없는가? (Markdown 표는 있어도 됨)
4. `# REFERENCE`가 존재하는가?

다음 JSON 형식으로만 응답:
{{"passed": true/false, "reason": "이유"}}
passed=true는 위 항목이 대체로 충족."""

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
