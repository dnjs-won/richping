# 다음 Codex 세션 작업 명세 — R0

작성일: 2026-09-20. 상태: **구현 대기**. 작업명: **일일 관찰 보고서와 고정 baseline forward 운영 시작**.

## 바로 사용할 구현 요청

> C:\richping의 AGENTS.md, PROJECT_SPEC.md, ROADMAP.md, PROJECT_STATUS.md, docs/DESIGN.md와 이 명세를 읽고 R0만 구현하라. 현재 Git/로컬 작업을 먼저 확인하고 보존하라. 기존 baseline의 투자 판단과 M2-1B feature/v3 outcome/평가 정책/threshold는 변경하지 말라. 매일 읽기 쉬운 shadow 보고서, freshness와 장애 구분, 운영 시도 기록, 분리된 forward 증거 요약을 제공하라. 기존 코드와 평가 함수를 재사용하고 아래 인수 조건을 검증하라. 연구 전략·universe 확대·배당 v4·paper 원장·자동 승격·자동 주문은 이번 범위에서 제외한다. 구현 완료와 실제 운영 확인/장기 증거 미확보를 구별해 보고하라.

## 해결할 문제와 현재 기준

CLI `daily`는 sync→track→shadow scan→JSON 저장/텍스트 출력까지 가능하다. `scripts/daily.ps1`에 lock이 있고 수동으로 OS 작업 등록이 가능하지만 등록·연속 운영은 확인되지 않았다. 기본 운영 DB에는 2026-09-14 shadow NO TRADE 1건만 있으며 최신 M2-1B 단위 증거는 별도 DB에 있다. 수익성은 INSUFFICIENT EVIDENCE다.

현재 main 기준 `26f565a`, 전략 ID `baseline-v1-c202598ad5eb5bbe`. 후속 세션은 실제 HEAD를 다시 확인한다. `code_hash()`는 패키지 전체 Python 파일을 포함하므로 보고 기능 수정도 새 model_id를 만든다. 이 ID를 과거 ID로 가장하거나 code_hash 규칙을 임의로 바꾸지 않는다. 이번 구현 전후 동일 입력의 **투자 판단 내용**은 같아야 하지만 provenance ID가 달라지는 것은 정상이다.

R0는 알파 승인이나 자동 승격 작업이 아니다. 사용자는 최신 후보/NO TRADE와 위험·증거를 매일 확인하고 시스템은 실제 미래 관찰을 시작한다. 추천 0건이어도 기준을 충족하면 R0 개발 완료다.

## 작업 범위와 모듈

1. **읽기 쉬운 일일 보고 계약** — `pipeline.format_report`, `cli` 및 필요하면 작은 보고 helper. 기존 immutable run body를 새 형식으로 덮어쓰지 말고 별도 파생 보고서를 만든다. JSON 기계 출력 호환성을 보존하거나 새 envelope schema를 명시한다. 최소 로컬 Markdown/텍스트와 JSON을 원자적으로 생성한다. `--db`를 바꾼 연구 실행이 운영 최신 보고서를 덮지 않도록 출력 경로/역할을 분리한다.
2. **실행 시도·freshness 기록** — 수집 전부터 시작/종료/오류 단계를 남긴다. 수집 실패는 runs 생성 전에도 일어날 수 있으므로 runs만 읽어 성공률을 계산하지 않는다. 기존 구조화 로그를 재사용하고 필요하면 작은 시도 manifest를 추가한다. 중복된 로그 플랫폼/복잡한 schema는 만들지 않는다.
3. **forward 관측 요약** — 저장된 실제 shadow runs와 outcomes를 model/mode/source/quality/계약별로 분리한다. 기존 `track`/적격성 함수를 재사용한다. read-only summary가 관측을 새로 저장하지 않게 책임을 나눈다. evidence 화면을 얻으려고 `validate`를 매일 돌리지 않는다.
4. **운영 진입점** — `scripts/daily.ps1`와 최소 스케줄러 설정/점검 절차. 프로젝트 경로·Python 경로·작업 시간대·종료 코드·실행 계정·PC 절전 한계를 명시한다. 실행 시 거래소 calendar와 실제 cutoff로 최신 완료 session을 결정한다. 고정 UTC 오프셋으로 미국장 시간을 계산하지 않는다. 작업 등록은 명시적으로 수행·확인한 경우에만 완료라고 기록한다.
5. **운영 시작 자료** — 기존 DB를 복사로 덮거나 M2-1B metadata를 소급 삽입하지 않는다. 현재 adapter로 정상 `sync`를 통해 새 immutable vintage를 확보하고 최신성/action capture/단위 증거를 확인한다. 이전 운영 자료를 보존한다. 처음부터 별도 forward DB를 쓰는 경우 이유·시작시각·구 DB 참조를 기록하고 이전 위험 latch를 피하려는 용도로 사용하지 않는다.

Telegram은 후속 선택 전달 기능이다. R0 핵심 완료에 필요하지 않다. 토큰·수신처가 없으면 로컬 보고서를 완성한다. 향후 명시적 발송 지시와 수신처가 있을 때만 외부 전송을 실행하며 비밀정보는 저장소/로그에 넣지 않는다. 현재 작업은 채널 개설이나 임의 메시지 발송 요청이 아니다.

## 보고서 필수 내용

| 영역 | 필드/행동 |
|---|---|
| 시점 | 대상 XNYS session, 생성/실행 cutoff, 최신 수집시각, 다음 진입 session, 유효기간/다음 개장 경과 여부 |
| 실행 상태 | 성공/실패/미실행/진행 중/과거 보고서 재표시. 성공한 옛 보고서와 오늘 실패를 동시에 구분 |
| 판단 상태 | 후보 있음 / 정상 NO TRADE / 위험 중단 / 데이터 장애. 장애를 전략의 부정적 기대값으로 번역하지 않음 |
| 정체성 | model/config/code/data ID, mode, quality, outcome/feature/evaluation contract, 운영 관찰 시작 ID/시점 |
| 후보 | ticker/rank/score/기여요인, 다음 시가 관측과 5-session 종가 기준, 종가 Entry ref·ATR stop/target은 참고값이라고 표시 |
| 기대값 | 날짜 평균 expected return, expected loss/RR, 경험적 win frequency, 표본 수/독립 signal dates/CI, research calibration 한계 |
| 무추천 | 시장·위험·무결성·raw signal·calibration의 실제 사유 및 관련 분모. 추정한 원인을 만들어내지 않음 |
| 결과 | 전체 horizon COMPLETE/PENDING/UNRESOLVED와 별도의 holding-period eligible/excluded 수, 미해결/제외 이유·버전 |
| 근거 수준 | SYNTHETIC / RESEARCH / FRESH_SHADOW 등 출처, Alpha INSUFFICIENT EVIDENCE, 포트폴리오 수익 N/A |
| 운영 | 최근 예정 실행과 실제 시도·성공·지연·실패, 마지막 정상 수집·관찰, 필요한 예외 조치 |

NO TRADE는 임의의 매수 후보를 대신 제공하지 않는다. 기존 JSON만으로 불충분한 사유는 결과를 바꾸지 않는 진단 필드로 노출한다. 시장 휴일/주말에 직전 session 보고서를 재표시하는 것은 허용하되 새 추천·새 forward 관측 날짜로 세지 않는다. 늦은 실행은 신규 후보를 과거 시점에 발행하지 않는다.

초기 알림은 최종 보고서 한 건이면 충분하다. 사용자에게 내부 DB/통계 설정 조작을 일상 작업으로 요구하지 않는다. 단, 데이터 장애와 성과 pause는 사실대로 설명하며 자동 리셋으로 숨기지 않는다.

## 불변조건과 버전 연속성

- 기존 datasets/bars/members/model_versions/recommendations/확정 outcomes를 UPDATE/DELETE하지 않는다. old report/body, v1/v2/v3 의미와 `cash_action_review_v1`을 유지한다.
- Feature dividend normalization ≠ Outcome dividend accounting. 결과 배당을 정상 COMPLETE로 바꾸거나 legacy v2를 현재 증거에 넣지 않는다.
- signal, score, calibration pooling/경계/embargo, 비용, risk threshold, universe, top-k는 그대로 둔다. 변경할 필요가 발견되면 구현을 확대하지 말고 blocker와 최소 후속 계약을 기록한다.
- 보고 변경 전후 같은 frozen 입력의 후보/점수/calibration/NO TRADE/위험 판단을 비교한다. 과거 snapshot byte는 그대로 보존하고 신규 model ID와 대응 관계는 별도 manifest에 기록한다.
- 구현 시작 때 기존 risk_state를 조회한다. 이전 버전의 성과 PAUSED가 있으면 새 model_id라는 이유로 정상 활성화하지 않는다. 승인된 재개 근거가 없으면 운영 시작을 차단하고 보고한다. 근거 없는 위험 상태 합산/이전이나 과거 ID 위조도 하지 않는다.
- 실제 shadow signal cutoff와 bar/action/membership known_at은 유지한다. 과거 research calibration은 fresh forward 성과와 분리한다. 과거 자료가 포함된 새 수집일을 과거 전 기간의 fresh 관측으로 세지 않는다.
- 운영 summary는 recommendation_id·holding horizon·평가 vintage 규칙으로 중복을 막는다. pending/미해결/비적격을 숨기거나 0%로 바꾸지 않는다. 연구 결과가 운영 위험 상태에 들어가지 않는다.

## 구현 순서

1. 현재 Git 상태, 코드/config/model ID, 실제 DB/산출물·risk_state를 read-only 점검하고 보존 목록을 만든다. `var/`의 기존 validation/failure 자료를 새 실적으로 덮지 않는다.
2. 최소 report/attempt schema와 출력 위치를 정하고 fixtures로 성공·정상 NO TRADE·실패·stale·휴일·늦은 실행을 검증한다. strategy 로직에 진단을 추가한다면 투자 판단 동일성을 먼저 확보한다.
3. forward 요약 및 wrapper/스케줄러 점검을 연결하고 테스트를 완료한다. 임시 DB를 쓰며 기존 운영 데이터에 테스트를 실행하지 않는다.
4. 실수집과 다음 개장 전 운영 실행을 수행할 수 있는 시점에 한 번 확인한다. 필요한 환경 권한/네트워크가 막히면 구체적인 실패와 아직 못 한 검증을 기록한다. 미래 일일 운영을 압축·합성해서 완료로 만들지 않는다.
5. 운영 시작 manifest, 보고 예시, 실행/복구 절차 및 PROJECT_STATUS를 갱신한다. 이후 자동 수집 기간 동안 R1 또는 격리된 R3를 진행할 수 있다.

## 인수 테스트

| 항목 | 통과 기준 |
|---|---|
| 판단 보존 | 같은 입력·시점·위험 상태에서 기존/신규 투자 판단 일치, ID 변화는 명시 |
| immutable | 기존 DB/snapshot/outcome/report 원본이 유지됨; 별도 새 산출물만 추가 |
| 실제 시점 | 미래 bar/event/capture/membership이 후보·통계에 유입되지 않음, 다음 개장 지난 신규 추천 거부 |
| report freshness | 수집 실패 후 옛 성공 artifact가 오늘 성공으로 표시되지 않음; 조회만으로 실패가 사라지지 않음 |
| 원자성 | 보고 생성 중 종료/replace 실패 때 기존 완성본 보존, 실패 시도 표시, 불완전 파일을 최신으로 읽지 않음 |
| 중복/재시도 | 동일 run/휴일 재실행에서 추천·성과·관측 날짜 중복 없음, FAILED 재시도 추적 |
| RUNNING/lock | wrapper 동시 실행 방지, 활성 프로세스가 있을 때 복구 금지, 안전 확인 없는 자동 recover-runs 금지 |
| 관측 | PENDING 만기 후 결과 관찰, 확정 outcome 재사용, eligible/excluded/UNRESOLVED 전체 분모 보존 |
| provenance | 연구·합성·옛 버전 결과가 fresh shadow 집계나 운영 위험 상태로 혼입되지 않음 |
| 통합 | `.venv\Scripts\python -m pytest`, CLI `--help`, `git diff --check` 통과; 기존 경고를 숨기지 않음 |

추가 테스트는 위 위험을 다루며 formatter 문자열 전체를 기계적으로 복제하는 테스트는 피한다. 기존 검증 엔진을 별도 구현하지 않는다. demo는 원래 `var/demo*`를 덮는 기본 실행 대신 격리된 작업환경이 필요한 경우에만 사용한다.

## 종료 및 인계

- **개발 완료:** 위 인수 조건 및 로컬 보고서/운영 관찰 기능 통과.
- **운영 시작 확인:** 실제 다음 개장 전 성공 또는 정상 NO TRADE 한 번, 수집판/시각/버전/로그·스케줄러 상태 확인. 실패하면 개발 완료와 운영 미확인을 분리한다.
- **미래 증거 대기:** 다일 무인 안정성·수익성·fresh 표본 확보는 미완료로 남긴다. R6의 초기 20 sessions 운영 기준과 성과 gate를 섞지 않는다.
- 납품: 변경 파일/판단 불변 근거, 테스트·실행 결과, 성공 및 장애 보고 예시, 데이터 보존 근거, 운영 시작시각과 버전, 미확인 사항·다음 R1 작업. 날짜 약속이나 Alpha 완료 선언 없이 보고한다.
