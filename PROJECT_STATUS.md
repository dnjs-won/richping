# Richping 구현 상태 · 2026-09-17 (M2-1A-R2-2-R1)

## 완료 및 보강 범위

- 독립 repository, Python 가상환경, SQLite schema, configuration.
- 최상위 명세와 14개 설계 항목 및 기존 프로젝트 재사용 분석.
- 실제 일봉 수집, 고정 ranking, 과거 확정 표본 calibration, immutable snapshot.
- 1/3/5/10/20 session 자동 관측, missing/action 격리, NO TRADE.
- M2-1A: 일반 현금배당 결과 계산 (`v2_ordinary_cash_dividend`). 진입일 배당락 제외, 보유 중 배당 누적, 세전 비재투자 총수익, 비용 1회 차감, 가격/배당 분리 진단, 기대값/평가 일관성, 구버전 호환 격리.
- M2-1A-R1: 구버전 호환성과 테스트 실행 결함 수정 (보고서 및 observe 버전 dispatch 명시화, Scenario 10 통합 테스트 결정론적 보강, conftest 임시 경로 격리).
- M2-1A-R2-1: `action_capture` 증분 provenance 보강 (수집 계층 보강 구현 완료, 검수 승인).
- M2-1A-R2-2: `v3_cash_action_guard` 계산 엔진 및 feature window 기업행동 차단 (구현 완료).
- M2-1A-R2-2-R1: `synthetic` shadow 시점 검사 수정 및 테스트 보강 (구현 완료, GPT-5.6 Sol High 검수 대기)
  - `richping/data.py`의 `inspect_action_capture`:
    - `adapter_version == "synthetic"` 예외 우회 경로 제거.
    - synthetic 데이터도 실제 수집 데이터와 동일한 point-in-time 시점 규칙 통과 필수 (`captured_at` 및 event `known_at` <= `as_of`).
    - `captured_at` 누락(None 또는 빈 문자열) 또는 미래 시점인 경우 `is_pending=True`, `reason="data_not_yet_known"` 반환.
    - `captured_at <= as_of`라도 보유창 내 event 중 `known_at > as_of`인 경우 `PENDING / data_not_yet_known` 반환.
    - research 모드는 시점 제약 없이 온전한 동작 유지.
  - `richping/data.py`의 `synthetic_dataset`:
    - 기본 `captured_at`을 마지막 거래일 cutoff(`days[-1]`)로 유지하여 capture 시점 계약 일관성 보존 (`captured_at` 파라미터 오버라이드 지원).
  - `tests/test_integrity.py`:
    - `test_future_membership_not_visible_in_shadow`에서 공유 fixture/전역 capture 변조 없이 평가일 기준 독립 fixture(`n=301`)로 구성하고, 마지막 일봉·capture 구간 끝·`captured_at`의 평가 시점 일관성을 명시적으로 assert.
  - `tests/test_action_capture.py`:
    - Scenario 11 결정론 테스트의 `captured_at` 기대값을 마지막 거래일(`ds1.sessions[-1]`)로 유지.
  - `tests/test_dividends.py`:
    - Section 4 요구 7개 필수 테스트 케이스 추가 (실제 `adapter_version="synthetic"` fixture 기반, Case 1~Case 7, 총 40개 테스트 통과).
- Rolling train/validation/OOS, 통계·위험 gate 기본 함수.
- CLI 보고서, CSV import, 실패/재시도, PowerShell 일일 실행 스크립트.

## 실제 검증 결과

- Python 3.13.7, 테스트 125 passed / 0 failed / 0 skipped (추가 옵션 없는 기본 `.\.venv\Scripts\python -m pytest` 통과).
  - `tests/test_action_capture.py`: 37 passed
  - `tests/test_cli.py`: 2 passed
  - `tests/test_dividends.py`: 40 passed (기존 18개 + R2-2 15개 + R2-2-R1 7개)
  - `tests/test_evaluation.py`: 16 passed
  - `tests/test_ingestion.py`: 4 passed
  - `tests/test_integrity.py`: 23 passed
  - `tests/test_validation.py`: 3 passed
- 합성 70-session 재생: 추천 72건, 완료 horizon 결과 360개. 추천 있는 날 49일, NO TRADE 21일.
- 합성 기본 504/63/63 walk-forward: 4 folds, 완료 OOS 추천 label 313개.
- 실제 Yahoo 수집: 후보 8종목 + SPY/QQQ, 일봉 10,020개, 마지막 session 2026-09-14.
- 실제 shadow scan: 시장 조건 미충족으로 NO TRADE.
- 실제 기본 walk-forward: 5 folds, 완료 OOS 추천 54건 / 43개 날짜. 비용 후 양의 기대값을 입증하지 못함. 상세 기간·비용·분모·국면별 결과는 var/validation.json에 보존.
- 검증 데이터는 config.toml의 현재 고정 종목군, Yahoo 수정 가능한 과거 가격, 왕복 20bps. 연구용 OOS이며 survivorship-free 또는 final holdout 증거가 아니다. 전략 portfolio NAV가 아닌 horizon 추천 수익이다.
- 합성 수익률은 동작 검증이며 투자 성과 증거가 아니다.
- 원본 프로젝트 파일을 수정하지 않았고 직접 복사한 원본 코드는 0개다.
- PowerShell 일일 스크립트 구문 검사를 통과했다. 실제 예약 실행은 검증하지 않았다.

## 미해결 차단 결함 및 R2 후속 단계

M2-1A-R2는 Astra 감독 설계에 따라 3단계로 나누어 진행 중이다:
- R2-1: 수집 계층 Capital Gains 보존 및 provenance 보강 (완료 및 승인)
- R2-2: `v3_cash_action_guard` 계산 엔진 및 feature window 기업행동 차단 (R2-2-R1 수정 완료, GPT-5.6 Sol High 검수 대기)
- R2-3: `cash_action_review_v1` 평가 정책 격리 및 보고서/파이프라인 분리 (미구현)

**M2-1A 전체 승인은 R2-3 및 최종 Astra 감사 완료 전까지 보류 상태**다.

다음 검수 모델: **GPT-5.6 Sol High** (R2-2-R1 synthetic shadow 시점 검사 수정 및 7개 테스트 검수).

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
