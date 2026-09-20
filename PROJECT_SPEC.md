# Richping — 최상위 프로젝트 명세

이 문서는 2026-09-15 사용자가 제공한 요구사항과 2026-09-20 목표 재정립을 구현의 최상위 기준으로 보존한다. 기존 프로젝트의 요구사항, roadmap, AGENTS는 상속하지 않는다.

## Goal / 원칙

사용자의 지속적인 투자 분석이나 일지 입력 없이 시장에서 상대적으로 유리한 종목을 추천하고, 당시 정보를 동결하고, 미래 성과를 자동 관찰하며, 검증된 증거로 추천 품질을 개선한다.

Automation First · Low Maintenance · Performance Driven · Statistically Validated · Simple for the User.

개발 우선순위: 실질적 투자 효용 → 필요한 검증 신뢰도 → 실제 위험 통제 → 자동화 → 확장성. Correctness·Data Integrity·Statistical Validity는 이를 위해 지켜야 할 필수 조건이며, 효용을 이유로 완화하지 않는다. Simplicity·Maintainability를 유지한다. 이는 기존의 무결성 우선 원칙을 폐기하는 것이 아니라, 무결성 개발을 실제 투자 효용에 연결하도록 순서를 명확히 한 변경이다.

새 작업은 추천 성능, 검증 신뢰도, 실제 손실 위험, 사용자 노동, 운영 안정성 중 하나에 직접 기여해야 한다. 기능 수나 코드량은 성공 기준이 아니다.

## Scope

- 독립 repository / architecture / DB / configuration / runtime / roadmap.
- Market data → validation → universe → features → regime → signals → ranking → recommendation → immutable snapshot → outcomes → evaluation.
- 결과가 확정된 과거 데이터만 이용한 기대수익·손실·손익비·신뢰도 추정. 근거 부족 시 NO TRADE.
- 추천 1/3/5/10/20 거래일 이후 수익률, MFE/MAE, target/stop 관찰. 사용자 결과 입력 불필요.
- 비용 후 expectancy 중심 평가. 승률, 평균 이익/손실, payoff, PF, tail, 빈도 및 국면별 성과.
- 시간 순서 train/validation/OOS, walk-forward, label purging, embargo, bootstrap 및 다중 탐색 통제.
- 후속 단계에서 제한된 challenger 생성 → OOS·통계·위험 gate → champion 유지/승격.
- NORMAL / REDUCED_EXPOSURE / PAUSED. 부족한 증거로 위험을 높이지 않는다.
- 멱등성, 실패 기록, 재시도, 구조화 로그, 입력 검증, 모델/설정 버전, 결정론적 재생.
- Production Recommendation / Research & Discovery / Evaluation & Promotion을 논리적으로 분리한다. 고정 전략의 forward 관찰과 격리된 연구는 병행할 수 있으나 미검증 연구 결과가 운영 추천에 직접 유입되어서는 안 된다.
- 고정 8종목은 시작 범위다. 단계적 universe 확장, 신호 없는 종목·비상승 대조군·실패 사례까지 포함한 사전 관측 특징 연구를 지원한다. 급등·눌림목·재진입 경험은 가설의 출발점이지 재현 가능한 알파의 증거가 아니다.
- 실제 활용 전 최소 paper 포트폴리오 회계로 중첩 포지션·자본 배분·현금·비용·집행 가능성을 평가한다. 추천 수익 합계/평균과 cohort drawdown을 계좌 수익/MDD로 표시하지 않는다. SPY 우위는 동일 기간·자본·현금 조건과 비교 완전성을 확인한다.
- 최종 목표는 사용자의 위험 대비 비용 후 순수익 개선이다. 수익·개선·자동 승격을 보장하지 않으며 검증 실패 시 기존 전략 유지 또는 NO TRADE가 정상 결과다.

## Non-Scope

MVP에서는 자동 주문, 포트폴리오 최적화, 실시간 초단타, 복잡한 web UI, 투자 일지, decision memory, ontology, knowledge graph, agent hierarchy, 수동 hypothesis 운영, 뉴스 NLP, 옵션 체인, 대규모 alternative data를 만들지 않는다.

최소 자본/포지션 회계는 포트폴리오 최적화와 구분하여 후속 R1 범위에 포함한다. 자동 주문은 별도의 명시적 사용자 승인 없이는 향후 단계에도 포함하지 않는다. 금리·VIX·섹터·경제지표 등은 기존 모델의 한계와 추가 효용·비용을 측정한 뒤 도입하며 발표/수정 시각을 포함한 PIT 계약이 필요하다. 분산 시스템은 실제 병목 확인 전에 도입하지 않는다.

## 성공 기준

1. 정해진 실행 시점에 입력 노동 없이 보고서 생성.
2. 추천 당시 데이터·모델·설정·시점 동결.
3. 미래 결과 자동 수집.
4. 시간 순서 OOS 성과 측정.
5. NO TRADE 가능.
6. 국면별 차이 확인.
7. champion/challenger 객관적 비교.
8. 성과 악화 시 추천 축소/중단.
9. 매일 일지 작성이나 모델 관리 불필요.

전체 성공 기준과 첫 milestone 완료는 구분한다. 첫 milestone은 작은 종목군에서 추천부터 결과 측정까지 작동하는 것이다. Alpha, 통계적으로 유효한 자동 승격, 시장 전체 커버리지를 구현 완료와 혼동하지 않는다.

## 확장 순서

2026-09-15 원래 계획(역사 보존): 0. 참고 프로젝트 검토 → 1. 작은 E2E → 2. 신뢰할 수 있는 검증 → 3. adaptive ranking → 4. pattern discovery → 5. 효용이 검증된 advanced data.

2026-09-20 이후 계획은 [ROADMAP.md](ROADMAP.md)의 R0~R6을 따른다. 일일 관찰 제품과 fresh forward 수집을 먼저 시작하고 최소 paper 평가·격리된 제한 연구를 병행한다. universe/패턴 탐색, 조건부 시장 환경 데이터, 통제된 승격·강등으로 확장한다. 전체 자동 개선 완성 전에 일일 보고와 모의매매 효용을 제공한다.

Pattern discovery는 강한 상승/하락, 상대 거래량, 갭, 돌파 이전 특징에서 가설을 찾되 발견 데이터와 성능 입증 데이터를 분리한다. 같은 OOS 반복 승격 금지, 실패 포함 trial 기록, purge/embargo, 상관·다중시험·비용 stress·fresh forward 검증을 적용한다. 자동 가설 생성은 제한된 전략 계열/파라미터부터 시작하며 기존 검증 엔진을 재사용한다.

이번 변경은 요구사항·미래 순서만 바꾸며 기존 immutable 데이터, M1/M2-1A/M2-1B 완료 기록 및 현재 feature/outcome/evaluation 계약을 변경하지 않는다. 신규 계약은 버전과 호환성 영향을 명시한 후속 구현으로 추가한다.

## Reference policy

`C:\konviction`, `C:\adaptive-alpha`는 read-only. 신규 코드는 `C:\richping`에만 작성한다. 재사용은 REUSE / ADAPT / REWRITE / DROP 판정 후에만 가능하다. 기존 코드를 살리기 위해 구조를 복잡하게 만들지 않는다.
