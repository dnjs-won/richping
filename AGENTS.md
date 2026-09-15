# Richping

`PROJECT_SPEC.md`가 최상위 요구사항이고 `docs/DESIGN.md`가 현재 MVP 계약이다. 신규 독립 프로젝트다. C:\konviction 및 C:\adaptive-alpha는 read-only reference이며 요구사항을 상속하지 않는다.

Python modular monolith / SQLite / CLI. 사용자 노동, 추천 성능, 검증, 리스크, 운영 안정성에 직접 기여하지 않는 확장은 보류한다. 자동 주문과 복잡한 frontend는 만들지 않는다.

추천 snapshot은 immutable. 미래 feature/label leakage, 현재 universe 소급, 누락 outcome 생략, synthetic 성과를 실제 Alpha로 보고하는 행위를 금지한다. 실행 코드 수정 시 핵심 불변조건을 테스트한다.

Commands: `.venv\Scripts\python -m pytest`, `.venv\Scripts\python -m richping demo`, `.venv\Scripts\python -m richping --help`.
