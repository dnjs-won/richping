# R0 일일 shadow 운영 계약

R0-A는 일일 실행 시도와 사람이 읽을 수 있는 파생 보고서를 구현했다. R0-B는 2026-09-20에 실제 next-open 이전 실행 1회와 Windows 예약 작업 등록·구성을 확인했다. 자동 주문, Telegram 발송, 새 전략, paper 원장은 포함하지 않는다. 예약 trigger의 첫 실행과 다일 무인 안정성, Alpha는 아직 확인되지 않았다.

## 실행과 출력

운영 진입점은 다음 하나다.

```powershell
powershell.exe -NoProfile -File C:\richping\scripts\daily.ps1
```

wrapper는 `C:\richping`으로 이동해 `.venv\Scripts\python.exe -m richping daily`를 실행한다. 배타적 파일 lock으로 동시 실행을 거부하고 Python 종료 코드를 그대로 반환한다. 기본 운영 산출물은 다음과 같다.

| 경로 | 의미 |
|---|---|
| `var/operations/attempts/*.json` | 수집 전에 생성되는 실행 시도 lifecycle. 실패해 runs가 없어도 남는다 |
| `var/operations/reports/*.json` | 특정 session/attempt의 완성된 파생 JSON 세대 |
| `var/operations/reports/*.md` | 같은 세대의 사람이 읽는 Markdown |
| `var/operations/latest.json` | JSON과 Markdown 세대가 모두 완성된 뒤 마지막에 교체되는 최신 포인터 겸 전체 보고서 |
| `var/operations/start-manifest.json` | R0 운영 시작 ID, model/config/code provenance, 이전 model과 risk latch 관계 |
| `var/operations/r0-b-start-verification.json` | 실제 첫 forward 실행, DB 전후, 새 vintage, scheduler 구성의 R0-B 확인 manifest |
| `var/operations/r0-b-start-verification.md` | 같은 R0-B 확인 내용을 사람이 읽는 형식으로 요약 |
| `var/operations/daily.log` | wrapper 표준 출력/오류 append log |

`latest.json`의 `artifacts.markdown`이 현재 완성 세대의 Markdown 경로다. Markdown 생성이나 원자적 교체가 실패하면 `latest.json`은 이전 완성 세대를 유지하고 해당 attempt는 FAILED로 남는다. 고아가 된 versioned 파일은 최신 성공으로 읽지 않는다. 최초 실행 전에 만든 `start-manifest.json`은 덮지 않고, 실행·scheduler 확인 결과는 별도 R0-B manifest로 추가했다.

기본 운영 DB가 아닌 `--db`를 사용한 `daily`와 모든 수동 `scan`은 기본적으로 `var/research/<db-name>/...` 아래에 쓴다. `--output-dir`로 격리된 테스트 경로를 지정할 수 있다. 기존 `var/daily-report.json`, immutable run body, dataset, recommendation snapshot, 확정 outcome은 R0 보고서가 수정하지 않는다.

## 보고서 읽기

```powershell
.\.venv\Scripts\python -m richping report
.\.venv\Scripts\python -m richping report --write --output-dir var\r0-a-evidence
```

`report` 조회는 outcome을 새로 관측하거나 DB에 쓰지 않는다. 저장된 최신 성공 run과 실행 시도를 조합하고 조회 시각 기준으로 CURRENT/STALE만 다시 계산한다. `--write`는 DB를 read-only로 유지하면서 별도 JSON/Markdown 세대를 만든다.

판단 상태는 다음처럼 분리한다.

- `CANDIDATES_AVAILABLE`: 후보가 있으며 score, 기여요인, 다음 XNYS 시가 관측, 5번째 session 종가 평가, 종가/ATR 참고값과 calibration 근거가 표시된다.
- `NORMAL_NO_TRADE`: 시장 상태, raw signal, calibration 또는 edge 기준으로 후보가 없다. 데이터 장애나 음의 기대값으로 바꾸어 설명하지 않는다.
- `RISK_HALT`: 성과 PAUSED latch 등 위험 중단이다. 같은 config의 과거 model ID에 PAUSED가 있으면 reporting code로 ID가 바뀌어도 이어진다.
- `DATA_BLOCKED`: 미해결 outcome 또는 평가 무결성이 현재 판단을 차단했다.
- `DATA_FAILURE`: 현재 시도가 수집 전/중 또는 보고 생성 중 실패했다. 과거 성공은 `prior_success_reference`일 뿐 오늘 판단이나 후보로 표시하지 않는다.

freshness에는 대상 XNYS session, 실제 cutoff, 다음 진입 session, next-open 유효시각, 최신 dataset session/capture가 있다. 다음 개장이 지나면 STALE이다. 휴일·주말의 동일 run 재표시는 `duplicate_run=true`, `new_forward_observation=false`이고 추천·성과 날짜를 늘리지 않는다. 다음 개장이 지난 뒤 새 shadow 추천을 만들려는 실행은 기존 scan guard가 실패시킨다.

outcome은 모든 horizon의 COMPLETE/PENDING/UNRESOLVED와 holding-period eligible/excluded를 따로 표시한다. read-only forward 요약은 model/mode/source/quality/outcome/evaluation 계약별로 그룹화하고, 같은 recommendation/horizon의 여러 outcome vintage는 최신 저장 dataset rowid 하나만 집계한다. SYNTHETIC, RESEARCH, FRESH_SHADOW를 합치지 않는다. 추천 수익과 cohort drawdown은 계좌 수익이 아니므로 portfolio return은 N/A다.

## 실제 R0-B 보고 예시

2026-09-20 22:38 Asia/Seoul에 실행한 실제 정상 NO TRADE 보고서의 핵심 부분이다. 전체 JSON은 `var/operations/latest.json`, 전체 Markdown 경로는 그 JSON의 `artifacts.markdown`에 있다.

```markdown
# Richping daily shadow report - 2026-09-18
- Execution: **SUCCEEDED** / COMPLETE
- Freshness: **CURRENT**; valid until 2026-09-21T13:30:00+00:00
- Judgment: **NORMAL_NO_TRADE** - insufficient_evidence_or_edge

## Outcomes and evidence
- Horizons: COMPLETE 0, PENDING 0, UNRESOLVED 0
- Evidence level: FRESH_SHADOW; Alpha: INSUFFICIENT_EVIDENCE; portfolio return: N/A
```

같은 날 첫 실행은 sandbox 네트워크 차단으로 수집 중 실패했다. 이 실패도 `var/operations/attempts/20260920T133458Z-185552aa38.json`과 별도 versioned 보고서에 보존됐다.

```markdown
# Richping daily shadow report - 2026-09-14
- Execution: **FAILED** / FAILED
- Freshness: **STALE**; valid until 2026-09-15T13:30:00+00:00
- Judgment: **DATA_FAILURE** - ConnectionError: failed to connect during collection

The current attempt failed before a valid new judgment was produced. A prior success is reference only.
```

운영 시작 증거는 `var/operations/r0-b-start-verification.json`과 같은 이름의 `.md`에 있다. 실제 shadow는 이제 2026-09-14 legacy 1 session과 2026-09-18 R0 1 session이며 추천/outcome은 0/0이다. legacy run body에는 feature/outcome/evaluation 계약 필드가 없으므로 현재 v3로 소급 표시하지 않고 `UNKNOWN_LEGACY_UNRECORDED` / `v1_price_only` / `legacy_unversioned`로 유지한다.

## Windows 예약 작업 점검과 복구

등록된 `\Richping Daily` 계약은 매일 Asia/Seoul 08:00, 실행 프로그램 `powershell.exe`, 인수 `-NoProfile -File C:\richping\scripts\daily.ps1`, 시작 위치 `C:\richping`이다. 현재 사용자 `lifes`, `Interactive`, `Limited`로 실행하고 다중 인스턴스는 `IgnoreNew`다. 동일 역할 task는 이 1건뿐이다. 2026-09-20 확인 시 상태는 `Ready`, 다음 실행은 2026-09-21 08:00, `LastTaskResult=267011`로 예약 작업 자체는 아직 실행되지 않았다. WakeToRun은 false이므로 PC가 종료·절전 상태이거나 Interactive 사용자가 로그아웃한 동안 실행을 보장하지 않는다. 관리자 권한과 OS 보안 정책은 변경하지 않았다.

```powershell
powershell.exe -NoProfile -File C:\richping\scripts\check_daily_task.ps1
```

실패 복구는 `attempts/*.json`, `daily.log`, `latest.json`을 먼저 확인한다. RUNNING run이 있으면 실제 Python/PowerShell 프로세스와 lock 보유 여부를 확인한다. 활성 프로세스가 없다는 안전 확인 뒤에만 `python -m richping recover-runs`를 실행하고 daily를 재시도한다. 자동 recover는 하지 않는다. 수집 실패는 기존 dataset/report를 삭제하거나 복사본으로 덮지 않고 다음 정상 sync에서 새 immutable vintage를 만든다.

R0-B의 수동 wrapper는 exit 0으로 확인됐다. 2026-09-21 08:00 trigger는 같은 2026-09-18 신호일의 중복/재표시가 예상되며 새 forward 관측으로 세지 않아야 한다. 미국 2026-09-21 session 종료 후 첫 신규 예정 관측은 2026-09-22 08:00 Asia/Seoul이다. 이 미래 실행을 미리 완료로 기록하지 않는다.
