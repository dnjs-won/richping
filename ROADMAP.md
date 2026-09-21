# Richping 목표와 실행 로드맵

기준일: 2026-09-20. 최상위 요구사항은 `PROJECT_SPEC.md`, 현재 실행 계약은 `docs/DESIGN.md`다. 이 문서는 미래 개발 순서를 대체한다. M1·M2-1A·M2-1B의 과거 완료 판정은 취소하지 않는다. **이 문서의 신규 기능·완료 기준은 계획이며 구현 완료 선언이 아니다.** 첫 구현 요청은 [FIRST_MILESTONE.md](docs/FIRST_MILESTONE.md)를 사용한다.

## 1. 프로젝트 재정의

Richping은 직장 생활과 병행하는 사용자를 위한 **자동 투자 기회 연구·검증·추천 시스템**이다. 매일 이용 가능한 정보로 후보를 찾고, 진입 조건·근거·손실 위험·기대값의 증거 수준을 제공하며, 이후 결과를 자동 관찰한다. 제한된 새 가설을 연구하고 검증을 통과한 경우에만 추천 전략을 바꾼다. 사용자의 일상 업무는 결과 확인과 최종 매매 판단이다. 매매일지 작성, 매일 전략 조정, 모델 관리는 요구하지 않는다.

성공은 기능 수가 아니라 거래비용·위험·현금 대기를 고려한 장기 순수익 개선, 잘못된 매매 감소, 기회 탐색 범위 및 사용자 노동 절감으로 판단한다. 순수익 개선은 검증할 목표이지 보장할 결과가 아니다. 유효한 전략을 못 찾으면 Champion 유지, 추천 중단, 현금 보유도 올바른 결과다. CRCL 및 레버리지 수익 경험은 연구 동기이며 알파의 증명이 아니다. CRCL의 특정 저점이나 사후 급등을 정답으로 맞추는 전략을 만들지 않는다.

최종 경험은 `자동 수집 → 오늘의 추천 또는 이유 있는 NO TRADE → 미래 성과 관찰 → 주기적 증거 평가 → 통제된 연구·비교·승격/강등`이다. 자동 주문은 포함하지 않는다. 첫 유용한 일일 보고서, 모의 포트폴리오, 제한적 소액 실전 검토, 전체 자동 개선의 완료 시점은 서로 다르다.

## 2. 현재 시스템의 위치: 확인한 사실과 증거

### 조사 범위 및 저장 상태

- 시작 시 로컬 `main`은 clean, HEAD와 `origin/main`은 `26f565a4e6d4ccbd97f1a14a31a03736050c5373`. GitHub `refs/heads/main`도 `git ls-remote`로 같은 해시를 확인했다. 로컬 미커밋 실행 코드 변경은 없었다. 이번 문서 수정은 아직 커밋/푸시하지 않았다.
- `PROJECT_SPEC.md`, `PROJECT_STATUS.md`, `README.md`, `AGENTS.md`, DESIGN, COVERAGE_DIAGNOSTIC, DIVIDEND_CONTRACT_DECISION을 읽고 `richping/`의 engine/evaluation/validation/pipeline/store/cli/core, 관련 수집·feature 계약 및 테스트와 대조했다.
- `var/`는 Git ignore 대상이고 Git 추적 파일은 없다. 후속 validation·failure-analysis 원문과 요약 JSON은 로컬에 존재하지만 GitHub에 반영된 코드나 문서 산출물로 간주하지 않는다. 아래 핵심 수치를 본 문서에 보존한다. 원래 분석 실행 환경 전체와 생성 스크립트는 복원하지 않았으며, 이번에 실데이터 validation을 새로 실행한 것은 아니다.
- SQLite를 `mode=ro`, `query_only`로 조회했다. `var/richping.db`: datasets 3, bars 30,060, shadow SUCCEEDED 1건(2026-09-14), recommendations 0, outcomes 0, experiments 1. `var/m2-1b-fresh.db`: dataset 1, bars 10,020, runs/recommendations/outcomes/experiments 모두 0. **fresh라는 파일명은 fresh forward 실적을 뜻하지 않는다.**
- 현재 코드로 계산한 model ID는 `baseline-v1-c202598ad5eb5bbe`, code hash는 `84faff746fb61abc28cb81d72b8f3d175c96cf2a8d61061e69b4af64617dcf6b`; 로컬 M2-1B 산출물과 같다. 원본 DB 및 7개 기존 보고서의 현재 SHA-256은 `var/m2-1b-integrity.json`의 after 값과 모두 일치했다. 과거 해시 기록 자체를 이번에 새로 생성한 것은 아니다.

| 단계/영역 | 현재 판정 | 의미와 남은 한계 |
|---|---|---|
| M1 | E2E 구현 완료 | 일봉 수집, 고정 추천, 동결, 자동 관측, CLI, synthetic replay. 알파 증명 아님 |
| M2-1A | COMPLETE WITH KNOWN LIMITATIONS / GO 기록 유지 | action provenance, v3 fail-closed, v2 평가 격리, 저장 outcome·시점·SPY 분모 보강. 일반배당 실데이터 회계 완료 아님 |
| Coverage 및 provenance 후속 | 구현·로컬 실측 있음 | capture 누락과 배당 feature 차단을 분리 측정 |
| M2-1B | COMPLETE / 구조적 추천 차단 해소 | `cash_gap_backward_v1` feature 정규화. outcome v3·평가 정책·통계 threshold 불변 |
| 후속 baseline validation/실패 분석 | 로컬 research 산출물 확인 | MIXED, 집중도와 calibration 경계 민감성. fresh OOS/승격 아님 |
| daily 자동화 | 부분 구현 | 증분 수집, retry, wrapper lock, 원자적 보고서 교체. 스케줄러 등록·알림·장기 무인 운영은 확인 안 됨 |
| 위험 제어 | 추천 경로 구현 | 최근 추천 기반 축소/중단 및 latch. 계좌 노출·실제 주문 제어 아님 |
| 자동 발견/개선/승격 | 미구현 | experiments와 순수 gate 함수만 존재; challenger 생성·promotion writer 없음 |
| 포트폴리오/실전 실적 | 미구현·미검증 | 추천 수익과 계좌 수익을 연결할 원장 없음 |

### 현재 전략은 무엇인가

후보는 AAPL/MSFT/NVDA/AVGO/AMZN/META/GOOGL/PLTR 8개다. SPY/QQQ는 후보가 아닌 시장 문맥이다. 가격 $5 이상, 원본 가격×거래량의 20일 평균 $5M 이상, 61-session feature 창이 필요하다. 고정 momentum 25 + SPY 대비 RS 25 + trend 20 + relative volume 15 + breakout 15 점수로 순위를 매긴다. 점수 ≥60, 가격 >MA20, 정상 ATR이 필요하다. 시장은 SPY·QQQ 모두 MA60 위이고 SPY 20일 실현변동성 연율 <25%일 때만 지원한다. 최대 3개, 기본 5-session 보유 관측이다.

따라서 **고정 추세·상대강도 모멘텀 전략**이다. 새 패턴을 학습하는 모델이 아니며 급등 초기, 눌림목 구조, 매도 후 재진입, 이벤트 판단을 명시적으로 구현하지 않는다. 눌림 뒤 추세 회복을 우연히 포착할 수는 있으나 포착률·진입 지연·실패율은 측정하지 않았다. CRCL은 현재 후보에 없고 신규 상장 종목은 warmup 및 충분한 calibration 표본도 제약이다. 현재 대형 성장주 편중 8개는 시장 전체 및 상폐 포함 과거 universe를 대표하지 못한다.

기대값은 과거 504 sessions 내 결과가 확정되고 label 경계/embargo를 통과한 같은 regime·score ±15 후보를 종목 간 pooling하여 추정한다. 최소 60건/30 signal dates, 날짜 평균 수익의 block bootstrap 95% CI 하한 >0 및 손실 표본이 있어야 한다. 점수는 예측 확률이 아니다. Expected Return은 날짜 평균 비용 후 수익 추정, Expected Loss는 손실 표본 평균, R/R는 평균 이익/평균 손실, Confidence는 경험적 승률이다. 전체 성과 `metrics.expectancy`는 추천 건별 평균이므로 calibration의 날짜 평균과 분모가 다르다.

Entry는 신호일 종가 참고값, Stop/Target은 ±2/4 ATR 참고값이다. outcome은 **다음 거래일 시가부터 horizon 종가까지 보유한 가격 수익**에서 왕복 20bps를 차감한다. stop/target 접촉은 진단일 뿐 그 가격에서 청산한 수익이 아니다. 같은 일봉 양쪽 접촉은 AMBIGUOUS다. 실제 갭·호가·주문 거절·사용자 체결 차이는 현재 반영되지 않는다.

### NO TRADE와 장애를 구분한다

- 후보 없음: universe/feature 무결성, 가격·유동성, score/MA20, ATR 필터 탈락.
- 증거 없음: calibration 표본 부족, CI 하한 ≤0, 손실 표본 부재, REDUCED_EXPOSURE에서 강화 edge 미달.
- 시장/위험: risk-off 또는 high-vol, 최근 적격 30건 expectancy <0이면 축소; expectancy ≤-2% 또는 cohort drawdown ≤-15%이면 PAUSED latch. 미해결 outcome/평가 제외도 scan을 중단시킬 수 있다. 현재 위험 상태는 model_id/mode별이다.
- 성과 pause는 자동 반등으로 풀리지 않는다. 시장·데이터 pause는 같은 영구 latch와 다르다. 새 코드 hash로 model_id가 바뀌면 기존 위험 증거와 분리될 수 있으므로 운영 버전 교체를 무심코 위험 초기화 수단으로 쓰면 안 된다.
- benchmark 결측/action 오류, 늦은 실행(다음 개장 경과), 수집 실패는 정상 NO TRADE가 아니라 예외/FAILED가 될 수 있다. 이후 보고서에서 장애와 거래 기회 부재를 명확히 구분해야 한다.

### 데이터와 실적 종류

| 종류 | 입증 가능한 것 | 입증할 수 없는 것 |
|---|---|---|
| Synthetic | 계산·시점·불변성·실패 경로 | 시장 수익성, 공급자 신뢰도 |
| Research replay/coverage | 저장 vintage에서 고정 규칙이 어디서 차단/통과되는지 | untouched OOS, 실제 운영 위험 latch의 성과 |
| 실데이터 research OOS | train 밖 시간 순서의 고정 규칙 진단 | 당시 실제 사용 가능 데이터, 생존 편향 제거, 최종 holdout 알파 |
| Fresh shadow | 고정한 전략을 실제 미래 시각에 기록한 뒤 관찰한 결과 | 실제 체결/계좌 수익, 과거 calibration 자료의 PIT 품질 자동 인증 |
| 미사용 확인 OOS | 사전 등록 후 처음 평가한 데이터에서의 비교 | 탐색·반복 열람된 기존 OOS의 재인증 |
| Paper / 실제 fills | 각각 명시한 가상 집행 / 실제 체결의 포트폴리오 결과 | paper를 실제 실현 수익으로 표시하는 것 |

shadow 신호 cutoff는 실제 실행 시각을 검사하지만 `Engine.history` calibration은 현재 수집판의 research 역사 labels를 사용한다. forward 수집을 시작해도 이 한계는 별도 표기한다. 현재 members 저장 구조와 active/known_at 필터는 존재하나 Yahoo의 현재 목록을 역사적 PIT membership으로 바꾸지는 못한다.

**Feature dividend normalization ≠ Outcome dividend accounting.** M2-1B의 가격 변환과 단위 증거는 보유기간 배당 권리·일반/특별 분류를 승인하지 않는다. v3는 현금배당·split·Capital Gains·capture unknown을 격리하며 v2 COMPLETE는 `cash_action_review_v1`에서 제외한다. Yahoo 소급 수정, 과거 membership, 상폐 회수금, 복합 기업행동은 미해결이다. 제외가 편향을 만들 수 있으므로 적격 수익만의 양수 평균으로 이를 덮지 않는다.

### 로컬 수치와 해석

M2-1B dataset: `7d573d75465eb054f3cc89cde451d11fdbd4787f3353c67e84b292be653af2e8`, 2022-09-19~2026-09-16, 10,020 bars. feature coverage 942 sessions에서 benchmark supported 16→941, blocked 926→1. Research rolling replay 추천 142일/265건, holding 결과 COMPLETE/PENDING/UNRESOLVED=256/0/9, 적격/제외 COMPLETE=256/0, SPY paired=132/142일. 미해결 9건은 holding 배당이다. `edge_not_supported` 1,508/1,959 calibration 시도. 이는 **구조적 병목이 풀리고 성능 증거 부족이 드러났음**을 뜻한다.

후속 `var/validation-m2-1b.json` 및 summary의 frozen 504/63/63 walk-forward는 별개 분모다.

| 지표 | 확인 값 | 판정 |
|---|---:|---|
| folds / OOS sessions | 5 / 315 | 시간 순서 연구 평가 |
| 선택 추천 / signal dates | 157 / 62 | 5-session 관측 대상 |
| COMPLETE / PENDING / UNRESOLVED | 122 / 23 / 12 | eligible COMPLETE 122, excluded COMPLETE 0 |
| 적격 추천 / 적격 날짜 | 122 / 52 | 157 전체의 성과로 확대 해석 금지 |
| 추천 건별 비용 후 expectancy / PF | +1.336% / 2.666 | 실제 계좌 수익 아님 |
| 40bps stress expectancy | +1.136% | 단순 비용 2배 진단 |
| 날짜 평균 bootstrap 95% CI | +0.430% ~ +2.311% | 건별 평균의 CI로 오기하지 않음 |
| paired SPY / attempted | 47 / 62일 | unmatched 15일도 보존 |
| paired 날짜 평균 초과수익 / CI | +0.815%p / -0.344%p ~ +1.916%p | 우위 확정 불가 |
| fold별 적격 수 | 112 / 0 / 0 / 9 / 1 | 첫 fold 91.8%, 시간 안정성 없음 |
| 적격 regime | 전부 RISK_ON_LOW_VOL | 다른 국면 성능 입증 안 됨 |
| cohort drawdown | -9.305% | portfolio MDD 아님 |

PENDING 23건은 해당 fold 종료 cutoff에서 미성숙한 결과다. 지금도 실제 미성숙이라는 뜻이 아니다. 경계 추천을 사라지게 하지 말고 후속 maturity view로 재평가하되 원본 OOS 보고서는 보존한다. 동일 신호의 다른 horizon이나 평가 vintage를 독립 표본으로 중복 세지 않는다.

`var/failure-analysis-m2-1b.json` 및 summary: fold 2/3은 raw signal/표본 부족보다 **동결 calibration CI 하한의 불안정성**이 주원인이다. NVDA/AVGO는 적격 122건의 54.1%, 추천 수익 단순 합계의 97.37%를 차지한다. 이 합계는 집중도 진단이고 자본 가중 투자 이익이 아니다. 두 종목 제외 진단 expectancy 약 +0.077%, PF 1.056. 이를 보고 고수익 종목만 남기는 것은 사후 선택이다.

종목별 calibration 제안은 로컬 가설이며 구현되지 않았다. 이미 열람한 fold 2/3에서 추천이 생기는지는 탐색 진단일 뿐 향후 승격 조건이 될 수 없다. 표본 축소와 종목 과적합 위험이 있어 채택을 확정하지 않는다.

`validate()`는 실제 집계 증거가 아닌 `promotion_gate({})`를 호출한다. REJECT 사유 전체가 모든 측정 지표의 실제 실패를 뜻하지 않는다. 5 folds, PF, stress는 수치상 문턱을 넘지만 PIT, fresh shadow, 결과 완전성, 표본, paired 개선, 안정성은 확보되지 않았다. 결론은 **MIXED research / Alpha: INSUFFICIENT EVIDENCE / 자동 승격 불가**다.

재확인용 원문 SHA-256:

```text
validation-m2-1b.json      b7422d30910bcc0af60c48ff234772476e6db8887b2417ff54d31f616bdb5103
failure-analysis-m2-1b.json 8854caf3c4182ef74bb4786c2f332ca5443c3de61c3fdab9930dfdb6b58dca04
coverage-m2-1b-final.json   7aa3dd12c0bccebce20872ae458f494dd376ec74620910edec0f62b789ed7c9a
```

장기 무인 운영 실측은 **NOT_ESTABLISHED**다. 1일 성공과 결정론적 복구 테스트는 다주 운영을 증명하지 않는다. 현재 사용자 산출물은 CLI/JSON의 후보·제외 사유·기대값·위험 참고값, outcome 상태와 연구 진단이다. 저장된 마지막 운영 보고서를 오늘의 추천으로 읽으면 안 된다.

## 3. 목표와 현재 설계의 차이 및 처분

| 기능/방향 | 판단 | 변경 이유와 범위 |
|---|---|---|
| Python modular monolith / SQLite / CLI | KEEP | 지금 규모에 충분. 운영·연구 데이터 쓰기 책임만 분리 |
| immutable dataset/snapshot/outcome, provenance, PIT 검사 | KEEP | 재사용할 검증 기반. 과거 결과를 새 계약으로 덮지 않음 |
| feature 정규화와 v3/evaluation 정책 | KEEP | 결과 회계와 혼동 금지. 추가 사건 계약은 병목 측정 후 별도 버전 |
| 고정 baseline | KEEP | 비교 기준 및 shadow 증거 수집. 검증된 수익 전략이라는 이름은 금지 |
| 단일 고정 universe와 신호 종목만의 연구 | MODIFY | 단계적 후보 확대와 비신호·실패 사례 관찰 추가 |
| 검증 완료 후에만 discovery 시작하는 순차 계획 | MODIFY | 운영 forward와 격리된 제한 연구를 병행; 미검증 production 유입 차단 |
| ranker 평가와 daily 위험 제어의 혼합 해석 | MODIFY | fixed replay, 운영 pause 포함 경로, paper 계좌 성과를 분리 |
| 보고서/일일 배치 | MODIFY | freshness·장애·NO TRADE·관측 증거를 매일 이해하기 쉽게 제공 |
| 가벼운 전달/운영 관찰 | ADD | 로컬 읽기 쉬운 보고서부터, 선택적으로 Telegram. 복잡한 UI 불필요 |
| 최소 paper 자본/포지션 원장 | ADD | 기존 MVP 밖이었지만 소액 실전 검토의 필수 검증. 최적화 아님 |
| 실험 원장/holdout 사용 이력/승격 이력 | MODIFY/ADD | experiments 재사용, 실패와 탐색 횟수 및 증거 연결 보강 |
| 자동 중단/강등과 검증된 대안 선택 | ADD | 새 전략 수보다 잘못된 승격 방지가 우선 |
| 거시·섹터·VIX·옵션·뉴스 | DEFER | 가격/거래량 한계와 추가 효용을 먼저 측정 |
| 분산 처리·agent hierarchy·대형 frontend·포트폴리오 최적화 | DEFER | 실측 병목/사용자 효용 전에는 구현하지 않음 |
| 수동 일지·무제한 AI 가설/자가 승격·사후 종목 예외 | DROP | 사용자 노동 및 과최적화 비용, 목표와 충돌 |
| 자동 주문 | 범위 제외 유지 | 별도 명시적 사용자 승인과 별도 설계 없이는 추가하지 않음 |

현재 기반은 재사용하기에 충분하지만 목표 달성에는 불충분하다. 추천 외 시장 관찰, 집행 가능한 전략 정의, 자본 회계, 실험 통제, 실제 증거를 연결한 승격, 장기 운영 실측이 빠져 있다. 원래 M1~M5는 역사적 계획으로 남기고 아래 R 단계로 대체한다.

## 4. 권장 목표 아키텍처와 공통 검증 계약

```text
수집(data.py) → 불변 vintage / known_at / membership 검증(store.py)
                  ├─ A Production Recommendation
                  │   고정 승인 버전 → feature_window/Engine → pipeline.scan
                  │   → immutable recommendation → daily 보고/선택 알림
                  │   → track/observe 미래 관찰 → 위험 축소·중단
                  └─ B Research & Discovery
                      전체 관찰 대상/대조군 → 제한 가설·trial 등록
                      → 동일 Engine/observe/validation/evaluation 재사용
                                  ↓
                      C Evaluation & Promotion
                      미사용 OOS + 비용/포트폴리오 + fresh shadow
                      → gate 증거 검증 → 제한적 활성화/강등 이력
                                  ↓
                      A의 다음 실행부터 선택된 승인 버전 사용
```

A/B/C는 논리적 경로다. 세 서비스나 에이전트 계층을 만들지 않는다. 처음에는 운영 SQLite와 연구 SQLite/산출물 디렉터리를 분리하고 같은 Python 함수를 사용한다. 기존 `mode`는 research/shadow만 지원한다. 경로 이름을 새 DB mode가 이미 존재하는 것처럼 취급하지 않는다. 후보별 model/config/code/data ID 및 evidence ID를 연결하는 작은 실행 명세를 추가한다.

- A는 운영 추천·관측·위험 상태를 소유한다. B는 운영 DB에 추천·위험 상태를 쓰지 못하며 read-only 동결 입력을 복사/참조한다. C만 승격 결정 이력을 소유한다. 기존 snapshot을 재작성하지 않고 유효시각 이후 실행에만 적용한다.
- baseline도 현재는 **운영 관찰용으로 고정한 버전**이지 알파 승인을 받은 Champion이 아니다. C가 생겨도 이 구분을 보존한다. 연구 가설을 생성한 AI에게 활성화 쓰기 권한을 주지 않는다.
- paper 원장은 추천과 분리한다. 실제 fills가 있으면 별도 실계좌 관찰 원장으로 구분하고 가상 fills와 섞지 않는다. 실거래 결과 자동 추적은 향후 read-only 체결내역 import 등으로 해결하며 일지 노동을 기본 요구하지 않는다. fills 확보 전에는 추천 outcome만 추적했다고 표시한다.
- 데이터 증가 시 증분 수집·캐시·요청 제한·재시도·단일 writer·배치 처리부터 측정한다. 현재 immutable full-vintage 저장은 확장 시 중복 용량 병목 후보다. 종목 수별 시간/메모리/DB 증가량을 보고한 뒤에만 불변 manifest+재사용 partition 등을 검토한다. 구 vintage의 ID와 읽기 호환성을 유지한다. 분산 시스템은 선행조건이 아니다.

### 성과 지표와 자본 비교

추천 진단에는 비용 후 기대수익, 날짜 평균과 건별 평균의 구분, 평균 이익/손실·실현 가능한 payoff, PF, quantile/expected shortfall/최악 손실, 손실 연속성, 거래 빈도, regime·ticker·fold 집중도, 표본/날짜/CI, 미해결/제외율을 함께 둔다. outcome completeness는 단순 COMPLETE 비율이 아니라 추천 전체와 누락 이유를 포함한다. 차단·결측이 무작위라고 가정하지 않는다.

Paper부터 초기 자본, 동시 보유 한도, 종목별 한도, sizing, 현금 부족 시 skip, 동일 종목 재추천, 진입/청산 순서, 주식 수 반올림, 비용·갭·미체결, 현금 이자 가정, 기업행동 처리를 사전 고정한다. 일별 NAV, 실현/미실현 손익, turnover, 자본 사용률, 현금 보유일, 실제 포트폴리오 MDD를 계산한다. 총 추천 수익의 합/평균, 동일 날짜 cohort 복리는 계좌 수익이 아니다. 손절가가 최대 손실을 보장하지 않으며 레버리지 수익을 위험조정 알파로 바꾸지 않는다.

SPY 비교는 (1) 같은 시작 자본·기간의 buy-and-hold 총수익을 기회비용으로, (2) 같은 시점의 자본 배분·현금 대기·거래비용 규칙을 적용한 SPY 대체 포트폴리오를 선택 효과 비교로 함께 둔다. 두 비교의 현금 노출 차이를 명시한다. 기존 matched-SPY 날짜 평균은 추천 진단으로 유지한다. SPY 배당/상폐 등 회계를 검증하지 못하면 총수익 우위를 판정하지 않고 비교 불완전으로 표시한다. 무배당 부분기간 비교만으로 전체 투자 우위를 주장하지 않는다.

### 자동 연구가 실패해도 안전한 계약

1. trial 실행 전에 가설·관측 범위·feature cutoff·label·진입/청산·비용·후보 수·분할·주지표·중단 규칙을 등록한다. 생성·실패·폐기·재시도까지 trial family에 기록한다. 무제한 파라미터 탐색 금지.
2. discovery 자료, 모델 선택 validation, 확인용 미사용 OOS, 이후 fresh forward를 구분한다. 이미 열람한 M2-1B OOS는 discovery 자료다. 데이터가 바뀌어도 같은 날짜를 새 holdout으로 세탁하지 않는다.
3. 시계열 split, 최대 label 중첩 purge/embargo, feature와 membership의 known_at, label_end를 지킨다. 같은 날짜 종목 및 중첩 holding 상관을 고려한 paired/date-block 분석을 재사용하고, 종목/섹터 집중과 block 길이 민감도도 점검한다. 200개 추천이 독립 200회라는 뜻은 아니다.
4. trial 수를 감안한 사전 고정 다중시험 보정, 비용 2배 및 갭/체결 stress, 국면/파라미터 안정성, tail·낙폭 비악화를 확인한다. 최상의 한 평균만 고르지 않는다. 점검 주기·alpha budget/순차검정 규칙도 결과 열람 전에 고정해 매일 CI를 보며 선택하는 문제를 막는다.
5. 미사용 OOS는 사용 이력에 소비 처리한다. 탈락한 뒤 동일 구간으로 수정·재승격하지 않는다. fresh forward도 연구에 열어 사용하면 그 이후의 새 확인 구간이 필요하다.
6. 기존 gate 하한(≥200 OOS 추천, ≥60 dates, ≥3 folds, PF≥1.1, 비용 stress 양수, paired CI 하한 >0, PIT/완전성/안정성/다중시험/fresh shadow)은 현재 계약으로 보존한다. 충분조건이 아니다. 미래 portfolio 기준 추가는 새 정책 버전으로 정의하며 기존 결과에 소급 적용해 원문을 바꾸지 않는다.
7. 처음에는 최대 1개 challenger·1개 변경축부터 시작한다. C 구현 후에도 gate 통과는 shadow review 적격일 뿐 즉시 실전 활성화가 아니다. shadow 승인 → 제한된 추천 활성화 → 추가 fresh forward 관찰 → 확대 여부의 단계로 운영한다.
8. 증거 부족/열화/운영 장애 시 신규 추천을 줄이거나 중단한다. 대안이 검증되지 않았으면 현금 상태로 남는다. 기존 성과 latch를 초기화해 재개하지 않는다. 승격·강등·롤백은 이유와 유효시각을 기록한다.

미래 R5/R6에서 `fresh_shadow` boolean만으로 통과시키지 않는다. 초기 검토용 운영 정책안은 **고정 버전의 fresh 관찰 최소 60 XNYS sessions 및 적격 signal dates 최소 30일**, 모든 예정 실행/선택 추천의 상태 설명, 비용 stress 양수, Champion 대비 paired 개선과 tail/낙폭 기준 충족이다. 기간/날짜 하한은 충분조건이 아니며 신뢰구간·표본/국면이 부족하면 연장한다. 이는 현 코드의 기존 gate를 수정한 것이 아니라 구현 전 사전 등록할 추가 정책안이다. ≥200 OOS 추천/≥60 OOS signal dates 등 기존 기준을 대체하지 않는다. R0 보고서와 R1 paper 시작에는 이 성과 승인 기준을 요구하지 않는다.

## 5. 신규 로드맵

규모 S=기존 경로의 국소 확장, M=여러 모듈 및 새 계약 1개, L=데이터 공급/회계/검증을 동반한 확장이다. 달력 납기를 뜻하지 않는다. **개발 완료와 미래 증거 충족을 별도로 종료 판정**한다. 미래 추천 빈도·시장 국면·공급자 사건에 따라 관찰 기간은 늘어날 수 있다.

### R0 — 일일 관찰 제품과 고정 baseline 증거 수집 시작 (즉시, M)

- 상태(2026-09-20): **R0-B 실제 next-open 이전 실행 1회와 Windows 예약 등록·구성 확인 완료.** 예약 trigger의 첫 실행과 미래 다일 관찰은 아직 충족하지 않았다.
- 목표: 사용자가 매일 볼 수 있는 보고서를 만들고 실제 미래 증거 축적을 시작한다.
- 현재: 수집 전 attempt, freshness/장애/NO TRADE 구분, JSON+Markdown 세대, read-only forward 요약, 운영/연구 출력 격리와 risk latch 연속성을 구현했다. 운영 DB에는 2026-09-18까지의 새 immutable adapter vintage와 새 FRESH_SHADOW 1건이 추가됐고 shadow 성공은 legacy 포함 2 sessions다. `Richping Daily`는 현재 사용자 제한 권한, Asia/Seoul 08:00으로 등록됐으나 예약 trigger 자체는 아직 실행 전이다.
- 필요성: 대기하면 얻지 못하는 forward 증거와 사용자 효용을 가장 먼저 확보한다. 전략 추가나 배당 전체 회계보다 선행한다.
- 범위: cli/pipeline의 보고·실행 상태, scripts/daily.ps1, 최소 운영 기록·freshness, 읽기 전용 증거 요약. 기존 알고리즘·위험 threshold·v3는 유지. 데이터/전략 버전을 명시해 운영 시작 시점 동결.
- 산출물: 오늘의 후보 또는 구체적 NO TRADE/장애 사유, 진입 관찰 규칙·ATR 참고값·증거 수준, 관측 진행표, 운영 상태. 로컬 Markdown/텍스트+JSON 우선. Telegram은 수신처 설정 이후 동일 내용 전달하는 선택 후속 범위다.
- 완료: 결정론적 장애/중복/시점/불변성 검사 통과, 실제 다음 개장 전 일일 실행 최소 1회 및 스케줄러 설정/로그 확인, 같은 run 보고서 재생 동일, stale 보고서가 오늘로 표시되지 않음. 이는 운영 시작 완료이고 장기 안정성 완료가 아니다.
- 검증: 기존 전체 테스트+신규 보고/운영 경계 테스트, 별도 fixtures DB, 실수집 실행 기록, 원본 snapshot/hash 보존. NO TRADE도 정상 완료 사례로 인정한다.
- 의존성: 기존 M2-1B, 실행 가능한 환경·네트워크. 외부 알림 없어도 종료 가능.
- 병목: 모델 ID 변경과 위험 상태 연속성, 수집 실패, 실행 시간, 빈번한 NO TRADE, PC 절전. 첫 코드 변경으로 버전이 달라지는 사실을 숨기지 않는다.
- 보류: 다음 개장 전 실행·데이터 시점 보증 실패 시 추천 게시를 막고 진단만 제공한다. fresh 통계 표본 부족은 보고서 제공을 막는 이유가 아니다.

### R1 — 고정 baseline의 판단 가능한 평가와 모의 포트폴리오 (M~L)

- 상태(2026-09-21): **R1-A 계약 및 R1-B 최소 원장 개발 완료. 핵심 회계 검수 Q와 실제 미래 paper 증거는 대기.** Frozen 157건의 원본/후속 분모를 별도 재현하고, 연구 fixed/운영-policy replay와 forward-only 등록 경로를 구현했다. Frozen replay는 배당 미해결로 NAV가 확정되지 않았고 rolling replay의 확정 NAV도 소비된 연구 자료이므로 Alpha 증거가 아니다. 두 SPY 비교는 배당 총수익 불완전으로 판정 보류다.
- 목표: baseline을 유지/연구 전용/중단할 근거를 만들고 자본 제약 아래 모의매매를 시작한다. “검증 완료”는 양의 알파 판정과 동의어가 아니다.
- 현재: frozen research OOS, coverage, 실패 진단과 maturity follow-up, append-only paper 원장이 있다. fold 경계 PENDING 23건은 후속 COMPLETE로 설명됐고 holding 배당 12건과 SPY unpaired/총수익 불완전은 보존된다. 실제 미래 `FORWARD_PAPER` 표본과 실체결은 아직 없다.
- 필요성: 추천 평균이 양수여도 실제 활용 가치가 낮을 수 있다. 자본과 빈도를 봐야 다음 전략의 개선 목표를 정할 수 있다.
- 범위: validation/evaluation 재사용, 원본 결과와 분리한 maturity follow-up, vintage/제외/paired coverage 표, 최소 paper ledger와 집행 계약. 기본 next-open→5번째 close를 우선 재현하고 stop 체결 전략은 별도 후보로만 다룬다.
- 산출물: baseline 판단 카드, 가상 자본·보유·현금·NAV·손실 분포, SPY 두 비교, 미래 shadow 누적 보고. 신규 전략 없이도 모의 운영 가능.
- 완료: 157=122+23+12 등 기존 분모 재현, 23 PENDING 후속 상태 모두 설명, 미해결·unpaired 원인 및 선택편향 민감도 제시, paper 현금/포지션 보존·중첩/재추천/미체결 처리 검증, INSUFFICIENT/부정적/추가 관찰 판정을 근거와 함께 발행. 자동 승격 문턱 미달은 그대로 유지.
- 검증: 손계산 가능한 자본 보존 fixture, missing/delist/action/gap stress, 동일 현금 흐름 SPY pairing, baseline 및 model별 shadow 구분. live 전략 위험 latch를 적용한 별도 실행 경로도 평가해 fixed replay와 차이를 보고한다.
- 의존성: R0 보고·버전 계약; paper 구현은 forward 성과가 쌓이는 동안 진행 가능.
- 병목: 배당·상폐 미해결로 NAV 또는 SPY 총수익이 불완전할 수 있다. 누락을 0으로 평가하지 않고 NAV 미확정/범위와 거래 중단을 표시한다.
- 보류: 사건 회계가 판단을 바꿀 정도의 병목이면 필요한 사건/공급자 계약만 별도 작업으로 연다. 현재 941/942 feature 복구를 이유로 모든 corporate-action 인프라를 선행하지 않는다. 미래 성과 판정은 충분한 fresh 증거가 올 때까지 미완료다.

### R2 — 단계적 universe와 비신호 종목 관찰 (M~L)

- 목표: 8개 밖의 기회와 실패/비상승 대조군을 관찰한다.
- 현재: explicit config 및 members/known_at 구조만 있고 역사적 dynamic universe 공급 계약은 없다.
- 필요성: 신호 종목만으로는 새로운 패턴과 놓친 기회를 발견할 수 없다.
- 범위: data/store/universe 계약, 날짜별 관측 가능 유동성 선별, 신규 상장·거래정지·상폐·symbol 변경 처리, 전 후보 feature/누락 reason의 연구 저장. membership 반복 입출입은 현재 ticker당 한 row 구조로 충분하지 않으므로 버전 있는 이력 계약을 설계한다.
- 산출물: 우선 50~100개 규모의 유동성 후보 관찰 pilot(목표 용량, 확정 선정 종목 아님), 제외 이유·관측 범위·처리비용 표. 신호와 무관한 관찰 패널.
- 완료: 당시 cutoff 이전 자료로 membership 결정, 당일 탈락·누락 종목까지 분모 보존, 10→50→100 규모별 수집시간/메모리/DB 증가 측정, 다음 보고 deadline 내 증분 처리가 됨. 과거 PIT 공급이 없으면 시작 이후 forward universe만 적격, 과거 replay는 research라고 표시.
- 검증: 미래 유동성/상폐/새 상장 변경이 과거 membership을 바꾸지 않는 테스트, symbol 식별·결측·revision·rate-limit 재개, nonwinner 포함 샘플 감사.
- 의존성: R0 경로 격리와 관측 계약. R1 알파 결론을 기다릴 필요는 없다.
- 병목: 공급자의 전체 종목 목록·상폐 역사·요청 한도·비용. universe 밖 상승은 관측 못 했다고 명시한다.
- 보류: 전시장 동시 full-history 수집은 보류한다. 넓은 목록의 저비용 유동성 screening→좁은 후보의 상세 특징 계산을 우선하되, 탈락군도 사전 정한 표본/집계로 남긴다. 역사 PIT 또는 비용 계약이 불가하면 forward pilot을 유지하고 시장 전체 성능 주장을 하지 않는다.

### R3 — 실행 가능한 패턴 가설과 제한 challenger 연구 (M)

- 목표: baseline이 놓치는 기회가 별도 전략으로 재현 가능한지 검증한다.
- 현재: failure-analysis의 종목별 calibration 제안만 있음. 자동 발견·실험 후보 생성은 없다.
- 필요성: R0 관찰 대기 중에도 연구할 수 있고, 다음 개선을 threshold 완화 대신 가설로 제한한다.
- 범위: experiments family/실패 기록 보강, 후보 generator와 strategy ID, 같은 Engine/observe 검증 경로. 초기 최대 1개 변경축·1개 challenger. 현재 gate와 baseline byte-level 결과 보존.
- 산출물: baseline의 패턴 포착률·진입 지연·실패 사례, 가설별 사전 조건·거절 조건·실험 결과 카드. 부정적 결과도 산출물이다.
- 완료: 아래 후보 중 한 가설을 발견 자료에서 선택·등록하고 untouched 구간을 별도 확보, 실행·실패 trial 모두 재현 가능, research 출력이 운영 추천/위험 상태를 바꾸지 않음. “좋은 수익”을 개발 완료 조건으로 삼지 않는다.
- 검증: feature cutoff·label_end·purge/embargo, 비상승/실패 대조군, 비용/갭/진입 가능성, 동일 기간 Champion 비교와 다중시험 기록. 사용한 OOS는 소비 처리한다.
- 의존성: 좁은 8종목 연구는 R0 후 격리해서 시작 가능; 시장 패턴 발견은 R2 패널이 필요. paper 성능 비교는 R1 필요.
- 병목: 종목별 calibration은 표본 급감 가능, 급등 사건은 희소하며 상관·국면 집중이 크다.
- 보류: 새 검증 구간이나 최소 독립 날짜가 없으면 탐색 진단에서 멈춘다. NO TRADE를 줄이기 위한 문턱 완화·CRCL 특정 가격 맞추기는 금지.

| 우선 연구 계열 | 의사결정 전 관측 조건의 예 | 실패/비상승 대조와 검증 질문 |
|---|---|---|
| baseline calibration 안정성 | 기존 regime/score 조건 유지, pooled 대비 ticker-conditioned 1축 | 종목 pooling이 문제인가, 단순 표본 축소인가? 기존 OOS 재개선은 탐색에 한정 |
| 눌림목·추세 재개/재진입 | 선행 RS/상승, 과거 고점 대비 ATR 조정폭, 조정 중 volume 수축, 당일 회복 조건 | 같은 선행 상승 후 추세 붕괴·반등 실패·무진입과 비교. 개인 매도일을 몰라도 구조 기반 기회 추적 |
| 압축 후 돌파/상대강도 개선 | 직전 변동성 압축, 과거 고점 돌파, 거래량·RS 변화 | 실패 돌파와 미돌파 유사군 포함, 다음 시가 갭 후에도 손익비가 남는가 |
| 갭·이벤트 이후 지속 | 확정된 당일 갭/마감 위치·volume, 알려진 이벤트 시각 | 갭 메움·되돌림 대조; 새 이벤트 데이터는 시점 계약 확보 후만 |

먼저 baseline이 이 사건군에서 어떤 신호를 언제 냈는지 확인한다. “큰 상승” label은 고정된 미래 horizon/초과수익으로 연구용 정의하되 feature에는 절대 넣지 않는다. trend 초기·중기·말기는 사후 꼭짓점 대신 당시까지 상승 기간/고점 거리/MA 관계로 정의한다. 유동성·규모·국면이 유사한 대조군을 포함하고 표본 추출률/가중치를 남긴다. 사후 승자에서 얻은 특징은 발견 데이터에서만 사용하고 다음 구간에서 반복성을 검증한다.

### R4 — 시장 환경 추가 데이터의 효용 검증 (M, 조건부)

- 목표: 현재 SPY/QQQ 추세+SPY 변동성 모델의 구체적 오류를 줄인다.
- 현재: 금리·VIX·시장 폭·섹터·경제 이벤트는 미구현.
- 필요성: 기존 모델의 어떤 실패를 설명/예방할지 측정된 경우에만 수행한다.
- 범위: 동일 가격 자료에서 시장 폭/섹터 RS 우선, 이후 VIX·금리/채권·발표 이벤트를 한 종류씩 ablation. data metadata에 observation_time, released_at, revision/vintage, ingested_at/known_at을 보존하고 availability lag를 적용한다. 수정 확정값을 과거에 사용하지 않는다.
- 산출물: 추가 비용·coverage 손실 대비 out-of-sample 개선 카드, 채택 또는 폐기 판정.
- 완료: baseline-only 대비 사전 지정 비용 후 주지표/위험의 유의미한 개선을 미사용 구간에서 비교하고 반복 가능 여부를 보고. 개선 없으면 미채택으로 종료.
- 검증: release/revision 미래 오염 테스트, stale/missing fallback, 동일 split·비용·trial 통제, regime별 표본 불확실성.
- 의존성: R1의 오류·R3 실험 통제; 시장 폭은 R2의 PIT 관측 범위 필요.
- 병목: 과거 발표 vintage 확보, 공급 비용, 신호 희소화.
- 보류: 오류 근거·PIT vintage·개선 가능성이 없으면 보류. 옵션 체인·뉴스 NLP·유동성 대체지표의 대량 수집은 마지막 조건부 후보다.

### R5 — 증거에 연결된 Champion/Challenger 승격·강등 (L)

- 목표: 연구 결과가 엄격한 절차를 거쳐 제한적으로 추천을 개선한다.
- 현재: `promotion_gate`는 순수 fail-closed 함수이며 evidence builder/승격 writer는 없음.
- 필요성: 수동으로 가장 좋아 보이는 trial을 고르거나 미검증 자동 승격하는 일을 방지한다.
- 범위: evaluation/validation/experiments 재사용, 실제 근거·출처를 연결하는 evidence builder, holdout 사용 원장, 버전 있는 gate, 제한 활성화 및 강등 이력. 평가 탈락/미측정/측정통과를 구별한다.
- 산출물: Champion vs Challenger 비교 보고서와 이유 있는 유지/거절/관찰/제한 활성화 결정. 사용자 매일 모델 관리 없이 반복.
- 완료: 모든 필수 gate evidence와 정책 버전이 재현 가능하고 미측정·부정적·오래된 증거는 거절, fresh shadow 통과 후에만 유효시각 이후 전략 전환, tail/비용/완전성·운영 악화 시 축소/중단·검증된 이전 버전 복귀가 테스트됨. 첫 challenger 실패도 정상 종료.
- 검증: 누락/위조 ID/서로 다른 universe·비용·기간 혼합 거절, OOS 재사용 차단, 이중 승격 멱등성, immutable 보존, pause 연속성, 실측 shadow 비교.
- 의존성: R1 portfolio 및 결과 회계, R3 미사용 OOS·실험 기록, 필요한 PIT/상폐 데이터. R4는 필수 아님.
- 병목: 표본/국면 확보는 개발로 해결 불가. 현재 무료 과거 자료만으로 gate 충족 불가.
- 보류: 충분한 증거가 없으면 gate infrastructure만 완료하고 자동 활성화는 차단한다. 후보가 늘어도 검증 기준을 낮추지 않는다.

### R6 — 소액 실전 검토와 장기 무인 운영 (M + 실제 관찰)

- 목표: 모의 집행과 실제 실행의 차이를 측정하고 사용자 위험을 제한한다.
- 현재: 실체결 원장·다주 무인 로그·실전 위험조정 성과 없음.
- 필요성: paper 손익과 실제 순수익 사이 간극을 검증해야 최종 목표를 평가할 수 있다.
- 범위: 스케줄러/장애 감지·복구·백업 복원, read-only 체결내역 import의 최소 경로, 사용자 지정 손실 예산·총/종목 노출 한도·집행 조건·중단 규칙. 초기 레버리지/집중 확대 제외, 자동 주문 없음.
- 산출물: 실전 검토 체크 결과, 실제 fills 대비 paper 차이, 실제/가상 분리 성과, 예외 때만 개입하는 운영 보고.
- 완료(운영): 사전 등록한 연속 20 XNYS sessions의 예정 실행을 모두 설명하고 신규 추천 생성 또는 명시적 중단/장애 보고, silent failure·중복 추천·stale 전송 0, 프로세스 종료/네트워크/복구/백업 restore 검증. 이 20일은 초기 운영 기준이지 장기 수익성 증거가 아니다. 이후 60 sessions 및 실제 장애에서 지속 관찰한다.
- 완료(실전 검토): frozen 전략의 미사용 확인 평가+fresh paper/forward 근거, 적격 결과 완전성 및 자본 기준 비용 stress/위험·SPY 비교가 사전 기준 충족, 집행 가능한 진입/청산 정의, 사용자가 자본/최대 허용손실을 정하고 최종 거래 판단. 전략 변경 없는 baseline에도 같은 수준의 실전 검토가 필요하다. R5의 자동 승격 기능 자체를 기다릴 필요는 없지만 그 증거 기준을 우회하지 않는다.
- 검증: gap/미체결/중첩/비용/계좌 잔고 reconciliation, 손실 한도 도달 때 신규 추천 차단, 실패 후 이중 집계 방지. fills 데이터 없으면 실전 수익을 보고하지 않는다.
- 의존성: R0+R1, 실제 미래 기간·사용자의 예산과 실행 선택. 시장 확장/거시/자동 연구 전체 완성은 필수 아님.
- 병목: 실제 사용자 체결과 모델 가정 차이, 수익 기회 부족, PC 가동률, 배당·상폐 회계, 손실 감내 한도.
- 보류: 증거 부족·실전 비용으로 edge 소멸·회계/운영 오류면 paper/NO TRADE 유지. 실전 시작일이나 수익을 약속하지 않는다.

### 순서와 병행

```text
지금 R0 → 매일 보고 및 forward 축적 ───────────────→ 지속
       ├→ R1 baseline 판단 + paper ──────────────→ R6 실전 검토
       ├→ 좁은 R3 연구 (운영과 격리) ─┐
       └→ R2 관찰 범위 → 넓은 R3 ────┼→ R5 제한 승격/강등
                     R1 오류 → R4 ──┘  (R4는 선택)
```

R0 개발 후 future evidence만 기다리는 기간에는 R1·제한 R3를 진행한다. R2/R4는 데이터/비용 효용 gate를 통과한 범위만 추가한다. 이는 실행 시 여러 에이전트나 분산 서비스를 요구하는 계획이 아니다.

## 6. 다음 작업 우선순위

**첫 마일스톤은 R0: 일일 관찰 제품과 고정 baseline 증거 수집 시작이다.**

현재 baseline의 구조적 차단은 대부분 해소됐고 후속 OOS와 실패 분석도 이미 로컬에 있다. 같은 분석을 반복하거나 즉시 ticker-conditioned challenger를 만드는 것보다 운영 보고서를 usable하게 만들고 실제 미래 기록을 시작하는 편이 사용자 효용과 검증 모두에 기여한다. forward 시간은 나중에 개발로 되살릴 수 없다.

R0 다음 구현은 R1의 최소 paper/평가 분모 정리다. 배당 v4 전체 지원, 전시장 full-history 수집, 거시·AI 가설 생성은 먼저 해야 할 근거가 없다. 다만 R0 실측에서 holding 배당/데이터 pause가 지속 운영을 막으면 해당 blocker를 수치로 기록하고 최소 계약 작업을 R1에 편입한다. NO TRADE를 없애려고 guard를 풀지 않는다.

R0의 자세한 모듈 범위·불변조건·인수 테스트·납품 형식은 [다음 세션 작업 명세](docs/FIRST_MILESTONE.md)에 별도로 고정했다.

## 7. 사용자에게 제공할 요약

- **지금:** 8개 종목의 고정 모멘텀 후보와 근거·위험 참고값을 계산하고, 이후 가격 결과를 추적할 수 있다. 로컬 최신 저장 운영 결과는 과거 NO TRADE 1일이며, 검증된 알파나 스스로 개선하는 시스템은 아니다.
- **다음 단계 후:** 매일 오늘 자료인지 확인된 보고서로 후보 또는 거래하지 않는 이유를 보고, 장애와 증거 축적 상태도 알 수 있다. 매일 전략이나 일지를 관리할 필요를 줄인다.
- **매매 판단 활용:** 현재 CLI도 한계가 명시된 참고 정보로 읽을 수 있다. R0부터 정기적인 관찰·판단 보조, R1부터 명시적 가상 자본의 모의매매가 가능하다. 수익성이 검증된 매매 근거로 삼거나 소액 실전을 검토하는 시점은 R6의 증거·운영·위험 기준 충족 이후다. 추천이 나온다는 사실만으로 그 기준을 충족하지 않는다.
- **남은 주요 단계:** 일일 운영 → 자본 기준 baseline 평가 → 넓은 종목/실패 사례 관찰 → 제한 가설 검증 → 증거에 따른 전략 전환. 거시·옵션 등은 개선이 필요할 때만 추가한다.
- **가장 큰 불확실성:** 현 성과가 특정 시기·NVDA/AVGO에 집중돼 재현되지 않을 가능성, 선택적 누락과 과거 PIT 한계, 실제 비용·자본 제약으로 edge가 사라질 가능성이다. 연구를 늘려도 유효한 전략을 찾지 못할 수 있다. 이를 숨기지 않고 기존 전략 유지나 현금 보유로 종료할 수 있어야 한다.
