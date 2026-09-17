# Richping

작은 종목군의 일봉에서 후보를 순위화하고, 추천 당시 정보를 동결하고, 미래 결과를 자동 측정하는 독립 Python/SQLite 프로젝트.

현재는 **M1 research/shadow MVP**다. 합성 데이터로 전체 흐름을 실행할 수 있고 실제 일봉 수집 adapter도 포함한다. 수익성이나 자동 개선 완료를 의미하지 않는다.

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

`config.toml`의 8개 미국 주식 + SPY/QQQ 데이터를 수집하고, 기존 추천 결과를 관측한 뒤, 완료된 최신 일봉으로 다음 개장 전 후보를 생성한다. 첫 실행은 약 4년치, 이후 10-session overlap으로 증분 수집한다. overlap 수정·신규 기업행동 발견 시 전체 새 vintage를 저장한다. 네트워크 오류는 최대 3회 재시도. 성공 보고서는 `var/daily-report.json`, DB는 `var/richping.db`.

한국 시간 오전 8시처럼 미국장 종료 후 다음 개장 전에 실행한다. 이미 다음 장이 열렸으면 새 추천은 실패 처리한다. 시장 휴일엔 최근 완료 session을 재사용하고 추천을 중복 생성하지 않는다. 데이터 장애 시 이전 보고서를 오늘 보고서로 출력하지 않는다.

Windows 작업 스케줄러에서 `powershell.exe -NoProfile -File C:\richping\scripts\daily.ps1`를 매일 08:00에 실행하도록 한 번 등록하면 된다. 스크립트는 중복 실행을 막고 `var/daily.log`에 로그를 쓴다. 이 구현은 시스템 작업을 자동 등록하지 않는다. UI/메일/알림 전송은 아직 없다.

분리 실행:

```powershell
.\.venv\Scripts\python -m richping sync
.\.venv\Scripts\python -m richping scan
.\.venv\Scripts\python -m richping observe
.\.venv\Scripts\python -m richping report
.\.venv\Scripts\python -m richping evaluate
.\.venv\Scripts\python -m richping validate
```

`--db`와 `--config`는 subcommand 앞에 둔다. 과거 재생은 `scan --mode research --session YYYY-MM-DD`로 명시한다. 캘린더 범위는 1990–2035이다. 중단된 RUNNING 작업은 다른 프로세스가 없음을 확인한 뒤 `recover-runs`로 FAILED로 전환하고 재실행한다. 일반 오류는 FAILED로 자동 기록된다.

## 결과 읽기

- Score는 고정 규칙 점수. Expected Return은 과거 유사 후보의 날짜 평균 비용 후 5-session 수익 추정.
- Expected Loss는 손실 표본의 평균 손실 크기. R/R는 평균 이익/평균 손실.
- Confidence는 과거 후보 승률이다. 검증된 개별 예측 확률이 아니다.
- Entry/Stop/Target은 추천 종가 및 ATR 기반 참고값. 실제 체결이나 예상 수익과 다르다.
- 최소 표본이나 기대값 신뢰구간을 충족하지 않으면 정상적으로 **NO TRADE**.
- COMPLETE / PENDING / UNRESOLVED를 모두 보고한다. 미해결 상폐/분할/미확인 배당을 0%나 정상 수익으로 바꾸지 않는다.
- M2-1A: `v2_ordinary_cash_dividend`는 역사적 계산 계약 보존용이며, 현재 `cash_action_review_v1` 정책에서 v2 COMPLETE는 현재 성과 증거에서 제외된다. 현재 기본 계약은 `v3_cash_action_guard`로, 현금배당 자동 지원 버전이 아니라 검증되지 않은 기업행동을 fail-closed로 격리하는 계약이다. 일반 현금배당 실데이터 자동 지원은 아직 승인되지 않았으며, 특징 창 배당 종목 제외 규칙은 유지된다.

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

무료 현재 데이터와 정적 종목군은 역사적 시점 무결성·상폐 종목 커버리지를 보증하지 않는다. 따라서 실제 데이터의 결과도 **research OOS**이며 자동 승격 증거로 사용할 수 없다. 기업행동을 포함하는 feature/outcome 창은 보수적으로 제외/미해결 처리한다. 이는 커버리지 제한이며 성과 선택 편향을 해결한 것이 아니다.

포트폴리오 원장을 만들지 않았으므로 portfolio Sharpe/Sortino/Calmar/MDD는 N/A다. cohort drawdown은 순차 날짜별 추천 수익의 진단값이며 계좌 drawdown이 아니다.

Champion은 고정 baseline-v1. 자동 challenger 학습·승격, 주식분할 및 복합 corporate-action 회계, point-in-time universe, 상폐 최종 수익은 후속 단계다. 현재 gate는 증거가 빠지면 REJECT. Performance PAUSED는 자동 재실행으로 해제되지 않는다.

## 문서

- [최상위 명세](PROJECT_SPEC.md)
- [14개 설계 항목, 재사용 분석, 단계별 계획](docs/DESIGN.md)
- [현재 구현/검증 상태](PROJECT_STATUS.md)

외부 기술 계약: [yfinance](https://ranaroussi.github.io/yfinance/), [exchange_calendars](https://github.com/gerrymanoim/exchange_calendars). 기존 프로젝트 코드는 직접 복사하지 않았다.
