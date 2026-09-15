# Richping — 최상위 프로젝트 명세

이 문서는 2026-09-15 사용자가 제공한 요구사항을 구현의 최상위 기준으로 보존한다. 기존 프로젝트의 요구사항, roadmap, AGENTS는 상속하지 않는다.

## Goal / 원칙

사용자의 지속적인 투자 분석이나 일지 입력 없이 시장에서 상대적으로 유리한 종목을 추천하고, 당시 정보를 동결하고, 미래 성과를 자동 관찰하며, 검증된 증거로 추천 품질을 개선한다.

Automation First · Low Maintenance · Performance Driven · Statistically Validated · Simple for the User.

판단 순서: Correctness → Data Integrity → Statistical Validity → Simplicity → Maintainability → Performance → Extensibility.

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

## Non-Scope

MVP에서는 자동 주문, 포트폴리오 최적화, 실시간 초단타, 복잡한 web UI, 투자 일지, decision memory, ontology, knowledge graph, agent hierarchy, 수동 hypothesis 운영, 뉴스 NLP, 옵션 체인, 대규모 alternative data를 만들지 않는다.

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

0. 참고 프로젝트 검토 → 1. 작은 E2E → 2. 신뢰할 수 있는 검증 → 3. adaptive ranking → 4. pattern discovery → 5. 효용이 검증된 advanced data.

Pattern discovery는 강한 상승/하락, 상대 거래량, 갭, 돌파 이전 특징에서 후보 interaction을 찾되 기존 전략 검증 엔진과 동일한 OOS gate를 거친다. 선행 조건은 아니다.

## Reference policy

`C:\konviction`, `C:\adaptive-alpha`는 read-only. 신규 코드는 `C:\richping`에만 작성한다. 재사용은 REUSE / ADAPT / REWRITE / DROP 판정 후에만 가능하다. 기존 코드를 살리기 위해 구조를 복잡하게 만들지 않는다.
