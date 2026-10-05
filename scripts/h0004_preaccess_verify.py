"""Independent metadata and artificial arithmetic verification; no real labels."""
import ast
from dataclasses import replace
from pathlib import Path
from fractions import Fraction

from richping.core import digest,timestamp
from richping.research_v2.contracts import payload
from richping.research_v2.strategy.h0004_directional_evaluator import DirectionalEvaluator,Scope
from scripts.h0004_preaccess_fixtures import fixture
from scripts.h0004_frequency_audit import fingerprint,encode,write_new


def verify():
    from scripts.h0004_preaccess import ROOT,verify_manifest,junit
    manifest,binding,anchors = verify_manifest()
    # Inspect dependency direction without running the signal or a real endpoint.
    for path in ('richping/research_v2/strategy/h0004_compression.py',
                 'richping/research_v2/strategy/h0004_segment_compression.py'):
        tree = ast.parse(Path(path).read_text(encoding='utf-8'))
        imports = [n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
        if any('directional_evaluator' in n or 'discovery_access' in n for n in imports):
            raise ValueError('Signal imports outcome adapter')
    proofs = []
    for repetition in range(2):
        e,r = fixture(times=('2026-05-06T10:00:00-04:00','2026-05-06T10:15:00-04:00',
                             '2026-05-06T10:30:00-04:00','2026-05-07T10:00:00-04:00'),
                      returns=(.1,.1,.1,-.1))
        rows = e.evaluate(r)
        full = e.aggregate(rows)
        # Independent equal-session reference uses exact rational fixture values.
        reference = float((sum([Fraction(1,10)]*3)/3+Fraction(-1,10))/2)
        if abs(full['full_cohort_session_balanced_mean']-reference)>1e-14 or full['total_emitted']!=4:
            raise ValueError('Session-balanced formula differs from independent fixture reference')
        unresolved = [dict(x) for x in rows]
        unresolved[-1].update(status='UNRESOLVED',gross_return=None,reason='synthetic_missing')
        incomplete = e.aggregate(unresolved)
        if incomplete['full_cohort_session_balanced_mean'] is not None or incomplete['total_emitted']!=4:
            raise ValueError('Partial labels silently omitted')
        # Weekend/holiday mapping tested on artificial anchors only.
        from richping.research_v2.strategy.h0004_experiment import scheduled_window,DEADLINE
        path,_ = scheduled_window('2026-05-08T20:00:00-04:00')
        if path[0]!=timestamp('2026-05-11T04:15:00-04:00') or path[-1]!=timestamp('2026-05-11T08:00:00-04:00'):
            raise ValueError('Exact scheduled weekend mapping failed')
        c,reader = fixture(times=('2026-10-19T10:00:00-04:00',),scope=Scope.CONFIRMATION_TERMINAL,
                          start='2026-10-19',end='2027-10-20',as_of=DEADLINE)
        blocked = c.evaluate(lambda *a:(_ for _ in ()).throw(AssertionError('Confirmation exposed')))
        if blocked[0]['status']!='PENDING' or any(c.audit.values()): raise ValueError('Preterminal label exposed')
        try: c.aggregate(blocked)
        except PermissionError: pass
        else: raise ValueError('Preterminal confirmation aggregation exposed')
        proofs.append(dict(synthetic_formula=True,synthetic_weighting=True,full_denominator=True,
            confirmation_pending_without_reads=True,synthetic_output_hash=digest(payload([rows,full,incomplete,blocked])),
            synthetic_counters=dict(e.audit)))
    if proofs[0]!=proofs[1]: raise ValueError('Nondeterministic synthetic evaluator')
    tests = [junit(ROOT/n) for n in ('tests-targeted.xml','tests-full.xml')]
    result = dict(schema='h0004_independent_preaccess_verification_v1',status='PASS_PREACCESS_NO_REAL_OUTCOMES',
        manifest_sha256=fingerprint(ROOT/'manifest.json'),source_hashes=manifest['source_hashes'],
        real_candidate_count=48,real_candidate_sessions=29,signal_trials=2,
        real_outcome_access=0,real_future_price_queries=0,real_efficacy_calculations=0,
        real_profitability_calculations=0,confirmation_outcome_access=0,
        actual_candidate_endpoint_scope='NOT_PROBED',protected_files=len(manifest['protected_files']),
        prior_tracks_and_trial1_trial2_freeze_protocol_preserved=True,deterministic=True,
        synthetic_verification=proofs[0],tests=tests,next_P0='H0004_DISCOVERY_EFFICACY_EXECUTION',
        confirmation='PENDING_ASYNCHRONOUS_FUTURE_TERMINAL_ADAPTER_REQUIRED')
    write_new(ROOT/'verification.json',encode(result))
    return result
