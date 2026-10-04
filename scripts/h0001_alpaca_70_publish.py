"""Commit verified discovery and main-only PM documents, then push both branches."""
from pathlib import Path
import subprocess

from scripts.h0001_alpaca_70_finalize import pm, junit, BRANCH, RECORD, ROOT
from scripts.h0001_alpaca_70_discovery import load_capture, audit
from scripts.h0001_alpaca_admission import credentials

REPO = Path(__file__).resolve().parents[1]
MAIN = REPO/'var/pm-action-unit-main'
PATHS = ['.gitattributes', 'PROJECT_STATUS.md', 'docs/H0001_ALPACA_70_DISCOVERY.md',
         ROOT.as_posix(), RECORD, 'richping/research_v2/aggregation.py',
         'richping/research_v2/daily_identity.py', 'richping/research_v2/real_data.py',
         'richping/research_v2/alpaca_data.py', 'scripts/h0001_alpaca_70_capture.py',
         'scripts/h0001_alpaca_70_diagnostic.py', 'scripts/h0001_alpaca_70_discovery.py',
         'scripts/h0001_alpaca_70_finalize.py', 'scripts/h0001_alpaca_70_publish.py',
         'scripts/prepare_independent_research.py', 'tests/test_h0001_alpaca_70_discovery.py',
         'tests/test_independent_research_intake.py']


def git(*args, cwd=REPO, capture=False):
    return subprocess.run(['git', *args], cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def main():
    if git('branch','--show-current',capture=True).strip() != BRANCH:
        raise ValueError('Unexpected workstream branch')
    if git('branch','--show-current',cwd=MAIN,capture=True).strip() != 'main':
        raise ValueError('Canonical PM worktree must be main')
    if git('status','--porcelain',cwd=MAIN,capture=True).strip():
        raise ValueError('Preserve unexpected main changes')
    junit(REPO/'var/h0001-alpaca-70-post-finalization-full.xml')
    admission, _, _ = audit(load_capture())
    if admission['status'] != 'PASS': raise ValueError('Admission required')
    secrets = tuple(credentials().values())
    for p in (REPO/ROOT).rglob('*'):
        if p.is_file() and any(s.encode() in p.read_bytes() for s in secrets):
            raise ValueError('Credential scan failed; values never printed')
    git('add','--',*PATHS)
    staged = git('diff','--cached','--name-only',capture=True).splitlines()
    if any(p not in PATHS and not p.startswith(ROOT.as_posix()+'/') for p in staged):
        raise ValueError('Unrelated staged change; preserve rather than commit')
    git('diff','--cached','--check')
    git('commit','-m','Admit independent Alpaca70 discovery and preserve sparse frozen H0001')
    pm(MAIN)
    git('diff','--check',cwd=MAIN)
    git('add','--','PROJECT_CONTROL.yaml','PROJECT_STATUS.md','project/BACKLOG.yaml','project/DECISION_INDEX.yaml',cwd=MAIN)
    git('commit','-m','Route sparse H0001 to future confirmation and activate independent hypothesis research',cwd=MAIN)
    git('push','-u','origin',BRANCH)
    git('push','origin','main',cwd=MAIN)
    print('WORKSTREAM_COMMIT',git('rev-parse','HEAD',capture=True).strip())
    print('PM_COMMIT',git('rev-parse','HEAD',cwd=MAIN,capture=True).strip())


if __name__ == '__main__': main()
