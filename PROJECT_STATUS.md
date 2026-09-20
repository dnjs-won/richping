# Richping 현재 상태 · 2026-09-20 방향 재정립

**현재 작업: R0-B 실제 forward 1회와 Windows 예약 등록 확인 완료. 예약 trigger 실행과 다일 안정성은 관찰 대기.**

- R0-B는 2026-09-20 22:38 Asia/Seoul에 2026-09-18 신호일의 next-open 이전 창에서 실제 wrapper를 실행했다. 첫 sandbox 실행의 수집 `ConnectionError`/exit 1과 후속 정상 adapter 재시도/exit 0을 모두 보존했다. 성공 결과는 `NORMAL_NO_TRADE`(`insufficient_evidence_or_edge`), freshness `CURRENT`, 새 forward 관측 1건이며 수동 실행 시각은 계획 08:00 대비 `LATE`로 표시된다.
- 정상 sync는 운영 DB에 새 immutable dataset `cf504cff91aa9d220d720660f80b4708d210b793cc16f34120bcefabaceb755f`를 추가했다. 2022-09-19~2026-09-18, 10,040 bars, `yfinance-1.7.0`, capture `2026-09-20T13:38:46.924059+00:00`, 배당 event/단위 증거 117/117건이다. 기존 dataset 3개와 기존 shadow run의 보존 및 모든 dataset content hash를 재검증했다.

- R0-A는 immutable run body와 기존 DB schema를 바꾸지 않는 `richping.operations` 파생 계층을 추가했다. `daily`는 수집 전에 attempt JSON을 만들고 성공·정상 NO TRADE·수집 실패·stale·휴일/중복·outcome 분모를 JSON/Markdown에 구분한다. 기본 운영 출력은 `var/operations`, custom DB와 수동 scan 출력은 `var/research`로 분리된다.
- 보고서는 XNYS next-open 유효시각, dataset session/capture, model/config/code/data ID, feature/outcome/evaluation 계약, 후보 score/기여요인/ATR 참고값, calibration 표본·날짜·CI, 실제 제외 사유, COMPLETE/PENDING/UNRESOLVED와 holding eligible/excluded를 표시한다. SYNTHETIC/RESEARCH/FRESH_SHADOW를 분리하며 Alpha는 **INSUFFICIENT EVIDENCE**, portfolio return은 N/A다.
- 실행 attempt는 runs 생성 전 실패도 남긴다. 실패 보고서는 과거 성공을 `prior_success_reference`로만 표시한다. versioned JSON/Markdown이 모두 완성된 뒤 `latest.json`을 원자 교체하므로 실패한 세대를 최신으로 읽지 않는다. 기존 `var/daily-report.json`은 덮지 않는다.
- read-only forward summary는 model/mode/source/quality/outcome/evaluation 계약별 저장 run·추천·outcome을 집계한다. 동일 recommendation/horizon의 여러 평가 vintage는 최신 저장 dataset rowid 하나만 사용하며 조회 자체는 outcome을 생성하지 않는다.
- reporting code로 model ID는 `baseline-v1-1c499becc6025728`로 바뀌며 code hash는 `8748263a3e98ecaed95611eef2ced7c4b0631ef2ab83296758e76855840efa8e`다. pre-R0 frozen synthetic 입력에서 ticker/score/calibration/참고가격이 동일한 golden test를 통과했다. 동일 config의 과거 shadow performance PAUSED는 새 model ID로 이어져 추천을 차단한다. 계약 필드가 없는 과거 run은 현재 v3로 소급 표시하지 않고 v1/legacy/unknown으로 명시한다.
- 실제 운영 DB는 datasets 4/bars 40,100, shadow SUCCEEDED 2 sessions(2026-09-14, 2026-09-18), 추천/outcome 0/0이다. R0-B 실행 전 `risk_state`는 없었고 실행 후 새 model의 `NORMAL/risk_sample_warmup` 상태 1건이다. 두 model의 config payload가 같고 이전 PAUSED가 없음을 확인했으므로 보고 코드 변경을 이용한 latch 우회는 없다.
- `\Richping Daily`를 현재 사용자 `lifes`, `Interactive`/`Limited`, 매일 Asia/Seoul 08:00에 등록했다. action은 `powershell.exe -NoProfile -File "C:\richping\scripts\daily.ps1"`, working directory는 `C:\richping`, 동시 인스턴스는 `IgnoreNew`다. 동일 역할 task는 이 1건뿐이다. 상태 `Ready`, 다음 실행 2026-09-21 08:00, `LastTaskResult=267011`로 예약 trigger 자체는 아직 실행 전이다. WakeToRun은 false이며 PC가 종료·절전 또는 사용자가 로그아웃한 동안의 실행은 보장하지 않는다.
- 보존 기준 `var/daily-report.json` SHA-256은 실행 전후 `5DD67D2A...F6CDFE`로 동일하다. 운영 DB SHA-256은 새 immutable 행 추가로 `2FAF7497...54FBE1`에서 `72C231CA...CDDA3E`로 바뀌었고 integrity는 `ok`다. 상세 manifest는 `var/operations/r0-b-start-verification.json`, 사람이 읽는 요약은 같은 이름의 `.md`, 실제 보고 예시는 `var/operations/latest.json`과 그 `artifacts.markdown`에 있다.
- 개발 인수 테스트는 성공/후보/정상 NO TRADE/수집 전 실패/stale/휴일·중복/late guard/PENDING 만기/원자 교체 실패/read-only 조회/risk latch·판단 golden·legacy 계약 비소급을 포함한다. 전체 `.venv\Scripts\python -m pytest`는 **239 passed / 0 failed / 0 skipped / 1 warning / 57.29s**. warning은 기존 `var/.pytest_cache` WinError 5다. CLI `--help`, 실제 DB read-only `report`, `git diff --check`도 통과했다.
- 상세 사용·실제 보고 예시·복구·예약 점검: [R0 운영 계약](docs/R0_OPERATIONS.md). **R0 개발과 실제 1회 실행·등록은 확인했지만 예약 trigger의 첫 실행과 다일 안정성·fresh 성과 증거는 아직 확인하지 않았다.**

- 최종 목표는 자동 기회 발견·가설 연구·검증·추천·미래 관찰·통제된 개선을 통해 위험 대비 순수익을 개선하는 것이다. 전체 자동 개선 이전에 일일 관찰 보고서와 모의매매 효용을 제공한다.
- 현재 판정: M1 E2E, M2-1A **COMPLETE WITH KNOWN LIMITATIONS**, M2-1B **COMPLETE** 유지. **Alpha: INSUFFICIENT EVIDENCE**, 장기 무인 안정성 **NOT_ESTABLISHED**, 자동 전략 발견/승격·포트폴리오 회계 미구현.
- 시작 시 로컬 main/추적 origin/main/실제 GitHub main 모두 `26f565a4e6d4ccbd97f1a14a31a03736050c5373`, working tree clean. GitHub는 `git ls-remote` 확인. 아래 문서 변경은 아직 커밋/푸시하지 않았다.
- `var/`는 Git 미추적이다. 후속 `validation-m2-1b.json`/summary 및 `failure-analysis-m2-1b.json`/summary를 직접 확인했다. 현재 model/code ID와 일치하며 핵심 결과·파일 해시는 [ROADMAP §2](ROADMAP.md#2-현재-시스템의-위치-확인한-사실과-증거)에 보존했다. 이번에 실데이터 검증을 다시 실행한 것은 아니다.
- 후속 frozen research OOS: 5 folds, 315 sessions, 추천 157건/62일, COMPLETE/PENDING/UNRESOLVED **122/23/12**, eligible **122건/52일**. 추천 건별 비용 후 expectancy **+1.336%**, PF **2.666**, 2배 비용 expectancy **+1.136%**. 계좌 수익이 아니다.
- SPY paired **47/62일**, 날짜 평균 초과수익 CI **-0.344%p~+1.916%p**. 적격 122건 중 첫 fold 112건, 모든 적격 결과는 RISK_ON_LOW_VOL. NVDA/AVGO가 추천 수익 단순 합계의 97.37%를 차지한다는 로컬 집중 진단도 확인. 시간·종목 안정성과 알파는 미검증이다.
- fold 2/3의 주 병목은 raw 신호 부족이 아니라 calibration edge CI 하한이다. 종목별 calibration은 로컬 제안 가설일 뿐 미구현·미채택. 이미 본 OOS에서 개선돼도 승격 증거로 재사용하지 않는다.
- `validate()`의 REJECT는 `promotion_gate({})` 호출 결과이며 실제 집계된 각 지표가 전부 실패했다는 의미가 아니다. evidence builder와 자동 승격 writer는 없다.
- R0-B 후 read-only DB 실측: 운영 DB datasets 4/bars 40,100, shadow 성공 **2일**, 추천/outcome **0/0**. M2-1B 별도 DB는 dataset 1/bars 10,020, runs/recommendations/outcomes/experiments **모두 0**. 별도 파일의 `fresh`는 forward 실적이 아니다. R0-B 전 기존 dataset/run과 보존 보고서는 유지됐다.
- 이번 검증: `.venv\Scripts\python -m pytest` **229 passed / 0 failed / 0 skipped / 1 warning / 61.29s**. warning은 기존 pytest cache WinError 5. CLI `--help`, `git diff --check`, 문서 내 로컬 파일 링크 검사 통과. 원문 OOS predictions에서 집중도·날짜 CI도 재계산해 로컬 요약과 대조했다. 기본 demo/daily/sync/validate는 기존 산출물 보존을 위해 이번 조사에서 실행하지 않았다.
- **다음 요청은 R1-A: baseline 평가 정리와 최소 paper 회계 계약 확정.** [ROADMAP](ROADMAP.md), [R0 운영 계약](docs/R0_OPERATIONS.md)을 따른다. 예약 trigger의 첫 실행과 이후 다일 관찰은 운영 중 계속 확인한다. 옛 문서의 “다음 작업 하나”는 당시 결정이며 현재 순서는 이 계획으로 대체한다.

---

아래는 당시 완료 판정과 미해결 제약을 보존한 역사 기록이다. 과거 시점의 테스트 수·데이터 기간·다음 작업을 현재 상태와 혼동하지 않는다.

# Richping 구현 상태 · 2026-09-17 (M2-1B, 역사 기록)

**M2-1B status: COMPLETE**

**Recommendation pipeline structurally unblocked: YES**

- Root cause: provenance 복구 후에도 61-session cash dividend blanket guard가 benchmark 926/942일을 차단했다.
- `cash_gap_backward_v1` 공통 feature helper를 benchmark/candidate/Engine.history/coverage에 적용. 과거 OHLC를 `1-D/previous_close`로 조정하고 마지막 가격에 anchor. 원본 volume 및 raw dollar-volume 유지. 단위 증거·큰 분배·split·Capital Gains·unknown·shadow cutoff는 fail closed.
- **Feature dividend normalization ≠ Outcome dividend accounting.** v3, `cash_action_review_v1`, 모든 전략/통계/risk threshold와 boundary/embargo는 그대로다. code_hash/model_id에 새 모듈이 포함된다. DB schema 변경 없음.
- 별도 DB `var/m2-1b-fresh.db`의 새 dataset: `7d573d75465eb054f3cc89cde451d11fdbd4787f3353c67e84b292be653af2e8`, `yfinance-1.7.0`, 10,020 bars, 116개 배당 단위 증거. 기존 `0910...5771`와 원본 OHLCV/actions 전부 동일. 기존 immutable dataset을 수정하지 않았다.
- 942일 비교: benchmark supported **16→941**, blocked **926→1**. 남은 1일은 첫 QQQ 배당의 직전 종가 부재. capture unknown 0. 후보 supported **19→2,210**, raw candidate dates **9→754**, calibration **12→1,959**, 추천 재생 **0→142일/265건**.
- v3 COMPLETE/PENDING/UNRESOLVED **256/0/9**. 미해결 9건 모두 holding cash dividend. 평가 eligible/excluded **256/0**, SPY paired **132/142일**.
- Current dominant blocker: calibration의 비용 후 edge 근거 부족(`edge_not_supported` 1,508/1,959 시도).
- Alpha evidence: **INSUFFICIENT EVIDENCE**. 현재 고정 universe의 research 진단이며 alpha 또는 무인 다일 운영 안정성 증명이 아니다.
- Next milestone: **고정 계약의 fresh forward/shadow 통계 증거 수집**.
- 실측·재현 명령: [Coverage Diagnostic](docs/COVERAGE_DIAGNOSTIC.md). 가격/단위/지원 범위: [Design](docs/DESIGN.md). 원본 DB와 기존 보고서 7개의 SHA-256 보존: `var/m2-1b-integrity.json`.
- 전체 테스트: baseline **173 passed / 0 failed / 0 skipped / 1 warning (40.43s)** → final **229 passed / 0 failed / 0 skipped / 1 warning (53.68s)**. 기존 173개 테스트 변경 없이 56개 추가. warning은 기존 pytest cache WinError 5. 최종 로그 `var/m2-1b-final-tests.txt`; CLI `--help`, `git diff --check` 통과.

---

아래는 M2-1A 및 최초 Coverage Diagnostic의 역사적 기록이다. feature 계약과 다음 작업은 위 M2-1B 상태를 따른다.

# Richping 구현 상태 · 2026-09-17 (M2-1A 종료)

## M2-1A 마일스톤 판정

**상태: COMPLETE WITH KNOWN LIMITATIONS**  
**감사 결론: GO — close M2-1A and proceed**

## Coverage Diagnostic v1 · 2026-09-17

- `python -m richping coverage` 추가: 기존 Dataset/Engine/평가 함수를 사용하는 read-only research coverage 집계. 기본 출력 `var/coverage_report.json`. DB schema 및 signal/outcome/evaluation 계약 변경 없음.
- 거래일 / candidate ticker-session / holding-period outcome / COMPLETE / pairing 시도 날짜 분모를 분리하고 count·rate·분모 단위를 보존. SPY/QQQ 배당·분할·Capital Gains·capture unknown을 독립 검사하며 중복 사유와 합집합을 구분.
- 기존 Yahoo 수집판(`82eb2d624ef2f11e4634eb75f44d8ae849e12bc93e7e83d951a473723b997888`)에는 action_capture가 없음. 2022-12-09~2026-09-14의 942 대상 거래일 중 benchmark 지원 0일, 차단 942일(100%).
- SPY 배당 guard 915일(97.13%), QQQ 915일(97.13%), 합집합 926일(98.30%). capture unknown은 942일(100%)이며 배당과 중복. 후보 7,536 ticker-session 중 배당 4,807(63.79%), split 122(1.62%), capture unknown 7,536(100%). Capital Gains 관측 0은 무분배 증명이 아님.
- research 재생 추천 0일/0건, NO TRADE 942일, COMPLETE/PENDING/UNRESOLVED 0/0/0, eligible/excluded 0/0, paired 0. calibration/edge 단계 미도달. 과거 v2 OOS 숫자를 현재 evidence로 재사용하지 않음.
- **Case 4 + Case 2; 실제 alpha 검증 충분성은 INSUFFICIENT EVIDENCE.** 가장 작은 다음 작업: 현재 adapter로 새 Yahoo 수집판을 한 번 수집한 뒤 동일 coverage 재측정. M2-1B는 시작하지 않음.
- Daily 코드/테스트 점검: 증분 재사용, PENDING 성숙, immutable outcome 재사용, 중복 안전성, FAILED/RUNNING 복구, wrapper lock, report atomic replace 확인. 실제 DB는 shadow 성공 1일뿐이므로 다일 무인 운영 안정성은 **NOT_ESTABLISHED**.
- 전체 `.venv\Scripts\python -m pytest`: **168 passed, 1 warning, 42.81s** (기존 145개 + 신규 23개, 실패/skip 없음). 경고는 기존 `var/.pytest_cache` 쓰기 WinError 5. 기존 M2-1A tests 수정 없음.
- 실제 coverage 실행 전후 원본 DB 및 기존 daily/validation artifact SHA-256 동일. CLI `--help` 확인. 상세 계약·실측·운영 점검은 [Coverage Diagnostic](docs/COVERAGE_DIAGNOSTIC.md).

---

## 구현 완료 범위

- **독립 인프라**: Python 가상환경, SQLite 스키마, configuration, CLI.
- **데이터 & 팩터**: 실제 일봉 수집, 고정 ranking, 과거 확정 표본 calibration, immutable snapshot.
- **자동 관측 & 파이프라인**: 1/3/5/10/20 session 자동 관측, missing/action 격리, NO TRADE, rolling walk-forward OOS, 일일 자동화 스크립트.
- **R2-1 Provenance 보강**: `action_capture` 증분 provenance 보존, yfinance 수집 계층 Capital Gains 보존.
- **R2-2 계산 엔진**: `v3_cash_action_guard` fail-closed 가드 계약 및 61-session feature window 기업행동 차단.
- **R2-2-R1 시점 제약 보강**: synthetic shadow 시점 검사 우회 제거, `captured_at` 및 event `known_at <= as_of` 검증.
- **R2-3 평가 정책 격리**: `cash_action_review_v1` 정책 격리, v2 COMPLETE 성과 제외, 분모/사유/버전 보존.
- **저장 결과 무결성 (Sol High Finding 1)**: DB 저장된 v3 outcome의 불변성 보존, structural integrity (horizon, end_session, observed_at 누락/형식) 실패 폐쇄, 보유 bar `known_at <= observed_at` 검증.
- **페어링 & 벤치마크 분모 (Sol High Finding 2)**: matched SPY의 UNRESOLVED/PENDING 전체 관측 분모 보존, signal-date 기준 pairing 진단 보존, 동일 paired date 기반 `matched_candidate` cohort 지표 제공.
- **수집 시점 provenance (Sol Medium Finding 3)**: Yahoo 일봉 수집 시 metadata fallback 접근 완료 이후 `symbol_captured_at = utcnow()` 기록 및 최댓값 `overall_captured_at` 사용으로 실제 응답 전 시점 기록 방지.
- **계약 문서화 (Sol Medium Finding 4)**: README 및 현재 구현 상태 문서의 v2(역사적 계산 보존)/v3(fail-closed 가드) 계약 동기화.

---

## 실제 검증 결과

- Python 3.13.7, 테스트 **145 passed / 0 failed / 0 skipped** (추가 옵션 없는 기본 `.\.venv\Scripts\python -m pytest` 100% 통과).
  - `tests/test_action_capture.py`: 37 passed
  - `tests/test_cli.py`: 2 passed
  - `tests/test_dividends.py`: 59 passed
  - `tests/test_evaluation.py`: 16 passed
  - `tests/test_ingestion.py`: 5 passed
  - `tests/test_integrity.py`: 23 passed
  - `tests/test_validation.py`: 3 passed
- *환경 경고*: `var/.pytest_cache` 캐시 쓰기 시 발생하는 `PytestCacheWarning`은 Windows 파일 잠금 관련 환경 warning이며 테스트 결과에는 영향 없음.
- 합성 70-session 재생: 추천 72건, 완료 horizon 결과 360개. 추천 있는 날 49일, NO TRADE 21일.
- 합성 기본 504/63/63 walk-forward: 4 folds, 완료 OOS 추천 label 313개.
- 실제 Yahoo 수집: 후보 8종목 + SPY/QQQ, 일봉 10,020개, 마지막 session 2026-09-14.
- 실제 shadow scan: 시장 조건 미충족으로 NO TRADE.
- 실제 기본 walk-forward: 5 folds, 완료 OOS 추천 54건 / 43개 날짜. 상세 기간·비용·분모·국면별 결과는 `var/validation.json`에 보존.
- 원본 참조 프로젝트(`konviction`, `adaptive-alpha`) 코드는 0개 복사, 완전 독립 구현.

---

## 검수 및 마일스톤 종료 기록

- **Gemini 구현**: R2-1, R2-2, R2-2-R1, R2-3 및 Sol 지적사항 국소 수정 구현 완료.
- **GPT-5.6 Sol 감사**: 독립 correctness audit 수행 완료.
  - 최초 audit에서 `2 HIGH + 2 MEDIUM` correctness finding 발견.
  - remediation 및 regression test 보강 후 최종 targeted review: **PASS — targeted findings closed; ready for Astra milestone audit**.
- **Astra 마일스톤 감사**:
  - 판정: **COMPLETE WITH KNOWN LIMITATIONS**
  - 결정: **GO — close M2-1A and proceed**

---

## 현재 계약 (Outcome & Policy Contract)

- **`v1_price_only`**:
  - Legacy compatibility 계약. 기업행동 존재 시 UNRESOLVED.
- **`v2_ordinary_cash_dividend`**:
  - 역사적 계산 계약 보존용.
  - 일반 현금배당 권리 수익 계산 산술을 포함하나, 현재 `cash_action_review_v1` 승인 성과 evidence에서는 전량 제외(`legacy_v2_unverified_contract`).
- **`v3_cash_action_guard`**:
  - **현재 기본 outcome contract**.
  - 일반 현금배당 지원 계약이 아니며, 검증되지 않은 corporate-action window를 fail-closed 격리하는 가격 수익 가드 계약.

---

## 반드시 남겨야 할 한계 (Known Limitations)

1. **일반 현금배당 실데이터 자동 지원 미완료**: 현재 확보된 무료 공급자 경로에서 검증된 ordinary cash dividend 자동 수용 경로는 승인되지 않음.
2. **복합 기업행동 회계 미완료**: Comprehensive split, 특별배당, 자본환급, 복합 corporate action 회계 미지원.
3. **상장폐지 회수금 미완료**: 상장폐지 최종 청산/회수금 계산 미지원.
4. **Point-in-Time Universe 미완료**: 현재는 고정된 현재 종목군을 사용하며, 역사적 membership 및 survivorship-bias free 데이터셋이 아님.
5. **Alpha 미검증**: 비용 후 양의 기대값(positive after-cost alpha)은 입증되지 않음.
6. **과거 성과 증거 배제**: 기존 OOS 결과는 현재 v3 승인 성과 증거로 간주하지 않음 (연구용 진단 지표).
7. **포트폴리오 미구현**: 포트폴리오 NAV 원장 및 실거래 자동 주문 실행(execution)은 MVP 범위 밖이며 미구현.

---

## 다음 단계 방향 (Next Steps)

Astra 감사 결론에 따라 인프라 선행 확장을 지양하고, **`측정 → 병목 확인 → 필요한 최소 구현`** 원칙으로 진행한다.

1. **실데이터 evaluation coverage 측정**: 현재 v3 가드 계약 하에서 실제 evaluation 커버리지 비율 측정.
2. **무인 daily 파이프라인 안정 운영 확인**: 일일 수집/track/scan의 장기 무인 반복 운영 안정성 확보.
3. **기업행동 차단 비율 측정**: SPY/QQQ 및 후보군에서 배당/기업행동으로 인한 UNRESOLVED 차단 비율 진단.
4. **신규 forward/shadow 증거 축적**: 미래 편향 없는 fresh out-of-sample forward 관측 데이터 축적.
5. **병목 기반 후속 단계 진행**: 실측 결과 기업행동 차단이 실제 성과 측정의 핵심 병목으로 확인될 경우에만 M2-1B(feature window) 또는 후속 R3/R4 단계 검토.
