# Richping

`PROJECT_SPEC.md`가 최상위 요구사항이고 `docs/DESIGN.md`가 현재 MVP 계약이다. 신규 독립 프로젝트다. C:\konviction 및 C:\adaptive-alpha는 read-only reference이며 요구사항을 상속하지 않는다.

미래 개발 순서는 `ROADMAP.md`의 R0~R6을 따른다. M1/M2-1A/M2-1B와 옛 M1~M5 계획은 역사 기록으로 보존한다. 첫 구현 명세는 `docs/FIRST_MILESTONE.md`다. 계획을 구현 완료로 기술하지 않는다.

Python modular monolith / SQLite / CLI. 사용자 노동, 추천 성능, 검증, 리스크, 운영 안정성에 직접 기여하지 않는 확장은 보류한다. 자동 주문과 복잡한 frontend는 만들지 않는다.

추천 snapshot은 immutable. 미래 feature/label leakage, 현재 universe 소급, 누락 outcome 생략, synthetic 성과를 실제 Alpha로 보고하는 행위를 금지한다. 실행 코드 수정 시 핵심 불변조건을 테스트한다.

운영 추천·격리된 연구·평가/승격의 쓰기 책임을 분리하고 기존 검증 엔진을 재사용한다. Feature dividend normalization과 outcome dividend accounting은 별개다. 연구 OOS/fresh shadow/paper/실체결 증거를 구분하며 추천 수익과 cohort drawdown을 계좌 성과로 표시하지 않는다. 최소 paper 자본 회계는 후속 범위이나 포트폴리오 최적화·자동 주문은 포함하지 않는다.

Commands: `.venv\Scripts\python -m pytest`, `.venv\Scripts\python -m richping demo`, `.venv\Scripts\python -m richping --help`.
