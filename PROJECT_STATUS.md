# Richping v2 상태 · 2026-09-30 extended-session research contract

**Generic extended-hours capability: COMPLETE. H0001은 DRAFT / BLOCKED_ON_DECISIONS다.**
**V2-A/B/C0 완료 상태는 유지하며 이번 작업은 H0001 C1 구현이 아니다.**

- `v2-c0-extended-session-contract` / `var/worktrees/v2-extended`를 지정 HEAD
  `73b5d3d5c096c0a2612c39191e6fd4b7980d8f7a`에서 생성했다. 루트 main의 기존
  cli/maturity/paper/pipeline 수정과 미추적 테스트는 보존했다. main merge 없음.
- 기존 `XNYS_RTH` capability는 유지했다. 별도 `US_EQUITY_EXTENDED_04_20` /
  `v2_extended_c1_signal_v1`은 America/New_York 04:00–20:00의 15m 연구 grid와
  PREMARKET/RTH/AFTER_HOURS metadata를 제공한다. 정규장은 09:30–16:00이다.
- extended 1H는 04:00–05:00부터 19:00–20:00까지 4개 입력씩, Daily는
  04:00–20:00 전체 64개 입력으로 집계한다. 모든 입력이 완료·도착한 후 공개하며
  known_at=max(input known_at) 및 same-known-at atomic batch를 유지한다.
  RTH Daily/1H와 session·aggregation version을 구분하고 혼합을 거부한다.
- 별도 extended continuity는 09:30/16:00 전환을 연속으로 처리한다. Overnight,
  주말, XNYS 휴일은 calendar gap이며 결측 bar가 아니다. DST는 IANA timezone을
  따른다. 겨울 20:00의 다음 UTC 날짜도 원래 ET session으로 식별한다.
- 조기폐장/비표준 XNYS 날짜의 extended availability는 일반화하지 않는다.
  해당 날짜 전체와 그 날짜를 가로지르는 dataset을 fail closed 처리한다.
  RTH 조기폐장 지원은 불변이다. 이 제한 때문에 일부 기간에서는 Daily 130개
  연속 이력을 확보할 수 없으며 gate를 완화하거나 bar를 만들지 않는다.
- 다섯 결정만 executable draft v4에 반영했다: H1-SESSION=RTH_EXTENDED,
  H1-BASE=15m, H1-EMA-SEED=first_observation/first_macd_observation/close/
  `macd_first_observation_recursive_v1`, H1-MACD-HISTORY=Daily/1H/15m 각각 130,
  H1-HISTORY-ORIGIN=전체 available completed causal history·세션 간 유지·EMA reset 없음.
  relative-transform lookback과 다른 strategy decision은 미결정 상태다.
- 남은 결정은 **C1 46 + performance 17 + optional 7 = 70개**, 미결정 경로 **97개**다.
  전체 decision ID 75개 및 state machine은 보존했다. `require_session_capability()`는
  통과하지만 `require_c1_ready()`는 `C1 requires FROZEN specification without C1 blockers`로
  거부한다. stale RTH claim은 거부하고 compatible extended fixture만 세션 admission을 통과한다.
- chart parity는 **UNVERIFIED**. 선택한 strategy session과 04:00 1H anchor는
  명시했지만 observed provider는 UNRESOLVED, observed exact 1H convention은 UNVERIFIED다.
- r03 원본 raw byte SHA-256은
  `abdd4f10d127ee7614a4eead734d1bfbf7dc1897ec368f8a3b70a1645e2552fc`로 불변이다.
  r04는 생성하지 않았다. `h0001_r03_spec_v4` canonical SHA-256:
  `8649baf0ff14e59a9e7f93ec50589299e1e38324247da7463c27c7456aa9672d`.
- 검증: 전체 **723 passed (155.86s)**, 실패·skip·pytest warning 없음.
  신규 extended **59개**, 기존 RTH/V2-A/B **130개** 및 C0 **280개** 포함.
  기존 RTH 테스트 파일은 byte-identical이다. `git diff --check`, CLI `--help`,
  extended SQLite roundtrip·run metadata·동일 replay hash도 통과했다.
- H0001 on_event/regime/relative-selection/threshold/swing-selection/execution/fill/
  portfolio/provider/수익성 backtest는 구현하지 않았으며 시장 데이터 수집도 하지 않았다.
  상세 계약과 한계: [extended-session 구현 기록](docs/V2_EXTENDED_SESSION_IMPLEMENTATION.md),
  [C0 명세](docs/V2_C0_H0001_SPECIFICATION.md),
  [연구 아키텍처](docs/V2_STRATEGY_RESEARCH_ARCHITECTURE.md).

---

# Richping v2 상태 · 2026-09-29 V2-C0 lifecycle re-audit remediation

**state-machine liveness finding 수정 완료. H0001은 DRAFT / BLOCKED_ON_DECISIONS다.**

- `v2-c0-h0001-spec-contract` / `03438243b0ce35a456bf350adcdbdf6da5416c26`에서
  INACTIVE_SIGNAL → DAILY_LONG_ALLOWED / DISABLED 복귀 전이를 추가했다.
  INACTIVE_SIGNAL은 현재 active long signal 부재이며 execution position state가 아니다.
- 분기·우선순위·reset은 기존 H1-DAILY-LONG, H1-DAILY-BLOCKER,
  H1-STATE-TRANSITIONS 계약을 재사용한다. 새 전이는 기존 unresolved 계약의 명시적
  reference이며 새 threshold·매매 규칙을 확정하지 않는다. 프로필은 `h0001_r03_spec_v3`다.
- 두 exit 경로 이후 새 causal Daily permission → setup → entry 조건을 다시 거쳐
  ENTRY_READY/ACTIVE_SIGNAL에 도달할 수 있다. 모든 nonterminal state의 reachability,
  liveness, dead-end/닫힌 순환 및 직접·간접 재활성화 우회를 graph-level에서 검증한다.
- 기존 **75 decisions / 107 unresolved paths**와 각 내용이 동일하다. r03 raw byte
  SHA-256은 `abdd4f10d127ee7614a4eead734d1bfbf7dc1897ec368f8a3b70a1645e2552fc`로 불변이다.
  execution/performance blocker의 C1 재유입을 차단하며 V2-A/B 코드는 변경하지 않았다.
- 신규 회귀 **51개**, C0 **280개** 포함 전체 **664 passed (136.16s)**.
  실패·skip·pytest warning 없음. CLI `--help`, `git diff --check` 통과.
- 새 draft hash: `2f92d6b4b930d365f897e23e41ef0785822a3d6e1fe270a9eb89fb4297686ff4`.
  C1 plugin/guard 구현 및 수익성 검증은 수행하지 않았다. main 및 기존 dirty 작업 보존,
  main merge 없음. 상세: [V2-C0 명세](docs/V2_C0_H0001_SPECIFICATION.md).

---

# Richping v2 상태 · 2026-09-29 V2-C0 freeze-semantics audit remediation

**두 correctness finding 수정 완료. H0001은 DRAFT / BLOCKED_ON_DECISIONS이며 C1 plugin은 미구현이다.**

- 같은 `v2-c0-h0001-spec-contract` worktree에서 `e2bce5b0dd0bd49a7b132f3aced2a3fcaadbfb0f`를
  기준으로 수정했다. main과 기존 dirty 작업은 보존했다.
- FROZEN은 구조적 신호 계약 동결이다. 별도 `require_c1_ready()`가 status/C1 unknown,
  transition 의존성, `v2_ab_c1_signal_v1` capability 및 선택한 feature convention/version을
  검증한다. 미래 capability 계약은 FROZEN일 수 있지만 현재 C1 시작은 차단된다.
  plugin export와 profitability/historical-reproduction gate도 C1 readiness를 먼저 요구한다.
- strategy는 causal signal state + Intent emission을 소유한다. `POSITION_OPEN`/`FLAT`을
  `ACTIVE_SIGNAL`/`INACTIVE_SIGNAL`로 바꾸고 진입·추가·청산 전이의 fill/sizing/exposure/order
  의존성을 제거했다. 실제 order/fill/position/capital은 미래 execution/portfolio 책임이다.
  transition conditions와 signal rule은 여전히 미결정이며 임의 trading rule을 추가하지 않았다.
- 원본 r03 byte와 V2-A/B 구현·테스트는 그대로다. r04는 없다. 필수 결정은 여전히
  **75개 = C1 51 + performance 17 + optional 7**, unresolved paths **107개**다.
  H0001 전략값·threshold·Daily regime·relative method·swing winner를 선택하지 않았다.
- H0001 specification profile만 `h0001_r03_spec_v2`로 올려 signal boundary 변경을 표시했다.
  새 draft hash: `28e0563158e09df737034750cbe6dfec6764869e0ebb6ceb75037280a4ffa1e5`.
  PyYAML은 모든 specification API의 `[research]` 전제로 문서/테스트에 명시했고 production
  dependency는 늘리지 않았다.
- 신규 회귀 **70개**, 전체 **613 passed (118.15s)**: C0 229개 및 기존 V2-A/B 포함.
  실패·skip·pytest warning 없음. CLI `--help`, `git diff --check` 통과.
- backtest/provider/execution/portfolio/on_event는 구현하지 않았다. main merge 없음.
  상세 계약과 검증: [V2-C0 명세](docs/V2_C0_H0001_SPECIFICATION.md).

---

# Richping v2 상태 · 2026-09-27 V2-C0 executable-spec contract

**V2-C0 infrastructure: COMPLETE. H0001 executable spec: DRAFT / BLOCKED_ON_DECISIONS.**
**H0001 profitability: NOT TESTED. V2-C1 plugin은 미구현이며 아직 시작할 수 없다.**

- clean `v2-b-reusable-features`와 감사 base
  `887810629a46912bd7cd4dcfca2709b1b33d7f74`를 확인한 뒤,
  `v2-c0-h0001-spec-contract` / `var/worktrees/v2-c0`를 분리 생성했다.
  시작 기본 작업 트리는 `main@94cc2d292a83714aadaa4033ddfd5a5cfca39125`였고,
  기존 cli/maturity/paper/pipeline 수정과 미추적 R1-Q 테스트를 그대로 보존했다.
- generic immutable specification, strict YAML/JSON parser, canonical SHA-256,
  DRAFT/FROZEN 검증, H0001-r03 필수 inventory와 별도 executable-spec draft를 구현했다.
  필드 누락·unknown enum·잘못된 타입·중복 키·blocker 분류 하향·중첩 unknown 은폐는 거부한다.
  parser용 PyYAML을 research/dev optional dependency에 명시했다.
- 결정 **75개**: C1 implementation blocker **51개**, performance experiment blocker **17개**,
  optional future extension **7개**. parameter/transition **107개 경로**가 UNRESOLVED다.
  C1 blocker가 남으면 FROZEN 불가. 수익률 실험은 performance blocker 해소와 chart parity도 필요하다.
  FROZEN은 구조적 신호 계약 동결이며, 사용자 결정·구현 정확성·수익성 증명이 아니다.
- 현재 15m RTH·first-observation EMA는 엔진 capability다. 전략의 session/EMA 결정을 대신하지 않는다.
  observed chart/provider·1H boundary·EMA/history/warmup은 미확정, parity는 UNVERIFIED다.
  향후 engine-side 규약을 동결한 C1 synthetic 테스트와 historical reproduction의 gate를 분리했다.
- r03 원본 byte hash는 기준 작업 트리와 동일하다. 새 r04를 만들지 않았다.
  V2-A/B causal·atomic-known-at·readiness·continuity·provenance 코드와 기존 테스트는 변경하지 않았다.
  generic replay/features는 H0001 모듈을 import하지 않는다. 기존 recursive V2 code hash에는
  추가 source가 자연스럽게 반영되며 과거 증거를 재작성하지 않는다.
- 최종 신규 C0 **159 passed (19.11s)**, V2 전체 **289 passed (39.27s)**,
  전체 pytest **543 passed (108.38s)**. 최종 실행 실패·skip·pytest warning 없음.
  `git diff --check` 및 staged diff check 통과. 테스트 중 ID 편집이 겹친 이전 실행은
  폐기하고 코드/명세를 고정한 새 프로세스에서 최종 결과를 확인했다.
- H0001 strategy/on_event/Intent, backtest, parameter optimization, provider 선정,
  execution simulator, portfolio, production/paper 변경은 수행하지 않았다. main merge 없음.
- Spec hash: `5e15b84787a42998ddeed7b183d7e2b5931b87f020840699803dceb56ad3dde3`.
  다음 단계는 사용자의 결정과 freeze 검토다. 이후 research-capture revision 필요성을 별도 판단한다.
  전체 결정 질문·후보·분류·feature mapping은
  [V2-C0 명세와 decision matrix](docs/V2_C0_H0001_SPECIFICATION.md)를 따른다.

---

# Richping v2 상태 · 2026-09-27 V2-B continuity audit remediation

**내부 expected timeframe bar 결손을 fail-closed하도록 수정 완료.**

- `v2-b-reusable-features`의 감사 HEAD
  `97d847ef2ecfb97199f6ca8637d4c0bb8076ef82`에서 수정했다.
- 공통 `xnys_completed_grid_v1` 계약으로 15m·개장 기준 1H·Daily의 XNYS 연속성을
  검사한다. 정상 overnight·주말·휴일·DST·early close는 연결하며, 실제 누락 slot이나
  누락 거래일은 `NOT_READY / noncontiguous_history`와 빈 값으로 반환한다.
- EMA/MACD/ATR은 전체 계산 이력, TR은 마지막 두 입력, 상대 변환과 swing은 해당
  window를 검사한다. 첫 visible bar 이전이나 마지막 visible bar 이후의 봉은 요구하지 않는다.
  MACD scalar는 첫 gap 이후 모든 field를 unavailable로 유지하므로 percentile/z-score의
  window가 gap 이후로 이동해도 왜곡된 누적 값을 사용하지 않는다.
- raw/external ScalarSeries의 timestamp gap을 상대 변환이 직접 검사한다.
  지연 봉 도착 후 새 as-of에서 재계산할 수 있고 과거 FeatureResult/ScalarSeries/context는
  불변이다. continuity 정책을 specification hash에 포함하고 기존 저장 증거는 변경하지 않는다.
- V2 전체 **130 passed (20.08s)**, 전체 pytest **384 passed (91.74s)**.
  신규 회귀 테스트 33개, 기존 prefix-invariance·atomic-known-at·swing 테스트 모두 통과.
  실패·skip·pytest warning 없음. `git diff --check` 통과.
- H0001·threshold·provider·execution·legacy 운영 코드는 변경하지 않았다.
  main의 기존 미커밋 변경을 보존했다. 수익성 증거를 생성한 작업은 아니다.
- 상세 계약은 [V2-B 구현 기록](docs/V2_B_IMPLEMENTATION.md)을 따른다.
  아래 최초 V2-B 완료 기록은 역사 기록이다.

---

# Richping v2 상태 · 2026-09-27 V2-B reusable features

**V2-B: COMPLETE — 전략 중립적인 reusable feature services.**

- 감사 기준 `df2e34b42b954ad73cc89c039318059d058214e9`와 clean V2-A 작업 트리를
  확인하고, 정확히 그 commit에서 `v2-b-reusable-features` / `var/worktrees/v2-b`를 만들었다.
  최초 기본 작업 트리는 `main / 94cc2d292a83714aadaa4033ddfd5a5cfca39125`이며
  기존 cli/maturity/paper/pipeline 수정과 미추적 `tests/test_r1b_q_regressions.py`를 보존했다.
- 불변 spec/result/scalar series, first-observation recursive EMA/MACD,
  True Range/SMA-seeded Wilder ATR, current-inclusive midrank percentile,
  population/sample z-score, positive causal scale normalization을 구현했다.
  span/period/window/min_history/method/seed를 versioned specification hash로 추적한다.
- strict L-left/R-right completed-bar fractal과 별도 HH/LH/HL/LL classifier를 추가했다.
  동일 가격은 EQH/EQL, 최초 swing은 null 분류다. pivot_at과 실제 confirmed_at을 구분하고,
  결측 grid를 건너뛰거나 미완성·미래 봉으로 swing을 확정하지 않는다.
- feature 입력은 detached causal context 또는 immutable scalar series다.
  dataset/store/loader/cache 의존성이 없다. atomic_known_at_batch_v1, 1H 개장 기준 집계,
  기존 V2-A 실행 코드·47개 테스트·isolated DB schema·legacy 실행 코드는 변경하지 않았다.
  READY/NOT_READY/UNDEFINED를 구분하며 warmup·zero variance·zero scale을 0으로 숨기지 않는다.
- 신규 V2-B **50 passed (5.00s)**, V2 전체 **97 passed (5.52s)**,
  전체 pytest **351 passed (77.60s)**. 실패·skip·warning 없음. `git diff --check` 통과.
  EMA/MACD/TR/ATR/percentile/z-score/normalization/structure 손계산,
  100봉 중 후반 50봉 극단값 변경에 대한 모든 이전 feature 결과 불변성,
  지연 봉·partial 1H/Daily·ticker 순서 독립성·feature 저장 멱등성·recursive code hash를 검증했다.
- H0001-r03 YAML은 변경하지 않았고 여전히 **DRAFT**다. 전략 규칙·execution/provider·실데이터
  backtest·optimization·walk-forward·production/paper 변경 없음. **수익성은 아직 측정하지 않았다.**
- V2-C 전 blocker: 관찰한 chart/provider의 EMA seed/history/warmup 및 1H candle boundary를
  확인해야 한다. XNYS 09:30–10:30 ... 15:30–16:00 convention은 그대로다.
  H0001의 relative transform과 실제 swing detector/spec도 별도로 확정해야 한다.
  reference fractal이나 API 예시 숫자를 H0001의 확정 사양으로 간주하지 않는다.
- 상세 수식·readiness·causal/provenance 계약·한계·미구현 범위는
  [V2-B 구현 기록](docs/V2_B_IMPLEMENTATION.md)을 따른다. 아래 V2-A 기록은 역사 기록이다.

---

# Richping v2 상태 · 2026-09-27 V2-A availability audit remediation

**동일 known_at의 atomic availability batch 수정 완료.**

- 같은 known_at의 모든 base bar와 그 시점에 완료되는 higher-timeframe bar를
  함께 공개한 뒤 strategy callback을 한 번 실행한다. Clock advance·event·trace·checkpoint는
  batch당 한 번이다. 지연된 과거 bar와 현재 bar도 known_at이 같으면 같은 batch에 포함한다.
- 종목 알파벳 순서는 canonical serialization에만 사용한다. 입력의 동일 end_at tie 순서는
  정규화하며 시간 역전·duplicate 거부는 유지한다. `ReplayEvent.base_bars`에 전체 batch를 기록한다.
- Run provenance에 `atomic_known_at_batch_v1`을 추가했다. 이전 per-bar 증거는 재작성하지 않는다.
  SQLite schema·legacy 운영·H0001·feature 구현은 변경하지 않았다.
- 첫 decision의 ALFA/BETA 동시 공개, ticker relabeling·입력 tie 순서 독립성,
  지연/현재 bar 동시 공개, 두 종목 1H 동시 완료, hidden-future, batch hash·저장 멱등성을 검증했다.
  V2 테스트 **47 passed (2.71s)**, 전체 **301 passed (74.45s)**. 실패·skip·warning 없음.
- `v2-a-causal-replay-foundation`에서 수정했다. 아래 최초 V2-A 결과는 역사 기록이다.

---

# Richping v2 상태 · 2026-09-27 V2-A

**V2-A: COMPLETE — contracts and causal replay skeleton.**

- `research-capture-contract`의 `f1156b7` 설계를 기반으로 별도 브랜치
  `v2-a-causal-replay-foundation`과 `var/worktrees/v2-a` 작업 트리에서 구현했다.
  시작 main HEAD는 `94cc2d292a83714aadaa4033ddfd5a5cfca39125`였다.
  기존 cli/maturity/paper/pipeline 변경과 미추적 R1-Q 테스트는 원래 작업 트리에 보존했다.
- `richping.research_v2`에 불변 bar/dataset/state/intent/fill/event 계약, 가용시각 clock,
  XNYS RTH 완료 봉 집계, generic callback, trace/checkpoint 및 격리 SQLite를 추가했다.
  기존 core의 canonical/digest/aware UTC/calendar helper를 재사용하고 legacy 실행 코드는 변경하지 않았다.
- Synthetic 15m만 지원한다. 1H는 개장 기준으로 시작하고 마지막 짧은 버킷은 공식 폐장에 완료한다.
  Daily는 모든 15m 구성 bar가 실제로 알려진 뒤에만 완료한다. 지연·결측은 보정하지 않으며
  callback은 full dataset 참조가 없는 불변 prefix만 받는다.
- 신규 테스트 **41 passed (2.61s)**. V2-A 작업 트리 전체 **295 passed (77.03s)**,
  원래 dirty 작업 트리 전체 **266 passed (76.40s)**. 실패/skip 없음.
  원래 작업 트리에만 기존 pytest cache WinError 5 warning 1건이 있다.
  구현 전 설계 브랜치 baseline은 **254 passed (77.25s)**였다.
- H0001-r03은 DRAFT로 유지한다. MACD·매매 규칙·수익성 backtest·provider·execution·paper 변경 없음.
  state 저장/복원은 지원하나 checkpoint부터 엔진을 자동 재개하는 기능은 후속 범위다.
  API는 신뢰된 Python plugin용이며 OS 보안 sandbox는 아니다.
- 상세 계약·재사용 조사·격리 결정·테스트·후속 범위는
  [V2-A 구현 기록](docs/V2_A_IMPLEMENTATION.md)을 참조한다. 다음 개발 단계는 V2-B의 범용 feature 서비스다.

---

# Richping 현재 상태 · 2026-09-21 R1-B

**R1-B 최소 paper 원장·maturity follow-up 구현 및 격리 연구 replay 완료. 실제 미래 paper 수익성은 증거 대기.**

- `richping.maturity`/`richping.paper`와 CLI `maturity-followup`, `paper-init`, `paper-advance`, `paper-report`를 구현했다. 운영 DB와 분리된 append-only SQLite가 manifest/source/follow-up/event/일별 NAV를 보존하며, fixed replay와 rolling 운영-policy replay 및 실제 미래 `FORWARD_PAPER` 등록을 구분한다. 자동 주문은 없다.
- 가상 $100,000, lot $10,000, 총 신규 노출 50%, 최대 5종목, 정수주, next-open→5번째 close, side당 commission/slippage 5/5bps를 구현했다. same-ticker 재추천, 중첩/현금 부족, open 진입→close 청산→mark 순서, 갭/미체결, 실현·미실현 P&L과 MDD를 처리한다. 배당·split·Capital Gains·결측/상폐를 0 또는 확정 NAV로 바꾸지 않고 신규 진입을 중단한다.
- 실제 원본 OOS는 **157=122 COMPLETE+23 PENDING+12 UNRESOLVED**를 재현했고 후속은 **145+0+12**, SPY paired 47/62→56/62다. 원본 DB/JSON은 보존했다.
- Frozen paper는 추천 157/fills 5, 첫 보유 배당 권리 미해결로 known cash $101,222.33이나 NAV/MDD는 미확정이다. 격리 rolling 운영-policy replay는 315 sessions, 추천 11/fills 5, 확정 NAV **$99,479.62**, 계좌 MDD **−0.72084%**다. 둘은 calibration/위험 경로가 달라 직접 Alpha 비교가 아니다.
- 동일 기간·자본 SPY buy-and-hold와 동일 lot·현금대기 SPY 대체 계좌를 분리했다. 배당 총수익 회계가 검증되지 않아 두 비교 모두 `COMPARISON_INCOMPLETE`; price-only 진단으로 SPY 우위를 주장하지 않는다.
- 현재 working-tree build는 model `baseline-v1-2bf86875d8007b20`, code hash `0119d7203ff2b931da67b8d51740a41450a385d252e25ad8ae9be7daa9b5b4a2`, risk cohort `1c721fb12c067d54c40e1b54a2f00fe88ad739f5717afec0c761e0987d4cf0ca`다. R1 모듈/CLI 추가로 package model ID는 달라졌으나 투자 판단 계약 기반 risk cohort는 유지된다. 이 build로 운영 daily를 실행하거나 운영 DB의 model/risk_state를 초기화하지 않았고 operational replay는 R1 격리 DB에만 썼다.
- 손계산 cash/P&L/MDD·갭/정수주·재추천·미해결 사건·미래 누출·멱등성·원본 보존·2배 비용 stress·SPY 배정 부족·source 충돌·forward-only 등록을 검증했다. 전체 `.venv\Scripts\python -m pytest`는 **254 passed / 0 failed / 0 skipped / 1 warning / 76.22s**. warning은 기존 pytest cache WinError 5다. CLI help와 실제 R1 보고 생성도 통과했고, 같은 입력 재실행 뒤 manifest ID와 ledger 행 수가 유지됐다.
- **개발 완료 / 실제 forward paper 시작 미등록 / 수익성·Alpha 미래 증거 대기. Alpha: INSUFFICIENT EVIDENCE.** 핵심 회계 변경의 다음 요청은 **Q**다.

---

# Richping 상태 기록 · 2026-09-21 R1-A

**R1-A 읽기 전용 baseline 분석·최소 paper 구현 계약 작성 완료. 아래의 R1-B 대기 표기는 당시 상태다.**

- [Baseline 증거 점검](docs/R1_BASELINE_REVIEW.md): 로컬 coverage/validation/failure-analysis 원문과 해시를 확인했다. frozen OOS의 전체 선택 157건은 **122 COMPLETE+23 PENDING+12 UNRESOLVED**이며 적격 122건의 session/ticker/net_return도 원문 간 일치한다. coverage 265건/142일과 별개다.
- 같은 원본 dataset에서 저장 선택의 관측 입력을 복원해 원래 cutoff의 157개 상태·사유와 저장 수익을 대조했다. cutoff만 후속 만기로 옮긴 읽기 전용 진단은 **145 COMPLETE+0 PENDING+12 배당 UNRESOLVED**, SPY paired **56/62일**이다. 원본 frozen **47/62일**과 구분하며 원본 OOS/DB를 재작성하지 않았다. fresh 성과나 새 확인 OOS가 아니다.
- [R1 구현 명세](docs/R1_IMPLEMENTATION.md): maturity 원본/후속 view, 가상 $100,000·추천당 최대 $10,000·총 신규 노출 50%·5종목, next-open→5번째 session close, 비용/정수주/현금/재추천/갭/미체결/사건·미확정 NAV, 두 SPY 비교, 재사용·별도 저장·손계산 fixture·완료/보류 기준을 고정했다. 숫자는 연구 가정이며 사용자 실전 예산이 아니다.
- 운영 읽기 전용 확인: datasets 4/bars 40,100, shadow 성공 2 sessions, 추천/outcome 0/0, 마지막 실제 model `baseline-v1-1c499becc6025728`, risk_state NORMAL 1건. 이번에 실제 daily나 예약 trigger/다일 안정성을 재검증하지 않았다. M2-1B `fresh.db`는 runs 0인 연구 dataset이다.
- 시작 HEAD `fc6a9af93ff921c07f0182cab23b7f882949b155`; 기존 dirty `richping/pipeline.py`, `tests/test_operations.py`를 보존했다. 현재 working-tree model은 `baseline-v1-1553f44240af729f`이며 아래 R0 당시 build와 다르다. 실행 코드는 수정하지 않았다. 문서 링크/diff·분모·fixture 산술·원본 해시를 검증했으며 전체 pytest를 이번에 실행한 것으로 표기하지 않는다.
- **계약 작성 완료 / paper 개발 미완료 / 운영 기록 확인·새 운영 검증 없음 / 미래 증거 대기. Alpha: INSUFFICIENT EVIDENCE.** 다음 요청은 **R1-B**다. R1-B 뒤 핵심 회계 검수 Q로 인계한다.

---

# Richping 상태 기록 · 2026-09-20 방향 재정립

**현재 작업: R0-B 실제 forward 1회와 Windows 예약 등록 확인 완료. 예약 trigger 실행과 다일 안정성은 관찰 대기.**

- R0-B 사후 검증의 risk 연속성 결함을 국소 수정했다. 전체 package `model_id`와 model별 forward 집계는 유지하고, config와 투자 판단 코드 모듈 및 signal/score/selection/feature/calibration/outcome/evaluation/risk 계약을 묶은 `richping_risk_cohort_v1`을 새 run body에 기록한다. 정확히 검증된 동일 cohort만 PAUSED·REDUCED_EXPOSURE·적격 warmup/recent-30 표본을 공유하며 동일 session/ticker/horizon은 중복 제거한다. legacy 성과는 추정 병합하지 않고 legacy PAUSED만 보수적으로 유지한다. 기존 운영 DB와 산출물은 이번 수정에서 재작성하지 않았다.
- R0-B는 2026-09-20 22:38 Asia/Seoul에 2026-09-18 신호일의 next-open 이전 창에서 실제 wrapper를 실행했다. 첫 sandbox 실행의 수집 `ConnectionError`/exit 1과 후속 정상 adapter 재시도/exit 0을 모두 보존했다. 성공 결과는 `NORMAL_NO_TRADE`(`insufficient_evidence_or_edge`), freshness `CURRENT`, 새 forward 관측 1건이며 수동 실행 시각은 계획 08:00 대비 `LATE`로 표시된다.
- 정상 sync는 운영 DB에 새 immutable dataset `cf504cff91aa9d220d720660f80b4708d210b793cc16f34120bcefabaceb755f`를 추가했다. 2022-09-19~2026-09-18, 10,040 bars, `yfinance-1.7.0`, capture `2026-09-20T13:38:46.924059+00:00`, 배당 event/단위 증거 117/117건이다. 기존 dataset 3개와 기존 shadow run의 보존 및 모든 dataset content hash를 재검증했다.

- R0-A는 immutable run body와 기존 DB schema를 바꾸지 않는 `richping.operations` 파생 계층을 추가했다. `daily`는 수집 전에 attempt JSON을 만들고 성공·정상 NO TRADE·수집 실패·stale·휴일/중복·outcome 분모를 JSON/Markdown에 구분한다. 기본 운영 출력은 `var/operations`, custom DB와 수동 scan 출력은 `var/research`로 분리된다.
- 보고서는 XNYS next-open 유효시각, dataset session/capture, model/config/code/data ID, feature/outcome/evaluation 계약, 후보 score/기여요인/ATR 참고값, calibration 표본·날짜·CI, 실제 제외 사유, COMPLETE/PENDING/UNRESOLVED와 holding eligible/excluded를 표시한다. SYNTHETIC/RESEARCH/FRESH_SHADOW를 분리하며 Alpha는 **INSUFFICIENT EVIDENCE**, portfolio return은 N/A다.
- 실행 attempt는 runs 생성 전 실패도 남긴다. 실패 보고서는 과거 성공을 `prior_success_reference`로만 표시한다. versioned JSON/Markdown이 모두 완성된 뒤 `latest.json`을 원자 교체하므로 실패한 세대를 최신으로 읽지 않는다. 기존 `var/daily-report.json`은 덮지 않는다.
- read-only forward summary는 model/mode/source/quality/outcome/evaluation 계약별 저장 run·추천·outcome을 집계한다. 동일 recommendation/horizon의 여러 평가 vintage는 최신 저장 dataset rowid 하나만 사용하며 조회 자체는 outcome을 생성하지 않는다.
- 마지막 실제 R0-B 운영 model은 `baseline-v1-1c499becc6025728`, code hash는 `8748263a3e98ecaed95611eef2ced7c4b0631ef2ab83296758e76855840efa8e`다. risk cohort 수정 후 현재 미실행 build는 `baseline-v1-5e5dc98a78907bee`, code hash `9702e075182f2fa93d844616367474db65b4ca5ac83b70ca9e87dcf1d856acad`, 기본 config의 cohort ID `70080b94...4323b1`이다. 이번에는 실제 daily/scan을 실행하지 않았으므로 운영 DB에는 새 model/run/cohort가 아직 없다. pre-R0 frozen synthetic 입력의 ticker/score/calibration/참고가격 동일성은 golden test로 유지했다. 계약 필드가 없는 과거 run은 현재 v3나 risk cohort로 소급 표시하지 않는다.
- 실제 운영 DB는 datasets 4/bars 40,100, shadow SUCCEEDED 2 sessions(2026-09-14, 2026-09-18), 추천/outcome 0/0이다. R0-B 실행 전 `risk_state`는 없었고 실행 후 새 model의 `NORMAL/risk_sample_warmup` 상태 1건이다. 두 model의 config payload가 같고 이전 PAUSED가 없음을 확인했으므로 보고 코드 변경을 이용한 latch 우회는 없다.
- `\Richping Daily`를 현재 사용자 `lifes`, `Interactive`/`Limited`, 매일 Asia/Seoul 08:00에 등록했다. action은 `powershell.exe -NoProfile -File "C:\richping\scripts\daily.ps1"`, working directory는 `C:\richping`, 동시 인스턴스는 `IgnoreNew`다. 동일 역할 task는 이 1건뿐이다. 상태 `Ready`, 다음 실행 2026-09-21 08:00, `LastTaskResult=267011`로 예약 trigger 자체는 아직 실행 전이다. WakeToRun은 false이며 PC가 종료·절전 또는 사용자가 로그아웃한 동안의 실행은 보장하지 않는다.
- 보존 기준 `var/daily-report.json` SHA-256은 실행 전후 `5DD67D2A...F6CDFE`로 동일하다. 운영 DB SHA-256은 새 immutable 행 추가로 `2FAF7497...54FBE1`에서 `72C231CA...CDDA3E`로 바뀌었고 integrity는 `ok`다. 상세 manifest는 `var/operations/r0-b-start-verification.json`, 사람이 읽는 요약은 같은 이름의 `.md`, 실제 보고 예시는 `var/operations/latest.json`과 그 `artifacts.markdown`에 있다.
- 개발 인수 테스트는 성공/후보/정상 NO TRADE/수집 전 실패/stale/휴일·중복/late guard/PENDING 만기/원자 교체 실패/read-only 조회/risk latch·REDUCED_EXPOSURE·warmup·최근 30개 중복 제거·판단 golden·legacy 계약 비소급을 포함한다. 전체 `.venv\Scripts\python -m pytest`는 **245 passed / 0 failed / 0 skipped / 1 warning / 67.10s**. warning은 기존 `var/.pytest_cache` WinError 5다. CLI `--help`, 실제 DB read-only `report`, `git diff --check`도 통과했다.
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
