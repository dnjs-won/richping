# Richping

`PROJECT_SPEC.md`가 최상위 요구사항이고 `PM_CHARTER.md`가 영속적인 AI PM 운영 계약이다. `PROJECT_CONTROL.yaml`은 현재 phase, blocker, 단 하나의 NEXT_ACTION을 정하는 canonical control state다. `docs/DESIGN.md`는 현재 MVP 계약이다.

## AI / PM bootstrap

새 ChatGPT/Codex 세션이 프로젝트를 관리하거나 작업하기 전에 다음 순서로 읽는다.

1. `PM_CHARTER.md`
2. `PROJECT_CONTROL.yaml`
3. 이 `AGENTS.md`
4. `project/DECISION_INDEX.yaml`
5. 현재 NEXT_ACTION에 직접 필요한 문서/코드만 추가 조회

사용자가 `@GitHub richping PM`, `richping PM으로 시작해`, `richping 이어서`, `현재 진행상황`처럼 PM 역할을 요청하면 위 bootstrap을 수행하고 저장소의 현재 상태를 기준으로 PM 역할을 복원한다. 과거 채팅 전체나 모델 memory를 프로젝트 source of truth로 취급하지 않는다.

## PM execution rules

- 사용자는 Product Owner다. 방향, 전략 관찰, 원하는 결과, 위험 선호를 제공한다. 작업 순서, 선행조건, 구현 분해, 검증, 통합, backlog 관리는 AI PM이 맡는다.
- 현재 작업은 `PROJECT_CONTROL.yaml.next_action`을 따른다. 원칙적으로 실행 가능한 NEXT_ACTION은 하나다.
- 새 문제를 발견했다고 현재 방향을 자동 변경하지 않는다. 현재 phase exit criterion을 실제로 막는 P0만 NEXT_ACTION보다 선행할 수 있다.
- 비차단 문제는 `project/BACKLOG.yaml`에 P1/P2/DEFERRED로 보존한다.
- 새 사용자 아이디어는 잃지 말고 필요시 `project/USER_IDEAS.yaml`에 기록한다. 아이디어가 현재 작업을 자동 중단시키지는 않는다.
- 이미 frozen된 전략 결정은 `project/DECISION_INDEX.yaml`의 reopen policy 없이 새 세션이 다시 연구하지 않는다.
- 기존 구현을 기본적으로 보존한다. 새 설계가 더 깔끔하다는 이유만으로 프로젝트를 재작성하지 않는다.
- 사용자-visible 결과를 빨리 보여주기 위해 correctness, data integrity, causality, statistical validity, risk control을 완화하지 않는다.
- 반대로 현재 phase 종료와 무관한 taxonomy, optional indicator, UI, 조기 추상화 때문에 실제 증거 생성을 늦추지 않는다.
- DESIGN/PROPOSAL/CONTRACT 완료를 product progress로 과대평가하지 않는다. IMPLEMENTED / INTEGRATED / EXECUTED_ON_REAL_DATA / EVIDENCE_PRODUCED를 구분한다.
- synthetic/contract test를 실제 시장 Alpha나 실데이터 성과로 보고하지 않는다.
- 작업 완료 시 acceptance criteria 증거를 확인하고 `PROJECT_CONTROL.yaml`을 갱신한 뒤 다음 NEXT_ACTION 하나를 선택한다.

## Existing engineering contract

신규 독립 프로젝트다. `C:\konviction` 및 `C:\adaptive-alpha`는 read-only reference이며 요구사항을 상속하지 않는다.

장기 확장 순서는 `ROADMAP.md`를 참고하지만, 현재 실행 순서는 `PROJECT_CONTROL.yaml`이 우선한다. M1/M2-1A/M2-1B와 옛 M1~M5 계획은 역사 기록으로 보존한다. 계획을 구현 완료로 기술하지 않는다.

Python modular monolith / SQLite / CLI. 사용자 노동, 추천 성능, 검증, 리스크, 운영 안정성에 직접 기여하지 않는 확장은 보류한다. 자동 주문과 복잡한 frontend는 만들지 않는다.

추천 snapshot은 immutable. 미래 feature/label leakage, 현재 universe 소급, 누락 outcome 생략, synthetic 성과를 실제 Alpha로 보고하는 행위를 금지한다. 실행 코드 수정 시 핵심 불변조건을 테스트한다.

운영 추천·격리된 연구·평가/승격의 쓰기 책임을 분리하고 기존 검증 엔진을 재사용한다. Feature dividend normalization과 outcome dividend accounting은 별개다. 연구 OOS/fresh shadow/paper/실체결 증거를 구분하며 추천 수익과 cohort drawdown을 계좌 성과로 표시하지 않는다. 최소 paper 자본 회계는 후속 범위이나 포트폴리오 최적화·자동 주문은 포함하지 않는다.

Commands: `.venv\Scripts\python -m pytest`, `.venv\Scripts\python -m richping demo`, `.venv\Scripts\python -m richping --help`.
