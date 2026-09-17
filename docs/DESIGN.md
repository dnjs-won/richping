# MVP 설계 · 2026-09-15

## 1. 이름 / 범위

프로젝트 이름은 **Richping**으로 확정한다. 이미 지정된 디렉터리와 일치하고, 간결한 투자 후보 알림이라는 제품에 맞는다. 패키지/CLI는 `richping`.

미국 주식 long-only, 일봉, 작은 명시적 universe, SPY/QQQ 시장 문맥, 5거래일 중심 추천으로 시작한다. 종가 정보가 완성된 뒤 추천하며 진입 관찰은 다음 거래일 시가부터다. 실제 주문은 없다.

## 2. 기존 자산 검토

검토 범위는 실제 source tree와 아래 파일이다. 실행 테스트를 돌리지 않은 기존 코드를 검증된 자산이라고 부르지 않는다. 기존 DB, 개인정보, 계좌 데이터, 비밀 설정은 읽거나 복사하지 않았다.

| Component | Source / evidence | Decision | Reason |
|---|---|---|---|
| Market/historical loader, API client, cache | adaptive-alpha `work/`, `master/`, `ARCHITECTURE.md` | REWRITE | runtime loader가 없고 개념 설계만 있음 |
| Universe / ticker normalization | adaptive-alpha `ARCHITECTURE.md` | REWRITE | 시점 계약만 참고; 실제 재사용 모듈 없음 |
| Corporate actions / delisting | adaptive-alpha `RESEARCH_PROTOCOL.md` §5 | ADAPT | 조정·상폐 누락을 숨기지 않는 원칙 채택; 코드는 신규 |
| Feature calculation | adaptive-alpha `ARCHITECTURE.md` §3 | REWRITE | 구현 없음; 가격/거래량 최소 특징만 작성 |
| Backtest / walk-forward / OOS | adaptive-alpha `RESEARCH_PROTOCOL.md` §3–7 | ADAPT | 시계열 분할·purge·holdout 재사용 금지 원칙만 적용 |
| Statistical metrics / experiment tracking | adaptive-alpha `RESEARCH_PROTOCOL.md` §4–6 | ADAPT | 날짜 군집·비용·실패 trial 기록 적용; 연구 관료제 제외 |
| Scheduler / retry / logging | 양쪽 source inventory | REWRITE | 이번 일일 배치에 독립적으로 재사용할 구현 없음 |
| SQLite utility | konviction `src/konviction/persistence/database.py` | ADAPT | FK·atomic transaction 패턴 참고. 기존 migration/계좌 schema 미복사 |
| Time validation | konviction `src/konviction/domain/timestamps.py` | ADAPT | aware UTC와 known-at 비교 패턴만 단순 재작성 |
| Kill switch | konviction `domain/risk.py`, `tests/application/test_sticky_drawdown.py` | ADAPT | 상태 강등/보수적 복구 개념만 참고; 계좌 sizing과 분리 |
| Migration integrity tests | konviction `tests/persistence/test_migration_safety.py` | ADAPT | 기존 자료 보존과 실패 원자성 회귀 테스트 관점만 적용 |
| Decision journal / ontology / memory | konviction `domain/decisions.py`, `application/services.py`, README | DROP | 수동 판단·기록 중심, 신규 목적과 불일치 |
| Ledger / FX / order / portfolio NAV | konviction `application/ledger.py`, `trading.py`, `valuation.py` | DROP | 자동 추천 MVP에 불필요한 계좌 결합 |
| Web frontend / old phases | konviction `web/`, 양쪽 ROADMAP | DROP | CLI 보고서면 충분; 기존 순서 상속 안 함 |

결론: 소스 코드 직접 복사는 0개. REUSE 판정은 검증된 독립 구현이 발견되지 않아 없다.

## 3. Architecture

Python modular monolith + SQLite + CLI + OS scheduler. 네트워크 수집은 선택적 yfinance adapter. CSV import와 결정론적 synthetic demo는 네트워크 없이 작동한다. 캘린더는 `exchange_calendars`의 XNYS를 사용한다. 평일 계산으로 거래일을 대체하지 않는다.

```text
data → features/regime → fixed ranker + past-only calibration
                              ↓
                     SQLite frozen recommendation
                              ↓
                future-session outcome → evaluation
```

첫 버전은 데이터/추천 품질을 검증하는 **research/shadow** 엔진이다. 무료 현행 데이터로 역사적 point-in-time 정확성이나 survivorship-free 성과를 주장하지 않는다. 온라인 수집 시 수집 시각을 실제 known-at으로 보존한다. 역사 재생은 공급자 일봉 가용 시각을 가정한 `research` 모드로 명시적으로 분리한다. Demo는 항상 SYNTHETIC 표시.

## 4. Data model / 시간

- `datasets`: source, research/synthetic quality, 내용 hash, 생성 시각. 각 수집판은 불변이며 수정판을 이전판에 덮어쓰지 않는다.
- `bars`: dataset_id + ticker + session. OHLCV, dividend/split, known_at, session close. 가격은 공급자 조정 기준을 dataset metadata에 기록.
- `members`: dataset_id + ticker + active_from/to + known_at + sector. 현재 정적 목록을 과거 구성이라고 주장하지 않는다.
- `model_versions`: 알고리즘·feature·설정 내용 hash + immutable JSON.
- `runs`: session/mode/model/dataset, RUNNING/SUCCEEDED/FAILED, 오류, 재시도 수.
- `recommendations`: run + ticker + rank + snapshot JSON. snapshot에는 feature/regime, 기여점수, cutoff, entry/stop/target, calibration 표본, 기대값, CI, model/config/data/code hash를 저장. 별도 snapshot 테이블 대신 한 행에 넣고 UPDATE/DELETE trigger로 동결.
- `outcomes`: recommendation_id + horizon + 평가 dataset. raw/net return, MFE/MAE, barrier hit 및 상태. 추천과 별도 저장. 미래 데이터가 features를 변경하지 않는다.
- `experiments`: 실행 전에 등록한 분할/비용/모델 및 결과. 실패도 보존.

시각은 UTC aware ISO8601, session은 미국 거래소 날짜. 연구용 cutoff는 거래소 close + 30분. shadow cutoff는 실제 실행 시각이며 다음 장 개장 전이어야 한다. 당일 미완성 bar 사용 금지. 날짜 + horizon은 거래소 session 인덱스다.

## 5. First algorithm

가격 ≥ $5, 과거 20일 평균 dollar volume ≥ $5M, 최근 61개 거래일 연속 데이터 필요. SPY/QQQ 둘 다 없거나 결측이면 실패. 특징: 1/5/20일 수익률, SPY 대비 20일 RS, MA20/MA60, 이전 20일 고점 거리, relative volume, ATR14, realized vol20. 시장은 SPY·QQQ 추세와 SPY 변동성으로 risk-on/off, low/high volatility 분류.

고정 0–100 점수: momentum 25, relative strength 25, trend 20, relative volume 15, breakout 15. 정규화 범위는 코드/모델에 고정하며 전체 미래 데이터로 fitting하지 않는다. Score ≥ 60, 양의 추세, risk-on을 기본 후보로 한다.

기대값은 이전 504 session의 **결과가 완성된** 같은 regime·비슷한 score(±15) 후보로 계산한다. 최소 60건/30개 추천 날짜. 동일 날짜 종목을 먼저 평균한 뒤 5-session block bootstrap으로 비용 후 평균수익의 95% CI 계산. 표본 부족 또는 하한 ≤ 최소 edge(0)이면 NO TRADE. confidence는 같은 표본의 경험적 승률이며 예측 성공 확률 보증이 아니다. expected loss는 손실 표본 평균 크기, expected R/R는 평균 이익/평균 손실. 손실 표본이 없으면 R/R를 미상으로 두고 통과시키지 않는다.

ATR 기반 stop=2 ATR, target=4 ATR는 참고 가격이다. 기대수익과 target 거리를 혼동하지 않는다. 순위는 통과 후보의 고정 score 내림차순, 동점 ticker 순. sector/industry는 알 수 없으면 null; 옵션/펀더멘털 필드는 아직 만들지 않는다.

## 6. Outcome

다음 session 시가를 진입 관찰 가격으로 한다. 1/3/5/10/20번째 session 종가까지 buy-and-hold 가격 수익, MFE/MAE, target/stop hit를 계산한다. 왕복 commission 10bps + slippage 10bps = 20bps 차감. 동일 일봉에서 양 barrier에 닿으면 `AMBIGUOUS`로 명시한다. barrier는 진단용이며 수익률은 일관되게 horizon 종가 기준이다. stop 체결 수익을 가장하지 않는다.

미성숙은 PENDING, 거래정지/상폐/데이터 결측은 UNRESOLVED. 미래 데이터 누락을 0% 또는 다음 관측일로 대체하지 않는다.

계산 버전:
- `v1_price_only` (기존 계약): 관측 기간에 split 또는 dividend가 존재하면 UNRESOLVED(`corporate_action_requires_accounting`)로 격리. 기존 스냅샷은 당시 계약을 불변 유지.
- `v2_ordinary_cash_dividend` (M2-1A):
  - 공급자 계약: Yahoo Finance `auto_adjust=False, back_adjust=False, actions=True` 기준. OHLC 가격은 split-adjusted(배당 미조정)이고, 배당은 배당락일 기준 split-adjusted 주당 현금배당 금액이다. 단위와 권리 조건이 확인된 데이터셋(`dividend_basis: ordinary_cash_split_adjusted_per_share`)만 지원.
  - (과거 재현용 보존 계약이며 현재 신규 평가 승인 정책이 아님; Astra DIVIDEND_CONTRACT_DECISION 확정)
  - 지원 조건 및 식별 한계:
    - 주식분할 없음 (`b.split == 0`). 분할 발생 시 `stock_split_requires_accounting`으로 UNRESOLVED.
    - 단일 배당 금액이 종가의 20% 미만인 적격 일반 현금배당. 공급자 API가 정기/특별 플래그를 제공하지 않으므로, 20% 이상의 배당은 특별/청산 배당 가능성으로 보아 `special_or_irregular_dividend_requires_accounting`으로 보수적 UNRESOLVED 격리.
    - 단위·계약 미확인 데이터(CSV 등)는 `unverified_dividend_basis`로 UNRESOLVED 유지.
  - 권리 및 수익 계산:
    - 진입 session 시가 매수 기준이므로, 진입일 당일이 배당락일이면 해당 배당은 권리가 없으므로 미포함 (`entry_day_dividend_excluded`).
    - 진입 익일부터 관측 종료일까지 발생한 적격 배당(`bars[1:]`)을 누적 합산 (`dividend_cash`).
    - 배당 재투자는 하지 않음: `dividend_return = dividend_cash / entry_price`.
    - 총수익: `raw_return = price_return + dividend_return`.
    - 거래비용은 1회만 차감: `net_return = raw_return - cost`. 가격만의 순수익 `price_net_return`도 별도 확인 가능.
    - 세전 배당 권리 기준 연구용 수익이며, 실제 지급일 입금이나 세후 계좌 수익이 아님을 명시.
    - MFE, MAE 및 target/stop hit는 가격 기준 진단으로 불변.
    - 기대값 추정(`calibration`)과 성과 관측(`observe`)이 동일한 v2 `net_return` 정의를 일관되게 사용.
- `v3_cash_action_guard` (M2-1A-R2-2 현재 기본값):
  - 실패 폐쇄형 현금 기업행동 격리 및 순수 가격 수익 계약.
  - 관측 기간(`days`)에 주식분할 발생 시 `stock_split_requires_accounting` (우선순위 1).
  - shadow 모드에서 capture 시점 미도래(`captured_at > as_of`) 또는 사건 시점 미도래(`known_at > as_of`) 시 `PENDING`, `data_not_yet_known`.
  - 관측 기간 내 Capital Gains 분배금 발생 시 `unsupported_capital_gains_distribution` (우선순위 2).
  - 관측 기간 내 현금배당 발생 시(진입일 `bars[0]` 및 전 기간 포함, 규모 무관) `unverified_cash_dividend_event` (우선순위 3).
  - action capture 누락, ticker 부재, unknown 상태 또는 보유창 미완전 커버 시 `action_capture_unknown` (우선순위 4).
  - 사건이 완전히 없고 검증 완료된 구간만 순수 가격 수익 계산: `raw_return = price_return`, `net_return = raw_return - cost` (비용 1회 차감).
  - 특징 생성(`Engine.signals`):
    - 후보 종목 61 거래일 창 내 split/dividend/Capital Gains 또는 unverified capture 존재 시 후보 제외 (`corporate_action_in_feature_window` 또는 `action_capture_unknown`).
    - 벤치마크 SPY/QQQ 61 거래일 창 내 split/dividend/Capital Gains 또는 unverified capture 존재 시 즉시 `ValueError`로 실패 폐쇄 (침묵형 대체 금지).
    - `Engine.history`는 `COMPLETE` 결과만 포함하며 제외된 결과는 `Engine.excluded_history`에 진단 보존.

## 7. Validation

기본 rolling train 504, validation 63, OOS 63 sessions; 63 sessions씩 전진. feature warmup 61 sessions. 최대 label 20 sessions + embargo 1 session을 경계에서 제외한다. MVP 고정 모델은 parameter fitting 없이 train 표본으로만 calibration하고, validation/OOS에서는 같은 calibration을 동결한다. Random split 금지.

비용 20bps 및 40bps stress, 날짜 군집/block bootstrap, regime별 성과, 표본 수, 완료/미해결/미성숙 분모, 추천 빈도를 기록한다. OOS는 training 밖의 시간 순서 평가라는 의미이며, 현행 정적 universe와 수정된 무료 데이터로 만든 결과는 `research OOS`, 최종 holdout 증거가 아니다.

평가는 추천 단위 expectancy/승률/평균 win/loss/payoff/PF/expected shortfall/tail loss를 우선한다. 같은 날 평균한 추천 수익의 순차 곡선은 **diagnostic cohort curve**라고 표시한다. 중첩 보유 추천을 portfolio NAV로 합성하지 않는다. 실제 일별 NAV가 없으므로 연환산 Sharpe/Sortino/Calmar/portfolio MDD는 null로 남긴다. 후속 단계에서 명시적 일별 포지션 회계를 추가한 뒤 제공한다.

### Coverage Diagnostic v1

`richping.coverage`는 기존 Dataset/Engine/평가 정책을 읽어 집계한다. `coverage` CLI는 DB를 read-only로 열고 `var/coverage_report.json`만 생성한다. 기본 기간은 60-session warmup 이후 전체 거래일이며 NORMAL 고정 모델의 rolling past-only calibration을 재생한다. 기존 validation의 frozen fold나 실제 운영 위험 latch와 구분한다. signal/outcome/평가 계약을 변경하지 않는다.

SPY/QQQ 61-session action 사유를 독립 검사하고 거래일, 후보 ticker-session, holding-period outcome, COMPLETE, pairing 시도 날짜의 분모를 분리한다. action 사유는 중복 가능하고 분모 0의 rate는 null이다. 실제 alpha 및 다일 무인 안정성의 증명이 아니며, 정의와 실측은 [COVERAGE_DIAGNOSTIC.md](COVERAGE_DIAGNOSTIC.md)를 따른다.

## 8. Champion / Challenger

현재 champion은 `baseline-v1` 고정. 첫 milestone에서 자동 학습/승격 실행은 하지 않는다. 작은 순수 gate 함수로 부적격 판정을 테스트한다. Phase 3: 사전 고정한 제한적 weight/threshold 이웃만 생성, trial 수 누적, train 선택 → validation → 미사용 OOS → shadow.

승격 필수: point-in-time universe/vintage와 상폐 포함 결과 완전성, ≥200 OOS 추천 및 ≥60 signal dates, ≥3 folds, regime/parameter 안정성, 양의 비용 stress expectancy, paired date-block 개선 CI 하한 >0, PF≥1.1, tail/drawdown 비악화, 다중시험 보정, fresh shadow evidence. 불충족/미측정은 REJECT. 현재 무료 데이터 adapter와 synthetic 데이터는 자동 승격 불가.

## 9. Kill switch

최근 완료된 30개 추천의 비용 후 expectancy <0이면 REDUCED_EXPOSURE: 후보 수를 1개로 제한하고 minimum edge를 강화. 날짜 cohort diagnostic drawdown ≤-15% 또는 expectancy ≤-2%이면 PAUSED. risk-off/high-vol regime에서도 새 후보 중단. 모델/날짜/모드별 증거만 사용하고 아직 확정되지 않은 미래 outcome은 사용하지 않는다.

성과에 의한 PAUSED는 DB에 유지된다. 재실행/가격 반등만으로 해제되지 않는다. Phase 3의 새로운 shadow 증거와 promotion gate가 자동 복구를 담당한다. MVP에는 임의 reset 명령이 없다. 주문·계좌 노출 제어를 의미하지 않는다. 분포 drift/추정 confidence collapse의 통계적 검사는 Phase 2 이후 확장한다.

## 10. Repository / milestones

```text
richping/           독립 Python package, CLI와 순수 함수
tests/              시점/결측/immutability/통계 회귀
docs/DESIGN.md      이 문서
config.toml        작은 기본 설정
scripts/daily.ps1   일일 배치 진입점
var/               ignored DB, reports, cache
```

M1: demo + data import/sync + scan + 자동 observe + report + leakage tests. M2: 실데이터 vintage/universe 계약, corporate actions/상폐, walk-forward 신뢰도 보강. M3: 제한된 challenger 자동화 및 gate. M4: discovery. M5: advanced data.

첫 실행 결과는 DAILY RECOMMENDATION의 rank/ticker/score/expected return/risk/RR/confidence 또는 이유를 포함한 NO TRADE이며, demo replay 후 actual return/MFE/MAE/hit를 조회할 수 있어야 한다. 합성 결과는 Alpha 증거가 아니다.

## 참고한 외부 기술 계약

- [yfinance history/download](https://ranaroussi.github.io/yfinance/) — 데이터 수집 adapter; 연구용 데이터의 공급자 revision 한계를 보존.
- [exchange_calendars](https://github.com/gerrymanoim/exchange_calendars) — XNYS session 및 close/open.
- [Alpaca market data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) — IEX와 SIP volume 차이를 검토. 첫 MVP에는 계정·feed 선택을 추가하지 않고 yfinance 한 adapter만 사용.
