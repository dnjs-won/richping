# Coverage Diagnostic v1 · M2-1B · 2026-09-17

2026-09-20 주석: 아래 수치·완료 판정·당시 다음 작업은 역사 기록으로 보존한다. 후속 로컬 research OOS/실패 분석을 확인한 현재 상태와 앞으로의 우선순위는 [ROADMAP](../ROADMAP.md) 및 [PROJECT_STATUS](../PROJECT_STATUS.md)를 따른다. “다음 작업 하나로 제한”은 당시 결정이며, 현재는 R0 forward 운영과 격리된 제한 연구의 병행을 허용한다. coverage 계약 자체는 변경하지 않는다.

## M2-1B 현재 계약과 재현

**Feature dividend normalization ≠ Outcome dividend accounting.** M2-1B는 feature-only 배당 정규화를 적용하며 outcome v3/evaluation 정책은 유지한다.

```powershell
.\.venv\Scripts\python -m richping --db var/m2-1b-fresh.db coverage --dataset-id 7d573d75465eb054f3cc89cde451d11fdbd4787f3353c67e84b292be653af2e8 --output var/coverage-m2-1b-replay.json
```

현재 검증 artifact는 `var/coverage-m2-1b-final.json`, 원본 비교는 `var/coverage-provenance-fixed.json`이다. 새 수집은 별도 `var/m2-1b-fresh.db`에 저장했다. 운영 DB를 교체하지 않았으므로 기본 DB의 기존 vintage에 M2-1B 단위 증거가 자동 생성되지는 않는다. 일반 `sync`는 증거 없는 이전 입력에서 새 전체 vintage로 전환한다.

JSON의 `schema=coverage_diagnostic_v1` 구조를 유지하고 `feature_contract=cash_gap_backward_v1`, `decision_funnel.raw_candidates`를 추가했다. `window_reasons`와 benchmark/candidate `by_reason.dividend`는 원본 배당 **관측**이다. `dividend_normalized`는 창 전체의 무결성/단위/수학 검증에 성공한 배당 창, `dividend_unsupported`는 배당이 관측됐으나 다른 action을 포함해 창이 실패한 경우다. 따라서 unsupported 수를 배당 자체만의 인과 효과로 해석하지 않는다. `signal_blocks.by_reason.dividend`는 이제 **배당 관측이 있는 차단 창의 합집합**이며, 성공한 정규화를 차단으로 세지 않는다. `both_benchmarks_dividend`는 기존처럼 관측 교집합이다. Engine와 benchmark/candidate 지원 여부가 어느 방향으로든 다르면 진단은 실패한다.

대상 기간은 이전과 같은 2022-12-13~2026-09-16, 942거래일/7,536 candidate ticker-session이다. 이전 dataset `0910ebac772cbd4fe42c22bd57a948f9b5cc918410b034d8e4d3213eee655771`와 새 수집의 **10,020개 OHLCV/dividend/split 값은 모두 동일**하다. 새 dataset id는 위 명령과 같으며 adapter `yfinance-1.7.0`, 116개 배당 단위 증거를 수집했다. before/after는 다른 immutable vintage지만 원본 가격/action 변화가 없는 비교다.

| 지표 | Before | After |
|---|---:|---:|
| benchmark supported / blocked | 16 / 926 | 941 / 1 |
| SPY feature computable | 28 | 942 |
| QQQ feature computable | 27 | 941 |
| SPY dividend observed / normalized / unsupported | 914 / 미지원 / 914 | 914 / 914 / 0 |
| QQQ dividend observed / normalized / unsupported | 915 / 미지원 / 915 | 915 / 914 / 1 |
| benchmark capture unknown 합집합 | 0 | 0 |
| candidate capture unknown | 0 | 0 |
| candidate dividend observed / normalized / unsupported | 4,809 / 미지원 / 4,809 | 4,809 / 4,688 / 121 |
| candidate split | 122 | 122 |
| candidate supported / excluded / benchmark 미평가 | 19 / 4,843 / 2,674 | 2,210 / 5,318 / 8 |
| raw candidate 날짜 / 개수 | 9 / 19 | 754 / 2,210 |
| calibration attempts | 12 | 1,959 |
| insufficient calibration 후보 / 날짜 | 12 / 6 | 171 / 59 |
| edge unsupported 후보 / 날짜 | 0 / 0 | 1,508 / 514 |
| recommendation 날짜 / 개수 | 0 / 0 | 142 / 265 |
| COMPLETE / PENDING / UNRESOLVED | 0 / 0 / 0 | 256 / 0 / 9 |
| evaluation eligible / excluded COMPLETE | 0 / 0 | 256 / 0 |
| matched SPY paired / attempted dates | 0 / 0 | 132 / 142 |

SPY/QQQ 어느 쪽이든 배당이 관측된 926일 중 925일이 복구됐다. 남은 1일(2022-12-13)은 QQQ 창 첫날인 수집 시작 2022-09-19의 배당을 검증할 직전 종가가 없다(`missing_dividend_reference`). 추정/대체하지 않았다. 후보 dividend_unsupported 121건은 split 창과 겹치며, 총 split 제외 122건은 유지된다. candidate excluded 총수가 늘어난 이유는 실제 feature 평가가 열리면서 weak_signal 5,196건이 판정됐기 때문이다.

calibration 탈락의 주원인은 edge_not_supported 1,508/1,959(76.98%)이다. 날짜 사유는 서로 중복되며 전체 배타적 NO TRADE 분류는 edge_unsupported 435일, calibration_insufficient 39일, unsupported_market_regime 258일, no_raw_signal 67일, integrity 1일이다. 이는 threshold 완화 근거가 아니다.

추천 265건 중 9건은 holding-period cash dividend로 v3 UNRESOLVED를 유지한다. matched SPY의 미해결/미성숙/평가 제외 및 unpaired 10일도 분모에서 생략하지 않는다. 새 수치는 NORMAL 고정 모델 rolling research 진단이며 저장/live 추천, untouched OOS, alpha 증명이 아니다. **Alpha evidence: INSUFFICIENT EVIDENCE.** 다음 작업은 **고정 계약의 fresh forward/shadow 통계 증거 수집** 하나로 제한한다.

검증: baseline 전체 **173 passed, 0 failed, 0 skipped, 1 warning, 40.43s**; final 전체 **229 passed, 0 failed, 0 skipped, 1 warning, 53.68s**. 기존 baseline 테스트는 변경하지 않았고 56개를 추가했다. 진행 중 shadow 오류 메시지 호환 assertion을 수정한 뒤 최종 전체 통과했다. warning은 기존 pytest cache WinError 5이다. 원본 `var/richping.db` 및 기존 JSON 보고서 7개 SHA-256 동일(`var/m2-1b-integrity.json`). 새 raw vintage를 저장한 별도 DB 외 기존 datasets/recommendations/outcomes에 쓰지 않았다. CLI `--help`와 `git diff --check`도 통과했다.

## 이전 Coverage Diagnostic v1 기록

아래 최초 실측과 운영 점검은 M2-1B 이전 기록이다. 당시 dividend occurrence가 곧 block이던 의미는 위 현재 정의로 대체한다.

M2-1A는 **COMPLETE WITH KNOWN LIMITATIONS**, **GO — close M2-1A and proceed**로 유지한다. 이번 변경은 coverage 측정이며 v3 signal/outcome, 평가 정책, pairing, action capture, PIT, immutable 저장 계약을 변경하지 않는다. M2-1B나 일반배당 지원은 시작하지 않았다.

## 재현

```powershell
.\.venv\Scripts\python -m richping coverage
.\.venv\Scripts\python -m richping coverage --start 2025-01-02 --end 2026-09-14 --output var/coverage-period.json
```

기본 출력은 `var/coverage_report.json`. 입력은 최신 저장 수집판이며 `--dataset-id`로 고정 가능하다. DB는 SQLite `mode=ro`와 `query_only`로 열고 schema/trigger 초기화도 실행하지 않는다. 원본 snapshot, outcome, experiment, risk state, 기존 validation artifact를 쓰지 않는다. 수집판과 코드/config가 같으면 JSON도 동일하다. 생성 시각을 넣지 않는다.

## 분모와 taxonomy

| 부분 | 분모 / 해석 |
|---|---|
| trading_days, benchmark, signal_blocks | 대상 XNYS 거래일. 기본 첫 60일 제외; 61번째부터 계산. signal_supported는 benchmark feature 계산 가능이며 risk-on과 다름 |
| candidate_evaluations | 대상 거래일 × config ticker 수. benchmark 차단일도 데이터 사전 검사를 수행. supported는 Engine raw candidate, excluded는 사전 검사/production 필터 탈락, 나머지는 not_evaluated_benchmark_blocked |
| decision_funnel 날짜 | 대상 거래일. calibration 사유 날짜는 서로 중복 가능 |
| decision_funnel 후보 | 실제 calibration 시도 후보 수. raw candidate 대비 calibration 진입 비율도 별도 기록 |
| recommendations | 거래일당 추천 수(확률 아님) |
| outcomes | 재생에서 선택된 추천의 holding-period outcome 수. 1/3/5/10/20 전체 horizon 수와 섞지 않음 |
| evaluation | COMPLETE holding-period outcome 수. eligible/excluded 및 exclusion reason/version 모두 같은 분모 |
| pairing | 추천이 한 건 이상 선택되어 SPY outcome을 시도한 날짜. signals 호출 날짜와 다름 |

각 metric은 count, denominator, denominator_unit, rate(0~1 비율 또는 명시된 빈도)를 갖는다. 분모 0이면 rate=null. raw total은 분모 자체다.

`window_reasons`는 기존 Dataset.window와 inspect_action_capture를 이용해 dividend/split/capital_gains/action_capture_unknown/data_not_yet_known/missing_or_unknown_history를 분리한다. SPY 오류가 먼저 발생해도 QQQ를 독립 검사한다. `signal_blocks.by_reason`은 benchmark 간 사유별 날짜 합집합이고 `both_benchmarks_dividend`는 교집합이다. 여러 action과 capture unknown은 함께 집계되므로 사유 수를 합하면 전체보다 커질 수 있다. Capital Gains 0건도 capture가 unknown이면 무분배 증명이 아니다.

후보는 먼저 기존 active 판정을 적용하고 not_in_asof_universe를 구분한다. 창이 정상일 때 price_or_liquidity/weak_signal/invalid_risk_reference는 production Engine의 제외 결과를 그대로 쓴다. benchmark 실패일에 후보의 가격·점수·위험 필터를 임의로 계산하지 않는다. 창이 결측이면 action 부재를 추정하지 않는다. shadow helper는 미래 bar/capture/event를 data_not_yet_known으로 구분하며, 보고서 재생은 research로 명시한다.

기본 추천 재생은 production Engine.signals/calibration을 사용하며 매일 과거 label만 calibration에 사용한다. scan의 NORMAL calibration/top-k gate를 적용한다. 운영 위험 latch를 재현하지 않으므로 실제 daily 추천과 동일하다고 주장하지 않는다. REDUCED_EXPOSURE는 library의 명시적 scenario로만 제공하며 강화 edge threshold와 1개 제한을 독립 집계한다. 기본 NORMAL에서 해당 사유 0은 강화 threshold를 시험했다는 뜻이 아니다.

NO TRADE 상위 범주는 상호 배타적이다. benchmark 실패 또는 전 후보 integrity/universe 탈락 → integrity_data_blocked; 다음으로 unsupported_market_regime, no_raw_signal. raw 후보가 있으면 추천 유무를 먼저 판정하고, 추천이 없을 때 reduced_exposure_threshold → edge_unsupported → calibration_insufficient 순서로 분류한다. 세부 calibration 날짜 집계는 중복을 보존한다.

outcome은 기간 말 cutoff로 observe하며 COMPLETE에 기존 cash_action_review_v1을 적용한다. matched SPY도 미성숙·미해결·제외를 보존한다. 두 쪽 eligible date 교집합으로 paired를 구성하며, matched_candidate는 같은 날 후보 평균을 사용한다. 양쪽 모두 부적격인 날짜도 unmatched에 남는다. `coverage_report(..., boundary=fold.calibration_frozen_at)`는 기존 validation fold와 같은 frozen calibration을 제공하며 기존 validation과 결과 일치 테스트가 있다. 기본 rolling coverage를 OOS로 표시하지 않는다.

## 실제 저장 Yahoo 수집판의 실측

- Dataset: `82eb2d624ef2f11e4634eb75f44d8ae849e12bc93e7e83d951a473723b997888`
- 수집판 저장: 2026-09-15. bars 10,020개, 후보 8개 + SPY/QQQ, 전체 1,002거래일.
- 대상: 2022-12-09 ~ 2026-09-14, warmup 60일 제외 **942거래일**.
- 기존 수집판에는 `action_capture`가 없다. 새 metadata를 소급 부여하지 않았다.

| 지표 | 수 / 분모 | 비율 |
|---|---:|---:|
| benchmark feature 가능일 | 0 / 942 | 0% |
| benchmark 차단일 | 942 / 942 | 100% |
| SPY dividend | 915 / 942 | 97.13% |
| QQQ dividend | 915 / 942 | 97.13% |
| SPY 또는 QQQ dividend | 926 / 942 | 98.30% |
| SPY와 QQQ 모두 dividend | 904 / 942 | 95.97% |
| benchmark action_capture_unknown 합집합 | 942 / 942 | 100% |
| candidate dividend | 4,807 / 7,536 | 63.79% |
| candidate split | 122 / 7,536 | 1.62% |
| candidate Capital Gains 관측 | 0 / 7,536 | 0% (capture 미확인) |
| candidate action_capture_unknown | 7,536 / 7,536 | 100% |
| raw candidate 날짜 | 0 / 942 | 0% |
| calibration insufficient / edge unsupported 날짜 | 각각 0 / 942 | 각각 0% (단계 미도달) |
| NO TRADE / integrity_data_blocked | 942 / 942 | 100% |
| 추천 날짜 / 추천 수 | 0일 / 0건 | 0% / 0건·거래일 |
| COMPLETE / PENDING / UNRESOLVED | 0 / 0 / 0 | null (추천 없음) |
| evaluation eligible / excluded COMPLETE | 0 / 0 | null (COMPLETE 없음) |
| paired / attempted recommendation dates | 0 / 0 | null |

이는 해당 저장 수집판의 연구 재생이다. 기존 과거 v2 OOS 수치를 현재 v3 evidence로 재사용하지 않는다. 배당 사유는 전체 기회의 98.30%에 존재하지만 capture 부재와 중복되므로 배당 guard 해제 시 98.30%가 복구된다고 해석할 수 없다.

판정: **Case 4(기존 수집판의 provenance 부재) + Case 2(benchmark 배당 guard)**. Case 3은 calibration 진입이 없어 판정 불가. 현재 실제 alpha 검증 evidence 충분성은 **INSUFFICIENT EVIDENCE**.

가장 작은 다음 작업 하나: **현재 adapter로 새 Yahoo 수집판을 1회 수집하고 동일 coverage를 다시 측정**한다. 기존 수집판은 보존하고 capture 부재와 dividend guard의 영향을 재확인한다. 이 작업에서 네트워크 수집이나 M2-1B는 실행하지 않았다.

## Daily pipeline 점검 범위와 한계

| 항목 | 코드/결정론적 테스트 근거 |
|---|---|
| 증분/previous reuse | yahoo_dataset의 10-session overlap, first-seen 유지; ingestion/action_capture tests |
| legacy capture 없는 입력 | 기존 adapter가 전체 새 vintage 수집으로 전환; 기존판 변경 없음 |
| 수정·신규 기업행동 | 전체 새 vintage, capture 병합 및 변경 탐지의 기존 tests |
| PENDING maturity | PENDING은 확정 저장하지 않으며 이후 track 재관측; 신규 maturity/reuse test |
| immutable outcome reuse | 동일 dataset/key의 확정 저장 body 재사용, INSERT OR IGNORE; 기존 및 신규 tests |
| 중복 run/recommendation | run id, BEGIN IMMEDIATE, SUCCEEDED body 재사용, UNIQUE 제약; 기존 repeat-scan test |
| FAILED/RUNNING | FAILED 재시도, RUNNING은 명시적 recover-runs까지 차단; 기존 failed-run 및 신규 recovery test |
| daily lock | scripts/daily.ps1의 FileShare.None 파일 핸들, finally Dispose. 직접 Python daily 호출은 wrapper lock을 거치지 않음 |
| report write | 임시 파일 작성 후 replace. replace 실패에도 이전 완성 artifact가 유지되는 신규 test |

운영 확장을 요구하는 새로운 코드 blocker는 이 제한된 점검에서 확인하지 않았다. benchmark 실패는 의도된 fail-closed이며 daily scan은 FAILED가 될 수 있다. RUNNING 복구는 자동 안정성으로 포장하지 않는다. lock 경쟁·프로세스 강제 종료·스케줄러·실제 공급자 장애 복구는 다일 production 검증이 아니다.

실제 DB에는 **2026-09-14 shadow SUCCEEDED 1개 날짜**만 있다. 다일 무인 실행 증거는 없고, JSON에도 `unattended_multi_day_stability: NOT_ESTABLISHED`를 기록한다. 코드와 synthetic 테스트 통과만으로 unattended production stability를 주장하지 않는다.

## 검증 결과

전체 `.venv\Scripts\python -m pytest`: **168 passed, 1 warning, 42.81s**, 실패/skip 없음. 기존 145개는 수정하지 않았으며 diagnostic 20개와 운영 반복성 3개를 추가했다. 경고는 기존 `var/.pytest_cache/v/cache/nodeids` 쓰기 WinError 5 / PytestCacheWarning이다. CLI `--help`와 실제 coverage 실행을 확인했다. 원본 `var/richping.db`, 기존 `daily-report.json`, `validation.json`은 coverage 실행 전후 SHA-256이 동일하다.
