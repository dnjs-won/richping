# R1-A baseline 증거 점검

2026-09-21 R1-A 시점 결론: **관찰용 baseline 유지 / 과거 성능은 연구 진단 / Alpha INSUFFICIENT EVIDENCE**. 이후 [R1 구현 명세](R1_IMPLEMENTATION.md)에 따라 R1-B paper 코드가 구현됐다. 이 문서의 분석 수치와 R1-A 당시 상태는 보존한다. 새 전략·threshold 변경 또는 실전 자본 결정은 하지 않았다.

## 조사 경계

`user_scripts.md` 공통 규칙과 PROJECT_SPEC/DESIGN/ROADMAP/PROJECT_STATUS/FIRST_MILESTONE을 현재 파일·코드와 대조했다. HEAD=`fc6a9af93ff921c07f0182cab23b7f882949b155`. 시작부터 `richping/pipeline.py`, `tests/test_operations.py`가 dirty였으며 보존했다. 실제 모델 인터페이스의 정확한 제품명/추론 등급은 별도 검증하지 않았으며 문서의 추천 모델 표를 실행 증거로 사용하지 않았다.

JSON 읽기, SHA-256, SQLite `mode=ro/query_only`, `Store(read_only=True)` 및 순수 `observe/evaluate_outcome_eligibility` 호출만 수행했다. sync/daily/scan/validate/demo, 외부 수집, 스케줄러 변경은 실행하지 않았다. 새 확인 OOS를 열지 않았다. 아래는 로컬 artifact 대조와 저장 선택의 관측 재계산이며 전체 신호/calibration validation을 새로 실행한 결과가 아니다. `var/`는 Git 미추적이므로 파일 부재 시 이 문서 수치만으로 재현 완료를 주장할 수 없다.

## 실제 존재하는 증거

| 자료 | 확인한 분모·결과 | 증거의 성격 |
|---|---|---|
| `var/coverage-m2-1b-final.json` | 2022-12-13~2026-09-16, 942 sessions, benchmark 941 supported/1 blocked. 후보 7,536=2,210 raw supported+5,318 excluded+8 benchmark 차단 미평가. 추천 265건/142일, 256 COMPLETE+0 PENDING+9 UNRESOLVED(배당); eligible 256, SPY paired 132/142일 | NORMAL 고정 rolling 연구 replay; frozen fold/운영 latch와 다름 |
| `var/validation-m2-1b.json` | 5 folds×63=315 OOS sessions, 선택 157건/62일, 122 COMPLETE+23 PENDING+12 UNRESOLVED, 적격 122건/52일 | fold별 calibration 동결 연구 OOS; untouched holdout 아님 |
| `var/failure-analysis-m2-1b.json` | `oos_selected_records` 157개 고유 fold/session/ticker, 위 상태 분할과 일치. 적격 122개 session/ticker/net_return가 validation predictions와 모두 일치 | 누락 결과를 포함한 선택 기록; 완전한 추천 snapshot은 아님 |
| `var/richping.db` | datasets 4, bars 40,100, shadow SUCCEEDED 2 sessions(09-14/09-18), recommendations/outcomes 0/0, experiments 1 | 실제 저장 운영 기록. 09-14 legacy와 R0 보고 계약의 09-18 fresh를 구분 |
| `var/m2-1b-fresh.db` | dataset 1, bars 10,020, runs/recommendations/outcomes/experiments 0 | 파일명의 fresh는 forward 실적이 아님 |
| `var/operations/latest.json` | 2026-09-20T13:38:52Z 생성, 09-18 신호 NO TRADE; 저장 valid_until=09-21T13:30Z | 생성 당시 CURRENT. 조회 시각의 최신성은 재계산 필요; 오늘 자동 실행/새 성과로 세지 않음 |

coverage `daily` 942행의 추천 합계도 265와 일치한다. 이유들은 중복 가능하며 단순 합이 총 탈락수가 아니다. calibration edge 거절 1,508/1,959회는 feature 복구 뒤 남은 병목이다. SPY 142일 중 133 COMPLETE/9 배당 미해결, candidate-only 9/spy-only 1 → paired 132/unpaired 10이다. 이것을 OOS의 47/62와 합치지 않는다.

## Frozen OOS와 실패 분석

| fold | OOS 기간 | 선택 | COMPLETE | PENDING | UNRESOLVED | SPY paired/attempted |
|---|---|---:|---:|---:|---:|---:|
| 1 | 2025-04-21~07-21 | 138 | 112 | 15 | 11 | 39/49 |
| 2 | 2025-07-22~10-17 | 0 | 0 | 0 | 0 | 0/0 |
| 3 | 2025-10-20~2026-01-20 | 0 | 0 | 0 | 0 | 0/0 |
| 4 | 2026-01-21~04-21 | 17 | 9 | 8 | 0 | 7/11 |
| 5 | 2026-04-22~07-22 | 2 | 1 | 0 | 1 | 1/2 |
| 전체 | 315 sessions | 157 | 122 | 23 | 12 | 47/62 |

따라서 **157=122+23+12는 artifact로 확인**했다. 적격 122건의 건별 비용 후 expectancy +1.33581%, PF 2.66644, 40bps stress expectancy +1.13581%. 저장 날짜 평균 CI +0.42976%~+2.31129%와 SPY paired 차이 CI −0.34448%p~+1.91602%p는 요약 artifact 값이며 이번에 bootstrap을 다시 실행하지 않았다. 양수 평균은 계좌 수익·Alpha 증명이 아니다.

fold 2는 raw 181/calibration 181 전부 edge 거절, fold 3은 raw 98 중 지원 국면 calibration 92 전부 edge 거절이다. 최소 표본 부족은 두 fold 모두 0이다. 첫 fold의 적격 112/122=91.8%, 전부 RISK_ON_LOW_VOL. 원본 predictions에서 재계산한 NVDA/AVGO 추천 수익 단순 합계 비중은 97.36875%다. 종목별 calibration 제안은 이미 본 자료에서 나온 미채택 가설이다. 이 진단으로 종목/문턱을 고르거나 기존 OOS를 새 확인 표본으로 재사용하지 않는다.

원본 SPY는 62일 중 COMPLETE 48/PENDING 9/UNRESOLVED 5다. paired 47, candidate-only 5(배당 SPY), SPY-only 1(후보 배당), neither 9(양쪽 fold 경계 PENDING)로 **unpaired 15일의 분모**가 보존된다. 12건 후보 UNRESOLVED는 모두 `unverified_cash_dividend_event`; 이 자료에는 결측/상폐 사유가 없다는 뜻이지 해당 위험이 해결됐다는 뜻은 아니다.

누락 선택편향의 산술 진단: frozen에서 수익이 없는 35건의 평균이 약 −4.65625%이면 알려진 122건의 순수익 합계를 상쇄한다(`−sum(122 net_return)/35`). 이는 35건의 실제 기대손실·추정치가 아니며 독립 표본/자본 배분을 가정한 계좌 수익도 아니다. 알려진 결과만의 양수 평균으로 완전성을 대신할 수 없음을 보여준다.

## PENDING의 후속 만기 — 별도 읽기 전용 진단

현재 `validation.py`는 각 fold/phase 마지막 session의 close+30분을 `observe` cutoff로 전달한다. 다음 5 sessions가 fold 밖이면 dataset에 해당 bar가 있어도 `horizon_not_mature`다. 아래 23건은 오늘도 미성숙하다는 뜻이 아니다.

원본 dataset `7d573d75465eb054f3cc89cde451d11fdbd4787f3353c67e84b292be653af2e8`를 로드하고 저장 features로 관측 입력을 복원했다(복원식/한계는 구현 명세 §2). 기존 엔진의 원래 cutoff 계산으로 **157개 상태·사유와 122개 net_return 전부 정확히 일치**했다. 동일 입력에서 cutoff만 `2026-09-16T20:30:00+00:00`로 옮긴 순수 관측 결과다. DB/원본 JSON에 저장하거나 frozen 결과를 교체하지 않았다.

| fold / signal session | 종목 | 5-session 만기 | 후속 상태 |
|---|---|---|---|
| 1 / 2025-07-15 | NVDA, AVGO, PLTR | 2025-07-22 | 3 COMPLETE |
| 1 / 2025-07-16 | NVDA, AVGO, PLTR | 2025-07-23 | 3 COMPLETE |
| 1 / 2025-07-17 | NVDA, AVGO, PLTR | 2025-07-24 | 3 COMPLETE |
| 1 / 2025-07-18 | NVDA, AVGO, PLTR | 2025-07-25 | 3 COMPLETE |
| 1 / 2025-07-21 | AVGO, GOOGL, NVDA | 2025-07-28 | 3 COMPLETE |
| 4 / 2026-04-15 | AMZN, NVDA, GOOGL | 2026-04-22 | 3 COMPLETE |
| 4 / 2026-04-16 | AVGO, AMZN | 2026-04-23 | 2 COMPLETE |
| 4 / 2026-04-17 | AVGO, GOOGL | 2026-04-24 | 2 COMPLETE |
| 4 / 2026-04-20 | AMZN | 2026-04-27 | 1 COMPLETE |

후속 전체는 **157=145 COMPLETE+0 PENDING+12 UNRESOLVED**, eligible 145다. 12개 기존 배당 격리는 유지된다. 같은 62 signal dates에서 SPY pairing은 both 56/candidate-only 5/SPY-only 1/neither 0, 따라서 unpaired 6일이다. 재계산은 research 모드의 역사 가용시각 가정에 따르며 실제 당시 수집 또는 fresh shadow 관찰로 승격하지 않는다. 결과를 보고 paper 가정을 조정하지 않았고 후속 수익률을 새 Alpha 지표로 선정하지 않았다.

## 운영 위험과 보존 기준

현재 working-tree `Config.load('config.toml')`의 model ID는 `baseline-v1-1553f44240af729f`, code hash는 `c803901b448b31296965201c84b6c1161558a0b6f818e978fdf30680f3e23f85`, risk cohort는 `1c721fb12c067d54c40e1b54a2f00fe88ad739f5717afec0c761e0987d4cf0ca`다. PROJECT_STATUS의 이전 build와 다르며 사용자 dirty 변경을 포함한 값이다. 실제 최근 운영 model은 `baseline-v1-1c499becc6025728`; DB risk_state는 이 model/shadow의 NORMAL 1개다. 새 build를 이번에 운영 실행한 기록은 없다.

`scan`은 `track`의 적격 표본, 명시적 risk cohort/dedup, 기존 PAUSED latch를 사용한다. 성과 PAUSED는 영구 유지하고 시장/data pause는 같은 영구 latch가 아니다. 최근 30개 expectancy/cohort drawdown은 추천 위험 지표이며 계좌 MDD가 아니다. coverage의 NORMAL replay와 frozen validation은 이 상태 경로를 실행하지 않으므로 실운영 추천 수/성과를 설명하는 자료로 쓰지 않는다. R1은 독립 paper admission 중단을 추가하되 운영 risk를 초기화하지 않는다.

원문 SHA-256(이번 직접 확인, ROADMAP의 세 artifact 해시와 일치):

```text
var/coverage-m2-1b-final.json  7aa3dd12c0bccebce20872ae458f494dd376ec74620910edec0f62b789ed7c9a
var/validation-m2-1b.json     b7422d30910bcc0af60c48ff234772476e6db8887b2417ff54d31f616bdb5103
var/failure-analysis-m2-1b.json 8854caf3c4182ef74bb4786c2f332ca5443c3de61c3fdab9930dfdb6b58dca04
var/validation-m2-1b-summary.json 0d750fb5ee877f5829c2623c4bb70d18a792a6c0b149c1b6c87a03afa976c11f
var/failure-analysis-m2-1b-summary.json ccddc67db4facc1ab84a080c5a789e422cdb65942dc03100368518767e483dcc
var/richping.db              72c231ca30c4d7fffd8d8672585b61403340d88a138b64778e38d9dc6fcdda3e
var/m2-1b-fresh.db           43925a0351afd026fa8306e46c6730f56a968e288d5726b74887c2e235182a6c
var/operations/latest.json   66d5ec26e03d899d9f85270f004f53c3753d130128357360b834f742ab1141c7
var/daily-report.json        5dd67d2adacfd90ed09f6102574393a4714474bd7d56ed3c6dd412002ff6cdfe
richping/pipeline.py         3f8adec4b70dae3103480a3d76600d4512e639f9b102f67403f1b94acc27dd42
tests/test_operations.py     d005e9563a2b1156f8e69a4bcf3f817348db608f94caa7e81d0c311480e25ca5
config.toml                 70325412db0d6274854a6af4a1e641413852cf3eb987e4f4cb4f5ea35bdccea6
```

문서 링크/분모/fixture 산술 및 diff를 검사하고 위 원본 해시를 재확인한다. 문서만 변경하므로 공통 실행 규칙에 따라 전체 pytest/CLI 실행을 이번 테스트 통과로 주장하지 않는다. 과거 245 passed 등은 이전 세션 기록이다. 예약 trigger·다일 무인 안정성은 이번에 재검증하지 않았고 미래 성과는 대기다. 다음 요청은 **R1-B**, 완료 후 회계 검수 Q다.
