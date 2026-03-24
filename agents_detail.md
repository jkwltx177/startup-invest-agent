# 에이전트별 루프를 한 번에 정리하면

- Supervisor / Investment Decision Agent
    
    Supervisor는 **Query Reception → Strategic Decision-Making → Delegation → Aggregation and Synthesis**를 수행하는 상위 통제자입니다. 
    
    ## 핵심 역할
    
    - 사용자 질의를 수신하고 전체 분석 목표를 정의
    - 질의 복잡도와 불확실성을 평가
    - 어떤 하위 에이전트를 어떤 순서와 깊이로 호출할지 결정
    - 각 에이전트의 결과 품질을 Judge 기준으로 평가
    - 최종 투자 여부를 판단하고 보고서 생성을 지시
    
    ## 내부 과정
    
    - **Query Reception**
        - 사용자 질문 수신
        - `question`, `target_domain` 설정
        - 반도체 스타트업 평가라는 목표를 명시적으로 구조화
    - **Planning**
        - 질문을 Task로 분해
        - 예: 후보 찾기 → 기술 검증 → 시장성 검증 → 경쟁 비교 → 종합 판단
    - **Routing**
        - 어떤 에이전트를 먼저 실행할지 결정
        - 후보가 없으면 Search Agent 우선
        - 후보는 있으나 기술이 약하면 Tech Agent 우선
        - 시장 정보가 최신이어야 하면 Market Agent에 웹 기반 검색 비중 확대
    - **Delegation**
        - 각 에이전트에 세부 질의와 기대 출력 포맷 전달
    - **Aggregation**
        - 결과를 모아서 정규화
        - 누락/충돌/불확실성 확인
    - **Decision**
        - 점수화, threshold 판단, 리스크 반영
        - 투자 / 보류 / 추가검토 결정
    - **Report Trigger**
        - Report Agent에게 최종 보고서 생성 요청
    
    ## 루프 유형
    
    Supervisor는 **Adaptive Loop + Recursive Loop + Judge Loop**를 갖는 것이 가장 적절합니다.
    
    ### 왜 Adaptive Loop인가
    
    자료에서 Adaptive Loop는 **Judge가 루프 진입 여부 자체를 판단**하는 구조입니다. 지금 설계도도 질의 난이도에 따라 일부 에이전트만 호출하거나, 추가 검색이 필요할 때만 재진입해야 하므로 가장 잘 맞습니다.
    
    ### 왜 Recursive Loop인가
    
    하위 에이전트 결과가 부족하면 Supervisor가
    
    - query transformation,
    - 재계획,
    - 다른 agent 재호출
    을 하게 되므로 고정 반복이 아니라 **조건 기반 재귀형 보완 루프**가 더 적합합니다.
    
    ## Supervisor의 구체적 루프
    
    - 1차 계획 수립
    - Search/Tech/Market/Competitor 결과 수집
    - Judge 수행:
        - 후보 수 충분한가
        - 기술/시장/경쟁 정보가 서로 연결되는가
        - 핵심 근거가 부족한가
        - 점수 산정이 가능한 수준인가
    - 부족하면 다음 중 하나 선택
        - `Re-plan`
        - `Re-route`
        - `Re-retrieve`
        - `Re-generate`
    - 충분하면 Investment Decision 실행
    - 이후 Report Agent로 전달
    
    ## Supervisor용 Judge 기준
    
    - **Coverage**: 스타트업 후보, 기술, 시장, 경쟁 구도가 모두 채워졌는가
    - **Consistency**: 각 Agent 결과가 서로 충돌하지 않는가
    - **Relevance**: 반도체 산업과 직접 관련되는가
    - **Support/Faithfulness**: 근거 문서가 실제 판단을 뒷받침하는가
    - **Decision Readiness**: 투자 판단을 내려도 될 정도로 정보가 구조화되었는가
    
    ## 종료 조건
    
    - `iteration_count >= max_iteration`
    - 또는 `is_done == True`
    - 또는 Judge score가 임계값 이상
    
- Startup Discovery Agent
    
    이 에이전트는 반도체 관련 스타트업 후보를 발굴하는 시작점입니다.
    
    자료의 관점으로 보면
    
    **Pre-Retrieval Routing + Query Expansion + Branching + Corrective Retrieval**
    
    성격이 가장 강합니다.
    
    ## 핵심 역할
    
    - 반도체 산업 내 스타트업 후보 탐색
    - 질의를 세분화해 후보군 확보
    - 반도체 관련성 필터링
    - Top-K 후보 반환
    
    ## 내부 과정
    
    - 사용자 질의에서 핵심 축 추출
        - 예: AI chip, EDA, design automation, power semiconductor, fab AI, inspection AI
    - **Query Expansion**
        - 원 질문에 없는 연관 키워드 확장
        - 반도체 value chain 기준으로 하위 주제 생성
    - **Pre-Retrieval Branching**
        - Sub-query를 여러 개 생성
        - 각 sub-query별로 병렬 검색
    - **Hybrid Retrieval**
        - Vector 검색 + keyword 검색 조합
    - **Rerank**
        - 반도체 도메인 적합도, 스타트업성, 정보 충분성 기준 재정렬
    - **Candidate Normalization**
        - 기업명 표준화
        - 중복 제거
        - 법인명/브랜드명 통합
    - **Top-K 선정**
        - 후보 수와 질을 함께 고려해 반환
    
    ## 루프 유형
    
    이 에이전트는 **Pre-Retrieval Branching + Corrective Recursive Loop**가 적절합니다.
    
    ### 1차 루프
    
    - query expansion
    - sub-query 병렬 검색
    - 결과 fusion
    
    ### Judge
    
    - 후보 수가 너무 적은가
    - 타켓 도메인(반도체) 외 산업이 섞였는가
    - 같은 회사가 중복되는가
    - 스타트업인가
        - 빠른 확장과 시장 선점
        - 상당히 빠름 (10배 성장 등)
        - 혁신적이고 독창적인 기술, 서비스 중심
        - 매우 높음 (시장, 기술, 고객 관점)
        - M&A, IPO 등
        - 투자 중심 (VC, 엔젤 등)
    - 트렌드 점수 낮으면 내리기
    
    ### 실패 시 웹서치 재시도
    
    - Query Rewrite
    - Query Expansion 방향 수정
    - 산업 키워드 강화
    - 지역/투자단계 필터 조정
    
    ## 이 에이전트의 판단 루프 문장형 설명
    
    스타트업 탐색 에이전트는 먼저 질의를 반도체 value chain 기준의 하위 질의로 분해하고, 각 질의에 대해 병렬 검색을 수행한 뒤 결과를 병합합니다. 이후 Judge가 후보 수의 적절성, 반도체 관련성, 중복 여부를 평가하며, 기준 미달 시 query rewrite와 domain filter 조정을 통해 최대 3회까지 재탐색하는 **branching 기반 corrective recursive loop**로 동작합니다.
    
- Technology Summary Agent
    
    이 에이전트는 후보 스타트업의 기술력과 차별성을 요약하는 역할입니다.
    
    자료의 관점으로는
    
    **Memory-first Retrieval + Post-Retrieval Re-ranking + Self-Evaluation Loop**
    
    가 가장 적합합니다. 특히 사용자가 적어준
    
    ```
    tech_summaries
    ```
    
    캐시 구조와도 잘 맞습니다.
    
    ## 핵심 역할
    
    - 기술 문서, 논문, 특허, 홈페이지 기반 기술 요약
    - 기술 성숙도, 차별성, 적용 분야 정리
    - 강점/약점과 리스크 도출
    
    ## 내부 과정
    
    - **Memory / DB 탐색**
        - 기존 `tech_summaries` 확인
        - Vector DB 검색
        - 이미 충분하면 캐시 사용
    - **부족 시 Web / External Retrieval**
        - 홈페이지
        - 기술 문서
        - 특허
        - 논문 / R&D 자료
    - **Post-Retrieval**
        - 문서 rerank
        - 핵심 chunk selection
        - compression
        - context reorder
    - **Technical Parsing**
        - 기술 스택
        - 알고리즘/아키텍처
        - 적용 문제
        - 기술 차별성
        - TRL, 양산 가능성
    - **Structured Summary 생성**
        - `TechSummary` 타입으로 정제
    
    ## 루프 유형
    
    이 에이전트는 **Corrective Recursive Loop + Feedback Loop**가 적절합니다.
    
    ### Judge 기준
    
    - 핵심 기술 메커니즘이 설명되었는가
    - 특허/논문/제품 문서 간 충돌이 없는가
    - 기술적 강점과 한계가 모두 드러났는가
    - TRL 판단 근거가 있는가
    
    ### 실패 시 선택지
    
    - `Re-retrieve`: 다른 출처 추가 검색
    - `Re-rank`: 문서 우선순위 조정
    - `Re-generate`: 요약만 다시 생성
    - `Re-plan`: 기술 축을 다시 정의
    
    ## 이 에이전트의 판단 루프 문장형 설명
    
    기술 요약 에이전트는 먼저 메모리와 Vector DB를 조회하여 기존 기술 요약이 충분한지 확인하고, 부족할 경우 웹과 문서 기반 검색으로 특허, 논문, 기술 설명 자료를 수집합니다. 이후 reranking과 compression을 거쳐 핵심 기술 구조를 요약하며, Judge가 기술 누락, 출처 간 충돌, 성숙도 판단 부족 여부를 평가하고, 필요 시 재검색 또는 재요약을 수행하는 **corrective feedback loop**로 동작합니다.
    
- Market Evaluation Agent
    
    이 에이전트는 시장 규모와 성장 가능성을 평가합니다.
    
    자료의 개념으로 보면
    
    **Routing + Hybrid Retrieval + Multi-hop Retrieval + Recursive Loop**
    
    가 적합합니다. 특히 시장성은 단일 문서로 끝나지 않고, 산업 리포트와 최신 뉴스, 수요 산업 정보를 함께 연결해야 하므로 multi-hop 성격이 강합니다.
    
    ## 핵심 역할
    
    - TAM/SAM/SOM 산정
    - 성장률, 수요 산업, 세그먼트 구조 파악
    - 기술-시장 적합성 평가
    
    ## 내부 과정
    
    - 시장 주제 정의
        - 예: AI 반도체, 전력반도체, 검사장비 AI, EDA 자동화
    - **Routing**
        - 정적 리포트 중심인지
        - 최신 뉴스/실시간 정보가 필요한지 판단
    - **Hybrid / Multi-hop Retrieval**
        - 산업 리포트 검색
        - 최신 뉴스 검색
        - 시장 수요와 기술 적합성 연결
    - **Normalization**
        - 시장 범위 정의 일관화
        - 연도 기준 맞춤
        - 통화/단위 정리
    - **Evaluation**
        - TAM/SAM/SOM
        - CAGR
        - 시장 진입 시점
        - 고객군 성숙도
        - 공급망 적합성
    
    ## 루프 유형
    
    이 에이전트는 **Recursive Loop + Multi-hop Loop**가 적절합니다.
    
    ### Judge 기준
    
    - 시장 범위가 너무 넓거나 좁지 않은가
    - 수치 출처가 서로 충돌하지 않는가
    - 기술과 실제 수요가 연결되는가
    - 최신성이 필요한 항목이 반영되었는가
    
    ### 실패 시 재시도
    
    - 시장 정의 재설정
    - narrower / broader query rewrite
    - 지역/응용산업 기준 재탐색
    - 최신 뉴스 경로 추가
    
    ## 이 에이전트의 판단 루프 문장형 설명
    
    시장성 평가 에이전트는 시장 범위를 정의한 뒤 산업 리포트, 수요 산업 자료, 최신 뉴스 등을 연결하는 multi-hop 검색을 수행합니다. 이후 TAM/SAM/SOM과 CAGR을 정규화해 산출하고, Judge가 시장 범위의 과대·과소 설정, 수치 충돌, 기술-수요 부정합 여부를 검사합니다. 기준 미달 시 시장 정의를 조정하고 재검색하는 **recursive multi-hop loop**로 운영하는 것이 적절합니다.
    
- Competitor Comparison Agent
    
    이 에이전트는 대상 스타트업의 상대적 위치를 파악합니다.
    
    자료 개념상
    
    **Post-Retrieval Branching + Fusion + Judge Loop**
    
    가 가장 잘 맞습니다. 경쟁사는 한 곳만 보면 안 되고, 여러 경쟁 후보를 개별 분석한 뒤 합쳐야 하므로 branching이 중요합니다.
    
    ## 핵심 역할
    
    - 경쟁사 식별
    - 포지셔닝 비교
    - 차별화 요소 및 리스크 도출
    
    ## 내부 과정
    
    - **Memory / DB 탐색**
        - 기존 `competitor_profiles` 확인
    - **경쟁사 후보 식별**
        - 동일 시장
        - 유사 기술
        - 동일 고객군
    - **Post-Retrieval Branching**
        - 경쟁사 A, B, C 각각 독립 분석
    - **비교 축 정의**
        - 기술력
        - 시장 점유율
        - 고객사
        - 파트너십
        - 투자 유치
        - 제조/양산 역량
    - **Fusion**
        - 각 경쟁사 분석을 한 표준 포맷으로 합치기
    - **Differentiation Summary**
        - 대상 스타트업의 장점/약점 도출
    
    ## 루프 유형
    
    이 에이전트는 **Branching + Fusion + Judge Loop**가 합니다.
    
    ### Judge 기준
    
    - 경쟁사 정의가 적절한가
    - 비교 축이 일관적인가
    - 대상 기업의 상대적 우위/열위가 드러나는가
    - 자료가 한 경쟁사에 치우치지 않았는가
    
    ### 실패 시 재시도
    
    - 경쟁사 재선정
    - 비교 축 수정
    - 특정 경쟁사 제거/추가
    - 최신 기업 정보 재검색
    
    ## 이 에이전트의 판단 루프 문장형 설명
    
    경쟁사 평가 에이전트는 대상 스타트업과 유사한 기술 또는 고객군을 가진 경쟁사를 선별한 뒤, 각 경쟁사에 대해 독립적으로 검색과 분석을 수행하는 branching 구조를 사용합니다. 이후 기술, 시장, 자금, 파트너십, 양산 역량을 기준으로 결과를 fusion하고, Judge가 경쟁사 선정 타당성과 비교 축의 일관성을 점검한 뒤 필요 시 후보를 다시 조정하는 **branching-fusion judge loop**로 구성하는 것이 가장 자연스럽습니다.
    
- Report Generation Agent
    
    이 에이전트는 최종 산출물 생성기입니다.
    
    단, 그냥 문장 생성기가 아니라
    
    **검증된 근거만 받아 쓰는 constrained generator**
    
    로 두는 것이 좋습니다. 자료에서 말한 Generation 이후 Verification, 그리고 Hallucination / Answer Relevance 검사를 여기에도 붙여야 합니다.
    
    ## 핵심 역할
    
    - 결과 통합
    - 투자 논리 구조화
    - 보고서 생성
    
    ## 내부 과정
    
    - Supervisor가 승인한 구조화 데이터만 입력으로 받음
    - 섹션 구성
        - 스타트업 개요
        - 기술 요약
        - 시장성
        - 경쟁 구도
        - 투자 판단
        - 리스크
    - 자연어 생성
    - 근거-문장 정렬
    - 최종 Markdown/보고서 포맷 변환
    
    ## 루프 유형
    
    이 에이전트는 **Generate → Verify → Re-generate**의 짧은 **Feedback Loop**가 적절합니다.
    
    ### Judge 기준
    
    - 보고서가 각 Agent 결과를 모두 반영하는가
    - 근거 없는 주장이나 과장 표현이 있는가
    - 투자 결론이 앞선 분석과 일치하는가
    - 문장이 자연스럽고 간결한가
    
    ### 실패 시 재시도
    
    - `Re-generate`만 수행
    - 필요 시 Supervisor에 누락 섹션 반환
    
    **심화 설계**
    
    섹션을 쪼개서 순서대로 생성하고, 각 섹션마다 Reflection을 돌리는 구조예요.
    
    ```
    ① 섹션 플래닝
       LLM이 보고서 목차 먼저 결정
       (데이터 상태 보고 어떤 섹션이 필요한지 판단)
            ↓
    ② 섹션별 순차 생성
       Executive Summary
            ↓
       스타트업 기술 분석
            ↓
       시장성 분석
            ↓
       경쟁사 비교
            ↓
       투자 의견 · 리스크
            ↓
    ③ 섹션별 Reflection
       - 이전 섹션과 논리적으로 이어지는가
       - 데이터 근거가 있는가
       - 할루시네이션이 있는가
       미달 → 해당 섹션만 재생성
            ↓
    ④ 전체 일관성 검토
       섹션 간 수치·주장이 충돌하지 않는가
            ↓
    ⑤ final_report 저장
    ```
    
    ## 이 에이전트의 판단 루프 문장형 설명
    
    보고서 생성 에이전트는 앞선 분석 결과를 논리적 구조로 정리해 자연어 보고서를 생성하며, 생성 직후 Judge가 근거 일치성, 문장 자연성, 결론 정합성을 검토합니다. 문제가 발견되면 전체 파이프라인을 다시 돌리기보다는 보고서 생성만 다시 수행하는 **short feedback loop**로 두는 것이 효율적입니다.