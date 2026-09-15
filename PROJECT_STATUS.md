# Richping 구현 상태 · 2026-09-15

## 완료 범위

- 독립 repository, Python 가상환경, SQLite schema, configuration.
- 최상위 명세와 14개 설계 항목 및 기존 프로젝트 재사용 분석.
- 실제 일봉 수집, 고정 ranking, 과거 확정 표본 calibration, immutable snapshot.
- 1/3/5/10/20 session 자동 관측, missing/action 격리, NO TRADE.
- Rolling train/validation/OOS, 통계·위험 gate 기본 함수.
- CLI 보고서, CSV import, 실패/재시도, PowerShell 일일 실행 스크립트.

## 실제 검증 결과

- Python 3.13.7, 테스트 48 passed / 0 failed / 0 skipped.
- 합성 70-session 재생: 추천 72건, 완료 horizon 결과 360개. 추천 있는 날 49일, NO TRADE 21일.
- 합성 기본 504/63/63 walk-forward: 4 folds, 완료 OOS 추천 label 313개.
- 실제 Yahoo 수집: 후보 8종목 + SPY/QQQ, 일봉 10,020개, 마지막 session 2026-09-14.
- 실제 shadow scan: 시장 조건 미충족으로 NO TRADE.
- 실제 기본 walk-forward: 5 folds, 완료 OOS 추천 54건 / 43개 날짜. 비용 후 양의 기대값을 입증하지 못함. 상세 기간·비용·분모·국면별 결과는 var/validation.json에 보존.
- 검증 데이터는 config.toml의 현재 고정 종목군, Yahoo 수정 가능한 과거 가격, 왕복 20bps. 연구용 OOS이며 survivorship-free 또는 final holdout 증거가 아니다. 전략 portfolio NAV가 아닌 horizon 추천 수익이다.
- 합성 수익률은 동작 검증이며 투자 성과 증거가 아니다.
- 원본 프로젝트 파일을 수정하지 않았고 직접 복사한 원본 코드는 0개다.
- PowerShell 일일 스크립트 구문 검사를 통과했다. 실제 예약 실행은 검증하지 않았다.

## 남은 범위

- 시점별 universe/vintage, 상폐 최종 회수금, 완전한 corporate-action 회계.
- 실제 challenger 생성/학습, paired OOS 비교와 자동 승격. 현재 gate는 미확보 증거에 REJECT.
- 이 PC에 예약 작업은 설치하지 않았다. README의 daily.ps1 명령을 작업 스케줄러에 한 번 등록해야 한다.
- 실제 계좌/포트폴리오 원장과 연환산 Sharpe/Sortino/Calmar는 없다. 현 단계 지표는 추천/cohort 진단이다.
- Performance PAUSED를 임의 재시작으로 해제하는 명령은 없다.
- 코드 hash + config hash가 model ID에 반영된다. 실행마다 snapshot/data/model ID를 저장한다.
- 실데이터 증분 수집은 mock 테스트로 검증했으며, 실제 네트워크에서 두 번째 증분 수집까지 확인한 것은 아니다.

다음 milestone은 feature 확장보다 데이터 coverage와 검증 신뢰도 보강이다. README.md의 실행 명령과 docs/DESIGN.md의 단계 경계를 따른다.
