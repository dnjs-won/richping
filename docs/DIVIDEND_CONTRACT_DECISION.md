# M2-1A-R1 검수와 현금배당 지원 계약 결정

결정일: 2026-09-16. 역할: 설계 감독·검수.
상태: **설계 결정 및 다음 작업 지시. 아래 v3·평가 정책·수집 변경은 아직 구현되지 않았다.**
최상위 요구사항은 `PROJECT_SPEC.md`. 현재 구현 계약은 `docs/DESIGN.md`이며, 그 v2 설명은 역사적 계약으로 보존한다. 이 문서는 다음 구현의 변경 계약을 명시한다.

## A. 국소 수정 검수: PASS

판정 범위는 R1의 네 가지 국소 결함이다. **M2-1A 전체는 CHANGES REQUIRED**이며 일반 현금배당 실데이터 지원 승인으로 해석하지 않는다.

| 확인 항목 | 실제 근거 | 판정 |
|---|---|---|
| 버전 없는 보고서 | `richping/pipeline.py:125`의 `format_report()`는 키 부재만 `v1_price_only`로 표시. 명시적 null/빈 문자열은 unsupported | PASS |
| 버전 없는 계산 | `richping/engine.py:47`의 `observe()`는 키 부재만 v1. 배당이 있으면 기존 사유로 UNRESOLVED, 없으면 기존 가격 수익 계산. `tests/test_dividends.py:333` 검증 | PASS |
| 알 수 없는 명시적 버전 | observe의 명시적 dispatch가 UNRESOLVED / `unsupported_outcome_version` 반환. `v999_future`, 빈 문자열, null, v1 오타에 대해 수익 필드 없음 및 track 성과 rows 제외를 검증 (`:400`) | PASS |
| 기존 확정 기록 보존 | Store의 UPDATE/DELETE 금지 trigger 유지, track의 INSERT OR IGNORE 유지. 임시 DB에서 기존 v1 결과 및 recommendation 보존 테스트 통과 | PASS |
| history/track 통합 | `tests/test_dividends.py:525`에서 ALFA 후보와 history 행 존재를 무조건 assert. 동일 session/ticker/end/version의 실제 `Engine.history`와 `track()` 순수익, 배당 1.50, 비용을 비교 | PASS |
| 기본 pytest | 아래 명령 1회 실행, exit 0, 63 passed / 1 warning, 15.86초 | PASS, 경고 잔존 |

실행 명령: `.venv\Scripts\python -m pytest`.
환경: Windows, Python 3.13.7, pytest 9.1.1. 실패·skip 없음.
경고: `var/.pytest_cache/v/cache/nodeids` 기록 시 WinError 5 / PytestCacheWarning. 테스트 실패를 일으키던 고정 basetemp 문제는 재현되지 않았으나 캐시 권한 경고까지 제거된 것은 아니다.

`tests/conftest.py`는 PID + UUID를 포함한 실행별 임시 경로를 사용한다. `pyproject.toml`에는 고정 `--basetemp`가 없고 cache_dir만 남았다. `PROJECT_STATUS.md:21`에는 Gemini의 기본 명령 연속 통과 요약이 있다. 별도 연속 실행 원문 로그는 확인하지 못했으므로 이번 1회 독립 실행과 구분한다. 현재 Git 기준은 첫 commit이며 diff에 최초 M2-1A와 R1 수정이 함께 포함되어 있어 R1만의 독립 commit diff는 없다.

유의: 현재 track은 저장된 outcome을 읽어 반환하는 대신 다시 observe한 값을 집계한다. 이번 PASS는 기존 행이 덮어써지지 않는다는 판정이다. 아래 평가 정책을 구현할 때 저장 사실과 현재 적격성 판정을 분리해야 한다. Scenario 10 마지막 calibration assert는 키 존재만 확인하지만, 요청된 history/track 순수익 직접 비교는 앞부분에서 무조건 수행된다.

이번 검수는 제품 코드·원본 DB·기존 보고서를 수정하지 않았다. 전체 테스트는 1회만 실행했다. 아래 실데이터 재현은 미해결 분류 결함 확인을 위한 별도 조회이며 원본 Store를 열지 않았다.

## B. 1차 자료와 실데이터 재확인

1. [Costco 2023-12-14 발표](https://investor.costco.com/news/news-details/2023/Costco-Wholesale-Corporation-Reports-First-Quarter-Fiscal-Year-2024-Operating-Results-And-Announces-A-Special-Cash-Dividend-Of-15-Per-Share/default.aspx)는 주당 $15를 특별 현금배당으로 명시한다. 기준일은 2023-12-28, 지급일은 2024-01-12다.
2. [OCC memo #53778, MIAX 게재본](https://www.miaxglobal.com/sites/default/files/alert-files/COST_Distribution_53778.pdf)은 해당 사건의 배당락일을 2023-12-27로 명시한다. 옵션 조정 공지는 여기서 날짜·사건 확인용이며 전체 주식 권리 계약을 대신하지 않는다.
3. [FINRA Rule 11140](https://www.finra.org/rules-guidance/rulebooks/finra-rules/11140)은 지정 ex-date, 25% 이상 분배, 정보 지연 등의 별도 날짜 규칙을 둔다. 이는 프로젝트의 20% 분류 근거가 아니며 일반/특별 배당 판별기가 아니다. 현행 T+1 규칙은 2024-05-28 시행으로, 2023년 사건에 현재 기준일 산식을 소급하면 안 된다. 실제 공지된 ex-date를 사용해야 한다.
4. [yfinance 공식 history 문서](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html)와 [공식 Price Repair 문서](https://ranaroussi.github.io/yfinance/advanced/price_repair.html)는 가격·배당 조정, 통화 단위 오류, 배당락일 오류, Capital Gains 중복 등의 수정 경로와 오탐 가능성을 설명한다. repair=False는 검증 완료를 뜻하지 않으며 repair=True도 사건 검증 인증이 아니다.
5. 설치 버전은 yfinance **1.7.0**. 설치 소스 `scrapers/history.py:378,438,449,517` 및 `utils.py:576` 확인: ETF/MUTUALFUND에 Capital Gains를 노출하며, 배당 통화 불일치 시 repair=True일 때만 FX 변환을 시도하는 경로가 있다. history의 배당 currency 열은 이후 제거된다. [공급자 소스](https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/history.py)도 참고했지만 실제 실행 판단은 설치 소스에 근거한다. Richping `data.py:159,174,199`는 repair=False로 수집하고 Dividends/Stock Splits만 Bar로 옮기며 새 Yahoo 데이터셋 전체에 VERIFIED_DIVIDEND_BASIS를 붙인다. 일반/특별 분류, 사건별 권리 근거는 보존하지 않는다.

실제 조회는 별도 임시 yfinance 캐시에서 다음 설정으로 수행했다. 샌드박스 네트워크 제한 후 승인된 조회로 재실행했다. 역사 연구 재현이며 당시 known-at의 증명이 아니다.

```python
yf.Ticker("COST").history(
    start="2023-12-22", end="2024-01-04",
    auto_adjust=False, back_adjust=False,
    actions=True, repair=False, raise_errors=True,
)
```

| 관측 / 현재 v2 재현 | 값 |
|---|---:|
| 2023-12-27 Close | 666.7999877929688 |
| 같은 날 Dividends | 15.0 |
| 배당 / 종가 | 0.0224955013116426 = 2.24955% |
| quote currency | USD |
| 가상 신호일 / 진입일 / 5-session 종료일 | 2023-12-22 / 2023-12-26 / 2024-01-02 |
| observe 상태 / 버전 | COMPLETE / v2_ordinary_cash_dividend |
| dividend_cash | 15.0 |
| return_basis | ordinary_cash_dividend_entitlement_gross_unreinvested |
| net_return | -0.012935922563953593 |

조회한 일봉으로 메모리 Dataset을 만들고, 현 adapter와 동일한 dividend_basis를 붙여 현재 observe에 전달했다. 실제 추천 발생이나 투자 성과를 주장하는 재현이 아니다. **특별배당이 작은 비율로 일반배당 COMPLETE에 들어가는 결함은 재확인됐다.** 이 사건에서 산술이 맞을 수 있다는 사실은 일반배당 분류가 맞다는 증거가 아니다.

## C. 확정 정책: A — 근거가 확인된 일반 현금배당만 허용

B의 현금분배 확장은 선택하지 않는다. 권리·단위·행사 조건을 검증할 수 있으면 기술적으로 더 넓은 계약은 가능하지만, 현재 공급 경로에는 그 사건별 증거가 없다. 명칭을 넓혀도 데이터 부족은 해결되지 않고 특별분배까지 지원 표면만 늘어난다.

**현재 확보·검수된 자동 실데이터 경로에서 일반 현금배당을 적격 처리할 수 있는 경로는 없다.** Yahoo의 Dividends 금액과 날짜, repair 설정, 미국 ticker, USD quote, 배당/종가 비율, 반복 지급 패턴만으로는 부족하다. 모든 무료 공급자가 불가능하다는 주장은 아니다. 새 공급자 탐색·유료 계약·운영자 종목별 분류 입력은 이번 범위 밖이다.

지원 목표는 A로 고정하되 첫 변경은 아래 **v3_cash_action_guard**로 한정한다. 이 버전은 배당 지원 버전이 아니라 검증되지 않은 기업행동의 정상 성과 진입을 차단하는 가격 수익 계약이다. 현금배당의 적격 산술을 다시 활성화하려면 사건 증거 경로를 먼저 검수하고 별도 v4 계약으로 구현한다. v3를 나중에 조용히 배당 지원 버전으로 바꾸지 않는다.

### 향후 일반배당을 허용하는 최소 사건 증거

- 대상 증권 식별자·거래시장·거래소 시간대, 사건 식별자, 명시적 `ordinary_cash` 분류. 분류 제공자와 그 정의가 확인되어야 한다. `Dividends`라는 열 이름만으로 분류하지 않는다.
- 발행사/거래소/권리 조건을 제공하는 공급자의 출처 URL 또는 문서 ID, 해당 내용의 보존본/해시, 발표 시각과 실제 수집 known_at, 공급자·adapter 버전. 분류와 ex-date의 출처가 다르면 각각 보존한다. URL이나 verified boolean만 입력해 검증된 것으로 취급하지 않는다.
- 지정 ex-date, record-date, payable-date 및 표준 권리 적용 근거. 현금 선택권·행사·due-bill·지연된 ex-date·분배 취소/수정 등의 조건 유무. 원문이 해당 필드를 생략한 경우에는 문서화된 공급자 사건 계약으로 그 의미를 설명할 수 있어야 한다.
- 세전 주당 현금 금액과 그 통화, 가격 quote 통화와 표시 배율(달러/센트 등), 가격/배당 각각의 주식 수 기준 및 split 조정 기준·기준시점, 둘을 같은 단위로 연결하는 근거. 배당 재조정된 가격에 현금을 더하는 이중 계산 금지. 이번 범위는 FX 환산·분할 회계를 지원하지 않는다.
- 겹치는 미지원 사건이 없고 가격 vintage가 frozen snapshot의 참조 가격과 일치해야 한다. 단위 정렬과 사건 분류·권리 확인은 별도 판정이다. 단위가 맞아도 특별배당일 수 있고, 일반배당이어도 다른 통화일 수 있다.

표준 규칙이 확인된 일반 현금배당만 진입일 시가 매수 기준으로 `entry_session < ex_date <= end_session`의 권리를 합산한다. 진입일 배당락은 제외, 최종일 배당락은 포함한다. 지급일 입금이 아닌 세전·비재투자 권리 수익이며 비용은 한 번 차감한다. MFE/MAE/barrier는 가격 진단이다. **확인되지 않은 사건은 진입일에 있더라도 먼저 격리**하며, 금액을 제외했다는 이유로 권리 검증을 생략하지 않는다.

특별/청산/자본환급/Capital Gains/선택형·비현금 분배 및 due-bill·비표준/불명확 권리는 금액에 무관하게 격리한다. 분할도 계속 미지원이다. 하나의 사건이 여러 현금 항목으로 표시되면 검증 없이 합치거나 중복 제거하지 않는다.

### 실패 폐쇄 사유

아래는 정책상의 사유 목록이다. 첫 작업에서는 v3와 수집에 실제 필요한 부분만 구현한다. 세부 분류·단위 사유는 사건 증거 경로를 여는 후속 작업에 배정한다.

| 사유 | 조건 / 배정 |
|---|---|
| `unsupported_outcome_version` | 명시적 미지원·비정상 버전. 현행 유지 |
| `unverified_cash_dividend_event` | v3에 현금배당 존재. legacy verified 문자열이나 임의 사건 메타데이터로 우회 불가. 첫 작업 |
| `unsupported_capital_gains_distribution` | 해당 창에 Capital Gains 비영(非零) 값 존재. Dividends와 동시 존재해도 격리. 첫 작업 |
| `action_capture_unknown` | 필요한 공급자 action 필드의 수집 범위/가용 여부가 미확인. 과거에 버린 값을 0으로 추정하지 않음. 첫 작업 |
| `stock_split_requires_accounting` | 분할 존재. 첫 작업에서도 유지 |
| `unverified_dividend_classification` / `unverified_dividend_source` | 향후 적격 경로에서 분류 또는 그 출처 부족 |
| `unverified_dividend_entitlement` / `nonstandard_dividend_entitlement` | 권리 조건 미확인 / 비표준 확인 |
| `unsupported_special_distribution` | 특별·청산·자본환급 등 확인된 미지원 종류 |
| `unverified_currency_or_unit` | 통화·가격 표시 배율·주당 조정 기준 근거 부족 |
| `dividend_currency_mismatch` / `dividend_price_unit_mismatch` | 확인된 통화 차이 / 가격·배당 단위 차이 |
| `conflicting_distribution_evidence` | 출처/사건 금액·날짜·조건 충돌 |

PENDING의 만기·known-at 규칙, 결측 및 price_vintage_changed 규칙은 유지한다. 확정된 UNRESOLVED에는 성과 수익 필드를 채우지 않는다. 미해결 outcome은 분모와 사유별 집계에 남긴다. 공급자의 누락 사건까지 완전하게 탐지한다는 보장은 하지 않는다.

### 버전과 과거 결과의 평가 적격성

- 누락 버전은 v1, 명시적 v1/v2는 각각 원래 산술·실패 조건으로만 재생한다. v2의 20% 로직은 승인된 규칙이 아니라 보존 대상인 옛 의미다. DEFAULT 상수를 v3로 바꿀 때 기존 `elif version == DEFAULT_OUTCOME_VERSION`를 그대로 두면 v2 의미가 바뀌므로 반드시 v2 고유 상수로 분리한다.
- 새 추천·모델·calibration·validation은 v3를 사용한다. code/config/model 식별자를 기존 방식으로 새로 만들고 기존 snapshot의 버전을 덧붙이거나 변경하지 않는다. 옛 recommendation에 v3 outcome을 끼워 넣지 않는다. 현 outcomes PK에는 계산 버전이 없으므로 같은 키로 재계산 결과를 덮어쓰는 설계는 금지한다.
- 계산 상태와 현재 평가 허용 여부를 분리하는 `cash_action_review_v1` 평가 정책을 둔다. **모든 v2 COMPLETE를 현재 승인 성과에서 제외**하고 `legacy_v2_unverified_contract`로 집계한다. 무배당 v2까지 제외하는 보수적 비용을 수용한다. 개별 사건 재인증·수동 예외·과거 DB 수정 없이 알려진 오분류 유입을 확실히 막는 최소 정책이다.
- v1 산술은 유지하되 현재 평가에서 실제로 포착된 Capital Gains 또는 action capture 불명은 별도로 부적격 처리한다. v1의 오래된 입력도 Capital Gains를 버렸을 수 있으므로 없는 메타데이터를 무사건 증거로 승격하지 않는다. synthetic은 별도 품질이며 실데이터 적격성 증거가 아니다.
- 원본 COMPLETE와 저장 body는 보존한다. 현재 읽기/평가 결과에 정책 ID, 적격 수, 제외 수, 사유·버전별 수를 파생 표시한다. 제외를 UNRESOLVED로 원본에 덮어쓰지 않는다. horizon 전체 상태 분모와 holding-period 추천 평가 분모를 구분한다. 제외만 있는 그룹도 출력에서 사라지면 안 된다.
- 기대값·성과·위험 판단·OOS에 부적격 결과가 섞이지 않게 한다. 기존 PAUSED latch를 자동 해제하지 않는다. 현재 부적격 증거가 있으면 운영 scan은 기존 데이터 문제 pause에 준해 보수적으로 멈춘다. 과거 보고서의 저장 숫자와 당시 결정을 고치지 않고, 현재 출력에 역사 기록 및 현재 부적격 안내를 덧붙인다.

## D. Gemini 3.8 Flash High — 지금 실행할 첫 작업 지시문

작업명: **M2-1A-R2 — v3 현금 기업행동 차단과 기존 v2 평가 격리**.
작업 디렉터리: `C:\richping`. 구현 모델: Gemini 3.8 Flash, 추론 High.

AGENTS.md, PROJECT_SPEC.md, docs/DESIGN.md와 이 결정문을 읽어라. 기존 dirty diff는 사용자 작업이므로 보존하라. 아래 첫 작업만 구현하라. 계약 변경이 필요하면 임의로 범위를 넓히지 말고 이유를 보고하라.

### 목표·제외 범위

현재 데이터로 증명할 수 없는 배당을 새 추천의 COMPLETE로 계산하지 않게 하고, Capital Gains 유실과 v2 성과 재유입을 막아라. 무사건 가격 수익 경로는 유지하라. 첫 작업은 배당 지원 활성화가 아니며 모든 v3 현금배당을 격리한다. synthetic에도 v3의 배당 허용 예외를 만들지 않는다.

일반배당 자동 분류기, 금액 threshold 대체 규칙, repair=True 전환, issuer scraper, 종목별 예외, 유료 공급자, 배당 포함 feature 산식, 분할·FX·포트폴리오 회계, 자동 주문, UI, 과거 결과 재작성은 제외한다.

### 수정 모듈·최소 데이터 변경

1. `richping/core.py`: v1/v2 고유 상수와 `v3_cash_action_guard`를 분리하고 새 기본 버전·지원 버전 dispatch를 명시하라. `cash_action_review_v1` 정책 ID를 별도로 정의하라.
2. `richping/data.py`: **Bar 필드와 기존 Dataset hash 직렬화는 변경하지 말라.** 기존 Dataset load 시 metadata를 보충하지 말라. 새 수집판 metadata에 작은 `action_capture` 구조를 추가해 Capital Gains를 보존하라. 기존 JSON metadata 저장을 쓰므로 새 DB 테이블/SQL migration은 필요 없다.
   - 구조에는 schema/adapter/provider 버전, history 옵션, ticker별 instrumentType·quote currency·실제 조회 구간·수집 시각, Capital Gains 열 상태(`present`, `not_applicable_by_provider`, `unknown`), 비영 Capital Gains의 ticker/session/원필드명/금액/known_at을 담아라. 금액은 유한 수치로 검증하며 비정상 값은 수집 실패로 처리하라. 배당 금액·분할은 기존 Bar를 유지한다.
   - Yahoo EQUITY에서 열이 없는 것은 검수한 provider 버전의 instrumentType 동작에 근거할 때만 `not_applicable_by_provider`로 기록하라. 이를 세계의 모든 분배가 없다는 보증이라고 쓰지 말라. ETF/MUTUALFUND에서 열 부재 또는 instrumentType 불명은 unknown. 필드가 실제 존재하면 instrumentType과 무관하게 비영 값을 보존한다. 구간/종목별 capture 정보 없이 데이터셋 전체 complete 선언 금지.
   - metadata에 일반배당 verified를 새로 부여하지 말라. quote currency는 가격 정보일 뿐 dividend currency의 증거로 복사하지 말라. repair 옵션도 검증 상태가 아니다.
   - CSV는 선택적 `capital_gains` 열을 metadata로 보존하고 Bar 생성 전 제거하라. 열 부재는 unknown. synthetic generator는 명시적 synthetic action capture를 만들되 배당 분류 근거로 사용하지 않는다.
   - 증분 수집은 action_capture가 없거나 계약 버전이 다른 이전판에서 전체 새 vintage를 수집하라. Capital Gains 변경/추가도 기존 split/dividend처럼 revision 판단에 포함하라. action sidecar 병합·비교는 순서에 독립적으로 결정론적이어야 하며 기존 first-seen known_at을 유지하라. 이전 metadata의 verified 플래그를 신규판에 무비판적으로 승계하지 말라.
3. `richping/engine.py`: 기존 v1/v2 분기를 그대로 명시적으로 보존하라. 새 v3는 만기·결측·known-at 확인 뒤 창 전체(진입일 포함)의 split, Capital Gains, dividend, capture unknown을 검사한다. 첫 사유 우선순위는 이 순서로 고정하고 해당 사유로 UNRESOLVED 처리하라. 배당 비율 계산과 legacy verified 문자열은 v3 적격성에 영향을 주면 안 된다. 무사건·capture 확인된 창에서만 기존 가격 수익/비용/가격 진단을 계산한다.
   - 기존 61-session feature 창의 action 제외에 Capital Gains/capture unknown도 반영하라. SPY/QQQ benchmark의 알려진 미지원 action도 정상 feature 입력으로 통과시키지 말라. feature의 수학적 정의를 새로 만들지는 말라.
   - 새 signals/history/calibration은 v3로 일치시키고 부적격·다른 계약 label을 섞지 말라. 누락·UNRESOLVED label 수/사유를 기존 결과 보고 경로에 노출하되 수익 표본에 넣지 말라.
4. `richping/pipeline.py`, `richping/cli.py`: 현재 평가 정책을 작은 공용 순수 함수로 만들고 위 C의 v2 전량 제외 및 action capture 정책을 적용하라. `track()`의 `(counts, rows)` 형태는 유지 가능하다. rows에는 적격 holding-period 결과만 넣고, counts에 별도의 `evaluation` 하위 객체로 policy/eligible_complete/excluded_complete/by_reason/by_version 및 제외만 있는 model/mode 그룹 정보를 담아라. 기존 세 상태 수는 horizon 분모로 유지하고 evaluation은 추천 holding-period 분모로 표시하라. 새 정책 전용 테이블은 만들지 말라.
   - 동일 recommendation/horizon/dataset의 확정 outcome이 있으면 그것을 저장 사실로 읽어라. 현재 as_of보다 뒤의 observed_at/end를 이용하지 말고, 과거 as_of 요청에는 기존 시점 규칙을 적용하라. 미확정 부분만 기존 버전으로 관측·INSERT OR IGNORE하라. 원본 상태·body와 현재 평가 판정은 분리하라. snapshot/result 버전 불일치도 부적격으로 표시하라.
   - format_report는 v1/v2/v3를 명시적으로 표시하라. 버전 없는 보고서는 계속 v1이고 명시적 null/빈 값/미지원 버전은 unsupported다. 기존 v2 보고서 출력에는 역사적 기록이며 현재 평가에서 제외된다는 안내를 추가하되 저장된 숫자·파일을 덮어쓰지 말라.
   - scan 위험 입력과 recent_30, evaluate 성과에는 적격 rows만 들어가야 한다. 부적격 제외로 표본이 사라졌다는 이유로 PAUSED를 해제하거나 NORMAL 추천을 허용하지 말라. 계산 버전별 결과를 분리하고 v1/v3을 합친 대표 성과를 만들지 말라.
5. `richping/validation.py`: 새 v3와 동일한 적격 조건을 추천 label·matched SPY·OOS에 적용하고 제외 분모/사유를 보존하라. 통계 함수의 수학이나 walk-forward 분할을 바꾸지 말라. 해당 경로의 `sum(counts.values())`에 nested evaluation 객체가 섞이지 않게 하라.
6. `tests/`와 `docs/DESIGN.md`, `PROJECT_STATUS.md`, 필요시 README만 관련 범위로 갱신하라. 기존 DESIGN의 v2 정의는 deprecated 역사 계약으로 남겨라. 실데이터 배당 지원·M2-1A 전체 완료라고 보고하지 말라. pytest cache 권한 경고는 비차단 참고 사항이며 이 작업에서 환경 ACL 변경이나 임시 폴더 대량 삭제를 하지 말라.

### 결정론적 테스트와 완료 기준

- 작은 비율 특별배당: COST 사건의 날짜/$15와 666.80 수준 가격을 고정 fixture로 사용하라. 네트워크 사용 금지. 보존된 v2 산술은 같은 결과를 유지하되 현재 평가에서는 제외. 같은 입력의 새 v3는 `unverified_cash_dividend_event`이며 net/raw 성과 필드가 없어야 한다.
- 분류 근거 없는 현금배당: 금액이 작거나 dataset에 legacy VERIFIED 문자열이 있어도 v3는 UNRESOLVED. 다른 ticker의 verified 주장, 임의 ordinary 메타데이터, synthetic quality로 우회 불가.
- 진입일·최종일: v3에서 각각 미확인 배당이 있으면 둘 다 격리. 기존 명시적 v2 산술 테스트에서 진입일 제외·최종일 포함·비용 1회 차감은 그대로 유지하라. 검증된 사건의 미래 v4 경계 테스트는 후속 작업에 배정한다.
- Capital Gains: Dividends=0인 단독 사건 및 둘 다 비영인 사건을 mock Yahoo frame/CSV로 입력해 금액 보존, Store round-trip/hash, 해당 창 격리, feature 제외를 검증하라. ETF 열 부재는 unknown, EQUITY의 확인된 provider 비노출은 위 계약대로 구분하라. 음수/비유한 등 잘못된 입력을 정상 0으로 바꾸지 말라.
- 증분: Capital Gains 추가·수정 시 새 vintage, 첫 수집판 미변경, 오래된 capture 없는 이전판은 전체 재수집을 검증하라. 일반 metadata 플래그만 바꿔 과거 유실이 복구됐다고 처리하지 말라.
- 저장·버전: 변경 전 형식으로 만든 fixture DB의 dataset ID, metadata JSON, bar JSON, recommendation snapshot, 확정 v1/v2 outcome body를 전후 동일 비교하라. 실제 사용자 DB를 테스트에 사용하지 말라. 모든 immutable trigger와 재실행 중복 방지가 유지되어야 한다.
- 정책: 수익률이 큰 v2 COMPLETE가 저장된 임시 DB에서 원본 COMPLETE는 남고 현재 적격 성과 수는 0, 제외 수는 1, reason/policy/version은 표시되어야 한다. 제외만 있는 그룹, 알 수 없는 버전, as_of 이전에 아직 알려지지 않은 저장 결과도 시험하라. 제외가 분모에서 사라지거나 위험 완화 근거가 되면 실패다.
- 통합: 무사건 v3의 결정론적 실제 후보를 무조건 확보해 `Engine.history`와 `track()` 순수익을 비교하라. 기업행동을 끼운 동일 창은 history/calibration에서 제외되고 track/validation의 미해결 분모에 남아야 한다. 기존 Scenario 10은 v2 산술 보존과 새 현재 평가 정책을 구분하여 바꾸고 조건부 assert로 퇴행시키지 말라.
- 미래 가격·배당·action sidecar를 바꿔도 과거 signal/calibration이 바뀌지 않는 핵심 시점 불변조건을 시험하라. synthetic 결과는 항상 synthetic으로 남겨라.
- 전체 `.venv\Scripts\python -m pytest`를 1회 실행하고 결과·warning을 그대로 보고하라. 추가 실행은 수정/실패 원인이 있을 때만 한다. `.venv\Scripts\python -m richping --help`는 허용한다. 원본 DB/보고서에 쓰는 기본 demo/scan/sync/validate 명령은 실행하지 말라.

납품 보고에는 변경 파일, 테스트 결과, 과거 데이터 보존 근거, v3 실데이터 배당 COMPLETE가 없다는 사실, 미해결 사항을 구분해라. 제품 변경의 후속 검수 모델은 **GPT-5.6 Sol High**다. 이 결정문에서 승인한 계약을 바꾸려면 **GPT-6 Astra High**의 계약 재검토가 선행되어야 한다.

## E. 후속 작업 — 제목·선행 조건만

| 제목 | 선행 조건 / 배정할 검증 |
|---|---|
| M2-1A-R3: 자동 사건 증거 경로의 적격성 검수 | 일일 수동 분류 없이 일반/특별, 권리, 통화·단위, 출처를 제공하는 실제 경로 확보. GPT-6 Astra High 검토. 확보하지 못하면 미착수 |
| M2-1A-R4: v4 검증된 일반 현금배당 계산 | R2 통과 + R3 계약 승인. 작은 특별배당/분류 근거 부재/통화·가격 단위 불일치/Capital Gains 실패 폐쇄, 적격 사건의 진입일 제외·최종일 포함, v1/v2/v3 보존과 v4 분리를 검증. 구현 검수 GPT-5.6 Sol High |
| M2-1B: 배당 포함 feature 창 | 적격 실데이터 경로와 v4 검수 통과. 별도 feature 계약 승인 전 착수 금지 |
