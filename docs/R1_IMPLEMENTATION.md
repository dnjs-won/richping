# R1 구현 명세 — maturity follow-up / 최소 paper 원장

2026-09-21, R1-A 계약 작성 / R1-B 구현 완료. 상위 계약은 [PROJECT_SPEC](../PROJECT_SPEC.md), [DESIGN](DESIGN.md), 순서는 [ROADMAP](../ROADMAP.md)이다. 현재 근거와 읽기 전용 검증은 [R1_BASELINE_REVIEW](R1_BASELINE_REVIEW.md)에 있다. 이 문서는 기존 feature, v3 outcome, 평가 정책, signal/score/calibration/threshold/universe/top-k를 바꾸지 않는 **추가 계약**이다. 자동 주문·승격·최적화는 없다.

## 1. 고정할 범위와 가정

`richping_maturity_followup_v1`, `richping_paper_ledger_v1`을 별도 버전으로 도입한다. 아래 숫자는 단순하고 손계산 가능한 **연구용 가상 기준값**이며 사용자 자본·실전 예산·허용손실이 아니다. 이번에 읽은 M2-1B OOS는 이미 소비한 탐색 자료다. 이 가정으로 수익을 보고 다시 sizing/비용/한도를 조정하지 않는다. 변경이 필요하면 이유와 새 계약/별도 cohort를 먼저 등록한다.

| 항목 | 기본값 / 의미 |
|---|---|
| 초기 자본 | USD 100,000, 외부 입출금 없음, long-only, 차입·레버리지·이자·세금·FX 없음 |
| 배정 | 추천당 최대 초기 자본의 10% = $10,000, 복리 증액 없음; 추가로 직전 확정 NAV의 10% 이하 |
| 종목 / 총 노출 | 신규 진입 시 종목 10%, 총 50% 이하(직전 확정 NAV 기준), 최대 5개 동시 보유; 한 종목 한 lot |
| 보유 | next-open 진입 session을 1일로 세어 XNYS 5번째 session close 청산 |
| 비용 | 매수·매도 각각 원본 거래대금의 commission 5bps + slippage 5bps를 현금 차감; 2배 stress는 각각 10bps |
| 가격 / 수량 | 승인된 원본 가격 단위, 정수 주식, 소수 주식 없음; 가격 문자열을 Decimal로 읽고 각 비용은 USD cent ROUND_HALF_UP |
| 현금 가정 | 매도 순현금은 그날 close 처리 뒤 반영, 다음 session open부터 사용. 결제 지연을 생략한 가상 회계이며 실계좌 buying power를 주장하지 않음 |

총 노출은 **신규 진입 허용 한도**다. 보유 중 가격 변동으로 넘으면 breach를 보고하고 새 진입을 막되 강제 매도로 5-session 계약을 바꾸지 않는다. 초기 자본 기준 배정은 추정 edge/ATR/승률에 비례하지 않는다. stop/target은 접촉 진단만 유지하고 체결 가격 또는 조기 청산으로 쓰지 않는다.

## 2. 원본 보존과 maturity follow-up

1. 입력을 원본 파일 SHA-256, dataset/model/config/code ID, fold/phase, 원래 cutoff, outcome/evaluation 버전으로 고정한다. 원본 DB는 `Store(..., read_only=True)`로 연다. 원본 `validate()`/`track()`을 운영 DB에 호출해서 후속 view를 만들지 않는다.
2. frozen selected universe 전부를 보존한다. 이 artifact에서는 validation의 적격 `oos_predictions` 122개만 읽으면 안 된다. failure-analysis의 `oos_selected_records` 157개와 fold 집계를 결합한다. key는 `(source_hash, fold, phase, session, ticker, horizon)`이며 다른 horizon/vintage를 독립 표본으로 늘리지 않는다.
3. 이 역사 자료에는 완전한 immutable snapshot/rank가 없다. 관측 전용 입력은 저장 features의 `price`, `atr`에서 entry=price, stop=price−2ATR, target=price+4ATR, 원본 cost=.002/horizon=5/v3로 복원한다. 같은 날짜 순위는 저장 score 내림차순/ticker 오름차순으로 복원하고 `DERIVED_RESEARCH_INPUT` 표시한다. 추천을 재선택하거나 calibration을 재학습하지 않는다. DB 추천 ID/당시 실제 발행으로 가장하지 않는다.
4. 복원 입력으로 **원래 fold 종료 cutoff의 157개 상태·사유, 122개 저장 net_return**과 정확히 대조한 뒤만 사용한다. 불일치/필드 누락은 `SOURCE_RECONSTRUCTION_UNVERIFIED`로 보존하고 관련 후속·paper 경로를 중단한다. 요약만 있거나 artifact가 없으면 `재현 미확인`; 분모/추천을 추정 생성하지 않는다.
5. 같은 선택 입력에 `observe`와 `evaluate_outcome_eligibility`를 적용하되 후속 `as_of`, 평가 dataset ID, 원본/후속 상태·사유를 별도로 저장한다. 기본 비교 vintage는 원본 `7d573d...af2e8`, cutoff는 그 마지막 session close+30분이다. 새 vintage 사용 시 원본도 보존하고 단위/기준 종가 변경은 기존 `price_vintage_changed` 등으로 격리한다. COMPLETE를 재해석해 덮지 않는다.
6. 결과는 원본 157=122+23+12와 후속 157=145+0+12를 병렬 보고한다(현재 자료 확인값; 다른 입력에는 강제하지 않음). 23건의 transition을 모두 출력한다. 진입일 포함 배당 12건을 v3 COMPLETE로 바꾸지 않는다. maturity 자료가 calibration/과거 feature/운영 risk 표본을 다시 쓰지 않는다.
7. SPY는 선택 신호 날짜 전체에 1개씩 같은 horizon/cutoff/v3로 관측한다. attempted, candidate eligible, SPY eligible, both, candidate-only, SPY-only, neither와 각 사유를 보존한다. 날짜 평균 후 동일 paired 날짜로 비교한다. 원본 unpaired 15일, 후속 6일을 버리거나 0% 대입하지 않는다.
8. 선택편향 진단은 전체/적격/누락 분모, fold/ticker/regime 집중, SPY unpaired 사유와 단순 누락 손익의 손익분기 평균을 포함한다. 누락 손익을 실제 추정치로 채우지 않는다. paired-only 분석에는 선택된 표본이라는 한계를 붙인다.

## 3. Paper 입력과 위험 경로 분리

| 계열 | 입력과 시작 | 보고 의미 |
|---|---|---|
| `RESEARCH_FIXED_REPLAY` | 검증된 역사 선택 157개, 원본 OOS 시작 2025-04-21부터 마지막 허용 OOS session(2026-07-22)의 5-session 만기 2026-07-29까지 | frozen 선택에 자본 제약을 적용한 소비된 연구 자료; 122개 승자/적격 결과만으로 구성 금지 |
| `RESEARCH_OPERATIONAL_REPLAY` | 동일 vintage/기간/config, 격리 연구 DB에서 날짜순 `scan`/`track` 및 기존 위험 규칙 실행 | 실제 운영 정책을 재생한 연구. 첫 신호 전 NORMAL/빈 표본이라는 cold-start 가정을 기록; 운영 이력으로 소급 표시 금지 |
| `FORWARD_PAPER` | R1-B 실행 시 등록한 실제 시작시각 이후, next-open 전 존재한 SUCCEEDED shadow snapshot과 사전에 남긴 paper intent | 미래 가상 체결. 이미 지나간 진입을 소급 생성하면 연구로 분리 |

fixed는 frozen calibration이며 scan은 rolling calibration이다. 두 replay 차이를 모두 latch의 효과라고 부르지 않는다. 각 경로의 calibration 방식, 추천·거절 수, 위험 상태/사유, cash idle, 원장 상태를 함께 출력한다. 최소 둘을 계산·대조하되 운영 DB에 쓰지 않는다.

운영 정책은 최근 적격 30건, 음의 expectancy 축소, expectancy ≤−2% 또는 cohort drawdown ≤−15% PAUSED latch, REDUCED의 top-1/강화 edge와 데이터·시장 일시 중단을 그대로 재사용한다. 원장이 위험을 새로 최적화하지 않는다. Forward는 발행된 추천만 소비하며 paper에서 걸러진 추천도 운영 risk의 원래 분모에서 삭제하지 않는다. paper NAV 불확실성 중단은 별도 `paper_admission_block`이며 운영 `risk_state`에 쓰지 않는다.

model ID는 실제 build provenance로 보존한다. Python 추가는 전체 code_hash/model ID를 바꾼다. cohort는 검증된 명시적 동일 계약에 한해 잇고, legacy PAUSED 보수적 유지 규칙을 적용한다. 불명확한 build 변경으로 latch를 초기화하지 않는다. 현재 dirty 파일은 사용자 변경이므로 R1-B 시작 시 다시 대조한다.

## 4. session 순서·수량·체결

1. **의도 등록:** 신호 cutoff 이후 다음 open 전, snapshot/hash/rank, 예정 진입·청산 session, 비용/한도/배정 산식을 고정한다. 재실행은 같은 intent를 재사용한다. 같은 session/ticker/horizon의 여러 build 추천은 명시적 같은 계약일 때 하나만 사용(최초 발행시각, 동률 source ID); 충돌하면 격리한다. 보유 종목 재추천은 `ALREADY_HELD`, 만기를 늘리거나 물타기하지 않는다. 그날 close 청산 예정이어도 open에는 보유로 센다.
2. **개장 처리:** 직전 확정 NAV=N, 직전 확정 종가의 기존 보유 평가액=M으로 동결한 신규 총예산은 `max(0, 0.50*N−M)`이다. 추천 rank, ticker, source key 순서로 `B=min(10000, 0.10*N, 잔여 총예산, 사용 가능 현금)`을 배정한다. 비용 포함 실제 매수 현금 debit만큼 총예산을 차감한다. 미확정 N/보유 가격이면 신규 진입 전부 중단한다. 같은 날 청산대금은 미리 쓰지 않는다.
3. **가상 fill:** 원본 next-open P를 사용해 `q*P + commission(q*P) + slippage(q*P) <= B`를 만족하는 최대 정수 q를 선택한다. q≥1이면 예산에 따른 축소 fill, q=0이면 `INSUFFICIENT_CASH_OR_INTEGER_LOT`. 갭은 P에 그대로 반영하며 전일 entry_reference로 체결하지 않는다. 미래 close/high/low/배당 결과를 보고 주문을 취소·순위 변경하지 않는다. 이는 개장 가격에 따른 예산 주문 시뮬레이션이며 정확한 MOO 정수 주문 체결 보장이 아니다.
4. **데이터/미체결:** 일봉 사후 수집으로 open을 알게 되면 사전 intent에 한해 `effective_at=open`, `recorded_at/known_at=실제 수집 이후`의 가상 fill을 기록한다. 그 가격을 사전 의사결정 정보로 소급하지 않는다. 수집 지연은 `PENDING_DATA`; 만기 cutoff 이후 해당 session 결측/정지/0 volume/비정상 가격은 `UNFILLED_OR_UNKNOWN`이다. 확인된 불가 거래는 `NO_FILL`, 단순 데이터 부재는 체결 여부 불명으로 남겨 확정 전체 성과를 막는다. 다음 관측일 open으로 이동하지 않는다. 나중에 정확한 동일 session 증거가 도착하면 append revision만 허용한다.
5. **청산과 mark:** open 진입 처리 → 예정 5번째 close 청산 → 남은 lot의 그날 close mark → NAV 순서다. 복수 청산은 source key 순서. 유효 close가 있으면 전량 가상 매도하고 비용 차감, 없으면 `EXIT_UNRESOLVED`로 수량·원가를 보존한다. 임의 연장 체결은 없다. close 이후 확정된 현금은 다음 open에서만 사용한다. 종가 진입/당일 open에 미래 청산대금 사용 금지.
6. 거래소 휴일/조기 마감은 `core.next_sessions/open_at/close_at/cutoff_at`을 재사용한다. daily 데이터는 XNYS 해당 session close+30분 및 실제 known_at 이후 보고 가능하다. 불완전 bar로 fill을 확정하지 않는다. 기본 유동성 모형은 가격/양의 volume가 검증되면 전량 가상 fill이며 호가·실제 부분 체결·시장 충격은 미모형화다. 별도 fixture에서 거절/지연을 강제하고 한계를 명시한다.

비용은 각 side 원본 거래대금에 대한 현금 비용이다. 원본 open/close와 slippage 비용을 따로 저장해 이중 차감하지 않는다. 현재 outcome의 `Pclose/Popen−1−.002`는 그대로다. paper 왕복 비용은 매도대금 변동과 cent 반올림 때문에 정확히 같은 수익률이 아니며 이 차이를 보고한다. stress는 동일 입력의 독립 가상 계좌에서 수량·거절까지 재계산하고 base 원장을 변경하지 않는다.

## 5. 원장과 미확정 가치

- 매수 원가 = 원본 매수대금+매수 commission+slippage. 매도 순대금 = 원본 매도대금−매도 commission−slippage. 전량 청산 실현 가격손익 = 매도 순대금−lot 원가. 미실현 가격손익 = 정수 수량×검증된 종가−lot 원가(아직 발생하지 않은 매도비용 미차감). `NAV = 현금 + 검증된 보유 평가액 + 승인된 미수금 − 승인된 부채`. 현금 보존과 `NAV−초기자본 = 누적 실현손익+미실현손익`을 미해결 권리 없는 경우에 대조한다.
- paper는 v3가 COMPLETE인 추천만 사후 매수하는 전략이 아니다. 진입까지 알려진 정보로만 통제하고 보유 중 새 배당/분할/Capital Gains/capture unknown/가격단위 변경을 발견하면 해당 사건을 격리한다. Feature 정규화를 원장 가격·배당 수익에 적용하지 않는다.
- R1 v1은 일반배당·특별배당·ROC·분할·합병·상폐 회수금을 자동 회계 지원하지 않는다. 배당락일을 지급일로 바꾸거나 v2/Adj Close를 총수익으로 쓰지 않는다. 실제 지급/권리·통화·세전/세후·수량 단위가 검증되지 않으면 현금/미수금을 0으로 확정하지 말고 `UNRESOLVED_ENTITLEMENT`를 별도 남긴다. 사건 없음이 완전 capture로 확인된 기간만 확정 price-only NAV이며 총수익과도 일치하는 사건 없는 범위다.
- 배당이 있어도 수량/가격 단위 불변과 정상 거래가격을 독립 확인할 수 있으면 예정 매도를 기록하되 누락 배당 권리는 계속 미해결이다. 분할·합병·단위 불명은 수량을 자동 변환하거나 청산하지 않는다. 상폐/정지/결측은 마지막 가격·0·−100%로 확정하지 않는다. 회수금은 별도 검증 계약 없이는 입금하지 않는다.
- 한 lot이라도 가치/권리/체결 여부가 불명이면 전체 `nav_status=UNRESOLVED`, `NAV/총수익/MDD=null`, 미확정 건수·사유·수량·원가·마지막 확정시점을 표시한다. 알려진 현금, 가격손익, 부분 평가액은 `known_component`로만 보여주며 전체 NAV/하한으로 부르지 않는다. 근거 없는 범위도 만들지 않는다. 원장이 모두 현금이 되어도 미해결 권리는 사라지지 않는다.
- 5-session outcome의 `horizon_not_mature`만으로 일별 NAV를 미확정 처리하지 않는다. 현재 session까지 fill/가격/사건 부재를 검증했으면 만기 전에도 보유 평가가 가능하다. 반대로 COMPLETE outcome 하나가 중간 모든 session NAV를 입증하지는 않는다. 연구의 과거 split-adjusted 가격 단위에서 계산한 정수주는 그 vintage 단위의 가상 수량이며 당시 실주문 수량·매수 가능성의 증거가 아니다. 다른 vintage 단위를 섞지 않는다.
- 미확정 구간에서 신규 진입을 멈추고 독립적으로 가능한 기존 청산/관측은 계속한다. 뒤늦은 증거는 새 as-of view와 revision으로 보존하며 당시 미확정/중단·이미 발행한 fill을 지우지 않는다. 전체 기간의 모든 session NAV가 검증되기 전 전체 기간 MDD는 null; 확정 prefix MDD를 보여줄 때는 기간을 명시한다. MDD는 초기 NAV를 포함한 `min(NAV_t / running_peak_t − 1)`이다. cohort drawdown은 별도 추천 지표로 유지한다.

## 6. SPY 비교 두 종류

두 비교는 별도 계좌로 각각 같은 $100,000·동일 시작/종료 session·비용·현금이자 0·정수주·사건 정책을 쓴다. 기간은 수익 결과와 무관하게 manifest에 먼저 고정한다. 연구 fixed의 시작은 첫 OOS session open, 종료는 마지막 허용 OOS session의 5-session 만기 close다(마지막 실제 추천 날짜로 단축하지 않음). 후보가 늦게 나와도 SPY 시작을 앞뒤로 옮기지 않는다. forward는 등록 뒤 첫 session open부터 공통 보고 cutoff까지이며 진행 중 NAV 비교에는 어느 계좌도 임의 종결 매도비용을 넣지 않는다.

| 비교 | 배분/현금 | 해석 |
|---|---|---|
| SPY buy-and-hold | 시작 open에서 비용 포함 전액으로 최대 정수주, 잔돈 현금; 고정 종료 close에 전량 매도. 후보의 10%/50%/5-lot 제한은 미적용 | 시장 전액 노출의 기회비용; 전략과 노출/현금 비중이 다름 |
| SPY 대체 포트폴리오 | 후보 계좌가 수락한 각 intent의 동일 B·진입/예정 청산 session에 SPY lot 배정, 거절된 추천에는 배정 없음. 미사용 B/정수 잔돈은 현금 대기 | 동일 자본 배정·보유 타이밍 비교; SPY 가격/정수 반올림으로 실제 debit은 다를 수 있음 |

대체 계좌는 source lot별 SPY 중첩 보유를 허용한다(같은 SPY라는 이유로 한 lot만 남기지 않음). 원래 후보의 동일 종목 재추천 거절 마스크/최대 5 lot을 그대로 따른다. B를 정확히 복사하고 수익 차이로 SPY 현금이 부족하면 외부 자금·음수 현금을 만들지 않는다. 가능한 정수주까지만 줄이고 `allocation_shortfall`, 계획 B/실제 debit/정수 잔돈을 기록하며 **동일 배분 비교 불완전**으로 표시한다. 결과를 맞추려고 후보 배정도 줄이지 않는다.

대체 SPY가 가격/사건으로 미해결이면 예정 slot을 유지하고 신규 비교 배정을 중단한다. 후보 청산이 미해결인 slot은 SPY 예정 청산을 따로 관측하되 공통 자금 해제 타이밍 불명과 비교 불완전을 표시한다. 결과를 보고 유리한 청산일을 고르지 않는다. source NO_FILL은 양쪽 미배정, source 체결 여부 불명은 대응 SPY도 pairing 불명이다.

**배당 총수익 회계를 어느 쪽이든 검증할 수 없으면 `COMPARISON_INCOMPLETE`**다. buy-and-hold는 보유 전체 기간, 대체는 각 slot 기간의 사건/capture를 검사한다. 가격만의 차이는 보조 진단으로 표시할 수 있으나 총수익 우위/Alpha로 판단하지 않는다. 동일 기간 전체 NAV 차이를 주표로 두고, 기존 날짜별 matched-SPY 추천 수익은 별도 분모의 지표다. 불완전 날짜를 제거하고 축소 기간을 전체 기간처럼 보고하지 않는다.

## 7. 최소 구현·저장·사용 흐름 (R1-B)

| 재사용 | 추가할 최소 책임 |
|---|---|
| `Store(read_only=True)`, Dataset, `core` calendar/hash/canonical | 원본 읽기/명시적 ID 로딩, UTC effective/known/recorded 시각 |
| `validation.walk_forward_folds`, `Engine`, `observe`, `evaluate_outcome_eligibility`, `metrics/block_ci` | 원본/follow-up 분모·SPY pairing. 기존 `validate`는 적격 122개만 저장하므로 전체 선택 입력 adapter 필요 |
| `pipeline.scan/track`, `risk_contract`, `risk_decision` | 격리 운영-policy replay. 운영 원장·risk와 쓰기 분리 |
| `operations` 보고/원자 저장 패턴, CLI | 작은 `paper` 모듈과 독립 SQLite 저장, JSON+Markdown 비교 카드. 새 framework 불필요 |

최소 SQLite는 `var/research/r1/<analysis_id>/r1.db`, forward는 `var/paper/<portfolio_id>/paper.db` 등 **원본과 다른 경로**다. source/output 실경로가 같으면 거부한다. 운영 DB schema v1은 변경하지 않는다. 다음 5개 테이블이면 충분하며 포지션은 events에서 도출한다.

- `manifests(id PK, kind, schema_version, created_at, payload, input_hashes)`: 기간/계약/모드/가상 자본/seed/원본·build ID/선택·위험 초기상태. immutable.
- `source_items(id PK, manifest_id, source_key UNIQUE within manifest, payload)`: 원본 selected/snapshot/상태/순위·복원 provenance. 실행 여부와 무관하게 전체 분모 보존.
- `followup(id PK, source_item_id, dataset_id, as_of, policy, payload)`: 동일 논리 입력 조합 UNIQUE, 원본/후속/eligibility/pairing, append-only.
- `paper_events(id PK, portfolio_id, event_key UNIQUE within portfolio, effective_at, known_at, recorded_at, payload)`: initial cash, intent/accept/reject, fill/fee, mark, unresolved, revision. key는 논리 경제 사건으로 만들고 관측 vintage 변화로 fill을 두 번 만들지 않는다. 수정은 supersedes 링크의 새 event다.
- `paper_nav(portfolio_id, session, as_of, revision, payload)`: 현금/lot/손익/총·종목 노출/미확정/두 비교, 복합 PK, append-only. 최신 선택은 명시한 as-of 이하 revision만 사용한다.

events/파생 NAV는 한 session transaction으로 저장한다. 중단 후 재시도는 같거나 전무하며 중복 매수/매도/비용 없음. 입력 바뀜은 새 manifest/view이지 원본 UPDATE가 아니다. immutable trigger/FK/논리 unique와 파일 원자 교체 패턴을 재사용한다. 동시 forward writer 1개만 허용한다. 보관된 source/hash 없이 휴대 가능한 결과라고 주장하지 않는다.

CLI 최소 작업은 (1) source 검증 및 `maturity-followup`, (2) `paper-init`으로 계약·기간/모드 등록, (3) `paper-advance --as-of`로 관측 가능한 사건 처리와 다음 open intent 등록, (4) read-only `paper-report`다. 세부 옵션은 기존 CLI 스타일을 따르되 DB/dataset/output을 명시한다. forward 등록 전 과거 intent 소급 금지, 아무 추천이 없으면 현금 계좌와 0건 분모를 정상 출력한다. 기존 daily는 기본 동작을 보존하며 paper는 명시적으로 선택한 계좌에만 연결한다. R1-A는 이 명령을 구현하거나 운영 등록하지 않았다.

## 8. 손계산 fixture와 완료/보류

모두 합성 fixture이며 실제 Alpha 표본이 아니다. 가격만 있는 완전 capture 입력을 사용하고 비용 5+5bps/side를 적용한다.

| fixture | 반드시 확인할 값/행동 |
|---|---|
| 기본 1 lot | 초기 100,000 / B=10,000 / open=100 → 99주, 매수 9,900+4.95+4.95, 현금 90,090.10. close 100/105/95/100/110 → NAV 99,990.10 / 100,485.10 / 99,495.10 / 99,990.10 / 100,969.20. 마지막 매도 비용 각각 5.45, 실현 969.20, 미실현 0 |
| P&L/MDD | day2 미실현 495.10, 현금+99×105=NAV. 초기 NAV 포함 peak, MDD=`99,495.10/100,485.10−1`=−0.9852206944%. 추천 raw 10%/net 9.8%와 paper 계좌 +0.9692%를 혼동하지 않음 |
| 두 SPY | 동일 기간 SPY 200→220, B=10,000 대체는 49주/최종 100,959.42; buy-and-hold는 499주/최종 109,770.42. 동일한 정수 잔돈·비용식 확인; 상대 노출을 숨기지 않음 |
| 갭 / 현금 | ref=100, open=125, B=10,000 → 79주, debit 9,884.88, 현금 90,115.12. 별도 현금=150/B≤150이면 open100에서 1주/debit100.10, 현금49.90; 1주 미만은 거절. 현금/총예산 음수 없음 |
| 중첩 / 재추천 / 순서 | 다섯 종목 보유 후 여섯째 거절, 같은 종목 재추천 거절·기존 만기 불변. 오늘 close 청산할 lot도 오늘 open slot/현금을 점유; 익일에만 재사용 |
| 누락 / 사건 / 시점 | 진입일 결측 체결불명, 청산 close 결측·상폐·분할·배당은 각각 보존; 부분 가격이 있어도 미해결 NAV/MDD null. 미래 수정 vintage·action known_at가 과거 선택/현금을 바꾸지 않음. entry-day 배당도 v3 격리 |
| 멱등 / 보존 | 같은 as-of 2회 및 session transaction 중간 실패 후 재개 결과 동일. 새 vintage로 duplicate fill/독립 outcome 표본 증가 없음. 원본 DB/JSON/snapshot/hash 유지 |
| 위험 / 비교 불완전 | performance PAUSED build 전환에도 우회 없음, 시장/data 일시 중단과 구분. SPY 배당/현금 부족/후보 청산불명 시 전체 우위 판정 불가; fixed와 operational replay 상태·빈도 차이 노출 |

R1-B 개발 완료는 위 fixture와 핵심 불변조건, 관련 회귀/전체 pytest, CLI help, diff 검사를 통과하고 사용자 보고서에 현금·보유·가상 fills·손익·노출·미확정·두 비교를 제공한 상태다. 검증은 별도 DB/output을 쓰며 운영 또는 기본 demo/validation artifact를 덮지 않는다. 역사 source 불일치면 관련 replay만 보류하고 synthetic 회계와 독립적인 forward 기능은 완성한다.

미해결 사건을 명시적으로 막는 원장은 개발 완료 가능하다. **완전한 NAV/총수익 비교·다일 운영 확인·미래 성과 증거·Alpha 판정은 별도**다. 사건 회계는 병목이 확인된 범위의 후속 계약 전까지 보류, Alpha는 INSUFFICIENT EVIDENCE, 자동 승격 없음. R1-B 완료 뒤 핵심 회계 검수 Q로 인계한다.

## 9. R1-B 구현 결과

`richping.maturity`와 `richping.paper`를 추가하고 CLI `maturity-followup`, `paper-init`, `paper-advance`, `paper-report`를 연결했다. maturity는 원본을 read-only로 열고 frozen 선택을 재구성한 뒤 원래 fold cutoff와 후속 cutoff를 별도 저장한다. paper DB에는 위 5개 append-only 테이블과 immutable trigger를 만들며 운영 DB schema/user_version은 변경하지 않는다. 격리 operational replay는 기존 `scan`/`track`/`risk_decision`, fixed follow-up은 기존 `observe`/평가 함수를 사용한다.

실제 `var/research/r1/r1-b-delivery/r1-report.{json,md}`는 frozen 157건의 원본 **122/23/12**, 후속 **145/0/12**, SPY pairing 47/62→56/62를 확인한다. Frozen paper는 첫 보유 배당 미해결 뒤 신규 진입이 중단돼 5 fills, known cash $101,222.33이나 전체 NAV/MDD는 미확정이다. 격리 rolling 운영-policy replay는 315 sessions, 추천 11/fills 5, 확정 최종 NAV $99,479.62, MDD −0.72084%다. 두 결과의 차이는 calibration/위험 경로 전체 차이이며 latch 단독 효과로 해석하지 않는다. 두 SPY 비교는 총수익 배당 회계가 불완전해 `COMPARISON_INCOMPLETE`다. 가격-only SPY 수치는 보조 진단일 뿐 우위 판정이 아니다.

손계산·중첩/재추천·현금/갭·미해결 배당·미래 불변·멱등/원본 보존, 2배 비용 stress, SPY 배정 부족, source 충돌과 forward-only 등록 테스트를 포함해 전체 **254 passed / 0 failed / 0 skipped / 1 warning**이다. warning은 기존 `var/.pytest_cache` WinError 5다. 실제 동일 입력 재실행에서도 두 manifest ID와 `2 manifests / 168 source items / 157 follow-up / 385 events / 1,920 NAV rows`가 그대로였다. 개발 완료와 별개로 forward paper는 `paper-init` 이후 실제 미래 shadow snapshot을 기다리며, 수익성/Alpha는 여전히 미입증이다. 다음 단계는 핵심 회계 **검수 Q**다.
