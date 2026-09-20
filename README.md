# Richping

작은 종목군의 일봉에서 후보를 순위화하고, 추천 당시 정보를 동결하고, 미래 결과를 자동 측정하는 독립 Python/SQLite 프로젝트.

현재는 **M1 E2E + M2-1A 무결성 보강 + M2-1B feature 배당 정규화 + R0-A 일일 관찰 보고가 구현된 research/shadow 시스템**이다. 수익성이나 자동 개선 완료를 의미하지 않는다. 실제 예약 실행과 다음 개장 전 운영 확인은 R0-B, 다일 안정성과 fresh 성과 증거는 이후 관찰 범위다. [새 로드맵](ROADMAP.md), [첫 구현 명세](docs/FIRST_MILESTONE.md), [R0 운영 계약](docs/R0_OPERATIONS.md)을 따른다.

## 시작

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-lock.txt
.\.venv\Scripts\python -m pip install -e ".[data,dev]"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m richping demo
```

Demo는 네트워크 없이 동작한다. 가상 종목 ALFA/BETA/GAMA/DELT와 합성 데이터를 쓰며 `var/demo.db`, `var/demo-report.json`, `var/demo-outcomes.json`을 만든다. 재실행 시 추천·결과를 중복 삽입하지 않는다. 실데이터 DB와 분리한다.

## 실제 데이터 / 일일 실행

```powershell
.\.venv\Scripts\python -m richping daily
```

`config.toml`의 8개 미국 주식 + SPY/QQQ 데이터를 수집하고, 기존 추천 결과를 관측한 뒤, 완료된 최신 일봉으로 다음 개장 전 후보를 생성한다. 첫 실행은 약 4년치, 이후 10-session overlap으로 증분 수집한다. overlap 수정·신규 기업행동 발견 시 전체 새 vintage를 저장한다. 네트워크 오류는 최대 3회 재시도. 운영 DB는 `var/richping.db`, 파생 보고서는 `var/operations/latest.json`과 그 안의 `artifacts.markdown`, 실행 시도는 `var/operations/attempts/*.json`이다. 기존 `var/daily-report.json`은 보존한다.

한국 시간 오전 8시처럼 미국장 종료 후 다음 개장 전에 실행한다. 이미 다음 장이 열렸으면 새 추천은 실패 처리한다. 시장 휴일엔 최근 완료 session을 재사용하고 추천을 중복 생성하지 않는다. 데이터 장애 시 이전 보고서를 오늘 보고서로 출력하지 않는다.

Windows 작업 스케줄러의 미래 운영 계약은 `powershell.exe -NoProfile -File C:\richping\scripts\daily.ps1`를 매일 Asia/Seoul 08:00에 실행하는 것이다. 스크립트는 중복 실행을 막고 `var/operations/daily.log`에 로그를 쓴다. `scripts/check_daily_task.ps1`는 등록·계정·action·trigger·마지막 종료 코드를 읽기 전용으로 점검한다. R0-A는 시스템 작업을 자동 등록하지 않았고 실제 실행 확인도 하지 않았다. UI/메일/Telegram 전송은 없다.

분리 실행:

```powershell
.\.venv\Scripts\python -m richping sync
.\.venv\Scripts\python -m richping scan
.\.venv\Scripts\python -m richping observe
.\.venv\Scripts\python -m richping report
.\.venv\Scripts\python -m richping evaluate
.\.venv\Scripts\python -m richping validate
.\.venv\Scripts\python -m richping coverage
```

`--db`와 `--config`는 subcommand 앞에 둔다. 과거 재생은 `scan --mode research --session YYYY-MM-DD`로 명시한다. 캘린더 범위는 1990–2035이다. 중단된 RUNNING 작업은 다른 프로세스가 없음을 확인한 뒤 `recover-runs`로 FAILED로 전환하고 재실행한다. 일반 오류는 FAILED로 자동 기록된다.

`coverage`는 최신 저장 dataset을 SQLite read-only로 읽고 `var/coverage_report.json`을 원자적으로 생성한다. 네트워크 수집이나 DB 변경 없이 반복 가능하다. `--start`, `--end`, `--dataset-id`, `--output`으로 대상 기간·수집판·출력 경로를 지정할 수 있다. 기본 대상은 첫 60거래일 warmup 이후 전체 거래일이다.

SPY/QQQ의 61-session 배당·분할·Capital Gains·capture unknown을 각각 검사하고, 중복 사유와 합집합을 기록한다. 거래일, 후보 ticker-session, 추천 holding-period outcome, COMPLETE, pairing 시도 날짜의 분모는 분리된다. 추천 funnel은 NORMAL 상태의 고정 모델 research 재생이며 실제 저장 추천이나 OOS/무인 운영 증거가 아니다. 자세한 정의와 실측·운영 점검은 [Coverage Diagnostic v1](docs/COVERAGE_DIAGNOSTIC.md)에 있다.

2026-09-20 확인 기준, 저장 실제 shadow는 2026-09-14 NO TRADE 1일, 추천/outcome 0/0이다. `report`는 이를 STALE 및 `Execution: NOT_RECORDED`로 표시하고 저장된 forward 그룹을 model/mode/source/quality/계약별로 읽기 전용 집계한다. 새 `daily`는 수집 전 attempt를 만들므로 오늘 실패가 과거 성공에 가려지지 않는다. M2-1B 별도 DB의 수집판/연구 결과는 일일 운영 실적이 아니다.

## 결과 읽기

- Score는 고정 규칙 점수. Expected Return은 과거 유사 후보의 날짜 평균 비용 후 5-session 수익 추정.
- Expected Loss는 손실 표본의 평균 손실 크기. R/R는 평균 이익/평균 손실.
- Confidence는 과거 후보 승률이다. 검증된 개별 예측 확률이 아니다.
- Entry/Stop/Target은 추천 종가 및 ATR 기반 참고값. 실제 체결이나 예상 수익과 다르다.
- 최소 표본이나 기대값 신뢰구간을 충족하지 않으면 정상적으로 **NO TRADE**.
- COMPLETE / PENDING / UNRESOLVED를 모두 보고한다. 미해결 상폐/분할/미확인 배당을 0%나 정상 수익으로 바꾸지 않는다.
- M2-1B: 검증된 Yahoo 배당 단위 증거가 있는 feature 창은 마지막 원본 가격에 고정한 OHLC 정규화를 사용한다. 기존 vintage에 증거를 소급 부여하지 않으며 새 `sync` 수집이 필요하다. **Feature dividend normalization ≠ Outcome dividend accounting.** 기본 outcome `v3_cash_action_guard`는 holding-period 배당을 계속 UNRESOLVED로 격리한다. `cash_action_review_v1`의 v2 COMPLETE 성과 증거 제외도 유지한다. 세부 지원 범위는 [설계 계약](docs/DESIGN.md)을 따른다.

## CSV contract

```text
bars.csv:
ticker,session,open,high,low,close,volume,known_at,dividend,split

members.csv:
ticker,active_from,active_to,known_at,sector,industry
```

UTF-8, ticker 대문자, UTC offset을 포함한 known_at. session은 XNYS 거래일. 일봉 known_at은 close+30분 이후. dividend/split 값은 없으면 0이지만 공급자는 기업행동의 누락 여부를 검증해야 한다. OHLC 조정 단위를 섞지 않는다. CSV는 현 단계에서 research 품질로만 수용한다.

```powershell
.\.venv\Scripts\python -m richping import-csv bars.csv members.csv
```

## 검증과 한계

기본 504 train / 63 validation / 63 OOS sessions, 최대 horizon 20 + embargo 1, 63 sessions씩 전진. 고정 baseline은 validation 시작 시 calibration을 동결한다. 실험은 실행 전 등록하고 실패 결과도 남긴다. OOS와 비용 2배 stress, 국면별 지표, SPY 동일 날짜 비교를 `var/validation.json`에 저장한다.

무료 현재 데이터와 정적 종목군은 역사적 시점 무결성·상폐 종목 커버리지를 보증하지 않는다. 따라서 실제 데이터의 결과도 **research OOS**이며 자동 승격 증거로 사용할 수 없다. Feature 창은 검증된 배당만 정규화하고 미지원 기업행동은 제외한다. Outcome 창의 기업행동 격리는 유지한다. 이는 성과 선택 편향을 해결한 것이 아니다.

포트폴리오 원장을 만들지 않았으므로 portfolio Sharpe/Sortino/Calmar/MDD는 N/A다. cohort drawdown은 순차 날짜별 추천 수익의 진단값이며 계좌 drawdown이 아니다.

Champion은 고정 baseline-v1. 자동 challenger 학습·승격, 주식분할 및 복합 corporate-action 회계, point-in-time universe, 상폐 최종 수익은 후속 단계다. 현재 gate는 증거가 빠지면 REJECT. Performance PAUSED는 자동 재실행으로 해제되지 않는다.

## 문서

- [최상위 명세](PROJECT_SPEC.md)
- [14개 설계 항목, 재사용 분석, 단계별 계획](docs/DESIGN.md)
- [현재 구현/검증 상태](PROJECT_STATUS.md)
- [목표 재정의·현 상태 평가·R0~R6 로드맵](ROADMAP.md)
- [다음 Codex 세션 R0 구현 명세](docs/FIRST_MILESTONE.md)
- [R0 일일 보고·시도·예약 점검 계약](docs/R0_OPERATIONS.md)

외부 기술 계약: [yfinance](https://ranaroussi.github.io/yfinance/), [exchange_calendars](https://github.com/gerrymanoim/exchange_calendars). 기존 프로젝트 코드는 직접 복사하지 않았다.
