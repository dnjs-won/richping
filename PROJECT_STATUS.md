# Richping 구현 상태 · 2026-09-17 (M2-1A-R2 Sol Remediation)

## 완료 및 보강 범위

- 독립 repository, Python 가상환경, SQLite schema, configuration.
- 최상위 명세와 14개 설계 항목 및 기존 프로젝트 재사용 분석.
- 실제 일봉 수집, 고정 ranking, 과거 확정 표본 calibration, immutable snapshot.
- 1/3/5/10/20 session 자동 관측, missing/action 격리, NO TRADE.
- M2-1A: 일반 현금배당 결과 계산 (`v2_ordinary_cash_dividend`). 진입일 배당락 제외, 보유 중 배당 누적, 세전 비재투자 총수익, 비용 1회 차감, 가격/배당 분리 진단, 기대값/평가 일관성, 구버전 호환 격리.
- M2-1A-R1: 구버전 호환성과 테스트 실행 결함 수정 (보고서 및 observe 버전 dispatch 명시화, Scenario 10 통합 테스트 결정론적 보강, conftest 임시 경로 격리).
- M2-1A-R2-1: `action_capture` 증분 provenance 보강 (수집 계층 보강 구현 완료, 검수 승인).
- M2-1A-R2-2: `v3_cash_action_guard` 계산 엔진 및 feature window 기업행동 차단 (구현 완료).
- M2-1A-R2-2-R1: `synthetic` shadow 시점 검사 수정 및 테스트 보강 (구현 완료).
- M2-1A-R2-3: `cash_action_review_v1` 평가 정책 격리 및 보고서/파이프라인 분리 (구현 완료).
- M2-1A-R2-Sol-Remediation: Sol High 통합검수 지적사항(2 HIGH + 2 MEDIUM) 국소 수정 완료:
  - HIGH 1: stored v3 COMPLETE의 bar known_at point-in-time 검증 및 구조적 정합성(observed_at 누락/비정상, horizon/end mismatch) 실패 폐쇄.
  - HIGH 2: matched SPY의 UNRESOLVED/PENDING 관측 분모 보존 및 signal-date 기준 pairing 진단 보존.
  - MEDIUM 3: Yahoo 일봉 수집 시 네트워크 완료 이전 known_at 기록 방지 (`symbol_captured_at = utcnow()` 및 max `overall_captured_at`).
  - MEDIUM 4: README 및 PROJECT_STATUS 현재 v2(역사적 계산 보존)/v3(fail-closed 가드) 계약 동기화.
- Rolling train/validation/OOS, 통계·위험 gate 기본 함수.
- CLI 보고서, CSV import, 실패/재시도, PowerShell 일일 실행 스크립트.

## 실제 검증 결과

- Python 3.13.7, 테스트 기본 `.\.venv\Scripts\python -m pytest` 통과 확인 중.

## R2 진행 및 검수 상태

M2-1A-R2 진행 상태:
- R2-1: 수집 계층 Capital Gains 보존 및 provenance 보강 (구현 및 검수 완료)
- R2-2 / R2-2-R1: `v3_cash_action_guard` 계산 엔진 및 feature window 기업행동 차단 (구현 완료)
- R2-3: `cash_action_review_v1` 평가 정책 격리 및 보고서/파이프라인 분리 (구현 완료)
- Sol High 통합검수에서 2 HIGH + 2 MEDIUM correctness 문제 발견 -> 이번 remediation 국소 수정 및 regression test 추가 완료.

**M2-1A 전체 승인은 독립 감사 완료 전까지 보류 상태**다 (PASS 판정을 미리 기록하지 않음).

## 남은 범위

- M2-1B: 배당 포함 특징 창(feature window) 처리 (현재는 61 session 창 내 배당 종목 제외 유지).
- 주식분할, 특별배당, 복합 기업행동 및 상폐 최종 회수금의 완전한 회계.
- 시점별 universe/vintage.
- 실제 challenger 생성/학습, paired OOS 비교와 자동 승격. 현재 gate는 미확보 증거에 REJECT.
- 이 PC에 예약 작업은 설치하지 않았다. README의 daily.ps1 명령을 작업 스케줄러에 한 번 등록해야 한다.
- 실제 계좌/포트폴리오 원장과 연환산 Sharpe/Sortino/Calmar는 없다. 현 단계 지표는 추천/cohort 진단이다.
- Performance PAUSED를 임의 재시작으로 해제하는 명령은 없다.
- 코드 hash + config hash가 model ID에 반영된다. 실행마다 snapshot/data/model ID를 저장한다.
- 실데이터 증분 수집은 mock 테스트로 검증했으며, 실제 네트워크에서 두 번째 증분 수집까지 확인한 것은 아니다.
