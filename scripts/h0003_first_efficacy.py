"""Owner-authorized first H0003 discovery outcomes, sealed evaluator before labels."""
from argparse import ArgumentParser
from contextlib import ExitStack,contextmanager
from datetime import timedelta
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

from richping.core import digest,sessions,timestamp
from richping.research_v2.contracts import payload
from richping.research_v2.sessions import NY
from richping.research_v2.strategy import h0003_efficacy as evaluator
from richping.research_v2.strategy.h0003_leadership import CONTRACT,Specification
from richping.research_v2.strategy.h0003_experiment import scheduled_window,validate_events
from scripts import h0003_signal_preregister as frozen
from scripts import h0003_frequency_audit as frequency
from scripts.h0003_benchmark_admission import load_capture,ROOT as QQQ_ROOT
from scripts.h0002_frequency_audit import SOURCE,FORBIDDEN,load_admitted,encode,fingerprint,preservation_fingerprint
from scripts.h0003_verify import junit
from scripts.h0001_long_history_audit import write_new

ROOT = Path('research/data_evidence/h0003-first-efficacy-20261005')
BASE = 'f1dffa02884096ff6abeaa05d2b94deec5957e97'
FILES = ('richping/research_v2/strategy/h0003_efficacy.py','scripts/h0003_first_efficacy.py',
         'tests/test_h0003_efficacy.py','docs/H0003_FIRST_EFFICACY.md')


def verify_contract():
    # Byte/canonical fingerprints and event metadata only. No market constructor.
    with frozen.metadata_only() as calls:
        verified = frozen.verify()
    if (any(calls.values()) or verified['protocol_hash'] != evaluator.PROTOCOL_HASH
            or verified['signal_freeze_sha256'] != evaluator.FREEZE_HASH
            or verified['discovery_events'] != 35 or verified['discovery_sessions'] != 29):
        raise ValueError('INVALID_FAIL_CLOSED: preregistration/signal binding mismatch')
    record = json.loads(frozen.FREEZE.read_bytes())
    events = json.loads(Path(record['discovery_events_path']).read_bytes())['events']
    pair_ids = [record['datasets'][s]['id'] for s in ('SOXX','QQQ')]
    validated = validate_events(events,pair_ids,record['discovery_event_stream_hash'])
    if (fingerprint(record['discovery_events_path']) != record['discovery_events_sha256']
            or record['paired_contract'] != list(CONTRACT) or validated['events'] != 35 or validated['sessions'] != 29):
        raise ValueError('INVALID_FAIL_CLOSED: paired stream/provenance mismatch')
    binding = dict(protocol_hash=evaluator.PROTOCOL_HASH,signal_freeze_hash=evaluator.FREEZE_HASH,
        dataset_ids=pair_ids,datasets=record['datasets'],candidate_stream_hash=validated['hash'],
        candidate_ids=[e['id'] for e in events],candidate_sessions=29,paired_contract=list(CONTRACT),
        signal_source_sha256=record['implementation_sha256'],signal_spec_hash=record['signal_spec_hash'])
    return verified,record,events,binding


@contextmanager
def guarded(preparation=False):
    targets = {**FORBIDDEN,'sqlite3.connect':'database',
        'richping.research_v2.strategy.h0002_efficacy.DiscoveryLabels.label':'other_hypothesis_labels',
        'richping.research_v2.strategy.h0002_efficacy._registered_bootstrap':'uncertainty_calculation',
        'richping.research_v2.strategy.h0002_efficacy.terminal_inference':'confirmation_inference'}
    if preparation:
        targets['richping.research_v2.strategy.h0003_efficacy.DiscoveryLabels.label'] = 'label_before_seal_or_preparation_complete'
    counts = {category:0 for category in targets.values()}
    def reject(category):
        def denied(*args,**kwargs):
            counts[category] += 1
            raise AssertionError('H0003 efficacy forbids '+category)
        return denied
    with ExitStack() as stack:
        for target,category in targets.items():
            stack.enter_context(patch(target,side_effect=reject(category)))
        yield counts


def verify_manifest():
    verified,record,events,binding = verify_contract()
    manifest = json.loads((ROOT/'preexecution-manifest.json').read_bytes())
    if (manifest['base_commit'] != BASE or manifest['binding'] != binding
            or manifest['runtime'] != frozen.runtime_identity()
            or manifest['plan_sha256'] != fingerprint(ROOT/'outcome-access-plan.json')):
        raise ValueError('INVALID_FAIL_CLOSED: preexecution manifest/plan mismatch')
    for group in ('implementation_files','preserved_files'):
        for path,expected in manifest[group].items():
            actual = fingerprint(path) if group=='implementation_files' else preservation_fingerprint(path)
            if actual != expected:
                raise ValueError('INVALID_FAIL_CLOSED: source/input/evidence changed: '+path)
    tests = junit(ROOT/'tests-preexecution-v1.xml')
    if tests != manifest['synthetic_test_receipt'] or any(tests[k] for k in ('failures','errors','skipped')):
        raise ValueError('INVALID_FAIL_CLOSED: pre-outcome adapter tests changed/failed')
    return manifest,record,events,binding


def seal():
    verified,record,events,binding = verify_contract()
    tests = junit(ROOT/'tests-preexecution-v1.xml')
    if any(tests[k] for k in ('failures','errors','skipped')) or not tests['tests']:
        raise ValueError('Passing synthetic adapter tests required before outcome access')
    paths = subprocess.run(['git','ls-tree','-r','--name-only',BASE],check=True,capture_output=True,text=True).stdout.splitlines()
    plan = dict(scope='SEALED70_DISCOVERY_ONLY',binding=binding,permitted_horizons=list(evaluator.HORIZONS),
        primary_horizon=evaluator.PRIMARY,confirmation_outcome_access=0,opportunistic_capture=False,
        labels=[dict(event_id=e['id'],horizon=h,anchor=e['at'],
            scheduled_path=[e['at'],*[t.isoformat() for t in scheduled_window(e['at'],h)[0]]])
            for e in events for h in evaluator.HORIZONS])
    write_new(ROOT/'outcome-access-plan.json',encode(plan))
    manifest = dict(schema='h0003_first_efficacy_preexecution_v1',base_commit=BASE,
        binding=binding,runtime=frozen.runtime_identity(),synthetic_test_receipt=tests,
        implementation_files={p:fingerprint(p) for p in FILES},
        preserved_files={p:preservation_fingerprint(p) for p in paths if p not in ('.gitattributes','PROJECT_STATUS.md')},
        plan_sha256=fingerprint(ROOT/'outcome-access-plan.json'),
        H0003_label_queries_before_this_seal=0,confirmation_outcome_access=0,
        authorization='Owner explicitly authorized H0003_FIRST_EFFICACY discovery only; frozen contracts unchanged.',
        preflight=verified)
    write_new(ROOT/'preexecution-manifest.json',encode(manifest))
    return manifest


def prepare_sources(record,events):
    own,benchmark,metadata = frequency.paired_inputs()
    if (metadata['own_dataset_id'],metadata['own_dataset_hash'],metadata['benchmark_dataset_id'],
            metadata['benchmark_vintage_hash'],metadata['benchmark_capture_hash'],metadata['benchmark_admission_hash'],
            metadata['paired_contract']) != (
            record['datasets']['SOXX']['id'],record['datasets']['SOXX']['hash'],record['datasets']['QQQ']['id'],
            record['datasets']['QQQ']['hash'],record['datasets']['QQQ']['capture_hash'],record['datasets']['QQQ']['admission_hash'],list(CONTRACT)):
        raise ValueError('INVALID_FAIL_CLOSED: reconstructed paired dataset identity mismatch')
    replay = frequency.replay(own,benchmark,Specification())
    if replay['events'] != events or replay['trace_chain_hash'] != record['discovery_trace_chain']:
        raise ValueError('INVALID_FAIL_CLOSED: frozen causal signal replay mismatch')
    dataset = load_admitted()
    capture = load_capture()
    action = json.loads((SOURCE/'action-history-audit.json').read_bytes())
    units = json.loads((SOURCE/'ohlc-unit-crosscheck.json').read_bytes())
    admission = json.loads((SOURCE/'admission.json').read_bytes())
    if (digest(action) != admission['action_audit_hash'] or digest(units) != admission['daily_unit_audit_hash']
            or action['splits_inside_interval'] or not admission['raw_split_identical_selected_intraday_and_daily']
            or not action['interval_start'] <= evaluator.START <= evaluator.END <= action['interval_end']):
        raise ValueError('INVALID_FAIL_CLOSED: SOXX action/raw-unit certificate mismatch')
    meta = dataset.manifest.unpack()
    own_rows = []
    for b in dataset.bars:
        provenance = b.provenance.unpack()
        unit_ok = (b.corporate_action in ('NONE_CONFIRMED','UNKNOWN')
            and provenance.get('corporate_actions')==CONTRACT[5] and provenance.get('price_basis')==CONTRACT[4])
        own_rows.append(evaluator.OutcomeBar(b.dataset_id,b.symbol,b.start_at,b.end_at,b.known_at,b.session,
            b.open,b.high,b.low,b.close,CONTRACT,unit_ok))
    bench_rows = []
    for row in capture['cases']['raw']['rows']:
        start = timestamp(row['t'])
        end = start+timedelta(minutes=15)
        bench_rows.append(evaluator.OutcomeBar(record['datasets']['QQQ']['id'],'QQQ',start,end,end,
            start.astimezone(NY).date().isoformat(),row['o'],row['h'],row['l'],row['c'],CONTRACT,True))
    if (payload([b.causal_close() for b in own_rows]) != payload(own)
            or payload([b.causal_close() for b in bench_rows]) != payload(benchmark)):
        raise ValueError('INVALID_FAIL_CLOSED: OHLC label versus frozen close vintage mismatch')
    cash = {}
    for source in action['dataset_completeness_sources']:
        if source['identity']=='alpaca-selected-actions':
            raw = json.loads(Path(source['path']).read_bytes())
            cash['SOXX'] = raw['corporate_actions'].get('cash_dividends',[])
    cash['QQQ'] = capture['cases']['actions']['corporate_actions'].get('cash_dividends',[])
    cash = {symbol:[r for r in rows if evaluator.START <= r.get('ex_date',r.get('ex_dividend_date','')) <= evaluator.END]
            for symbol,rows in cash.items()}
    source = dict(datasets=record['datasets'],paired_contract=list(CONTRACT),
        certified_sessions=sessions(evaluator.START,evaluator.END),
        as_of=min(timestamp(meta['captured_at']),timestamp(capture['captured_at'])).isoformat(),
        SOXX_action_sha256=fingerprint(SOURCE/'action-history-audit.json'),
        SOXX_unit_sha256=fingerprint(SOURCE/'ohlc-unit-crosscheck.json'),
        QQQ_admission_sha256=fingerprint(QQQ_ROOT/'admission.json'),
        cash_distributions_not_reinvested=cash,price_return_only=True,
        certification_scope='EX_POST_GROSS_RAW_PRICE_LABEL_UNITS_NOT_BAR_TIME_ABSENCE_KNOWLEDGE')
    return own_rows,bench_rows,source


def execute():
    # Both checks precede constructing data or an event-conditioned price accessor.
    manifest,record,events,binding = verify_manifest()
    before = {p:fingerprint(p) for p in manifest['preserved_files']}
    with guarded(preparation=True) as preparation:
        own,benchmark,source = prepare_sources(record,events)
        write_new(ROOT/'label-source-manifest.json',encode(source))
    if any(preparation.values()):
        raise ValueError('Outcome accessed during preparation')
    verify_manifest()
    with guarded() as forbidden:
        reader = evaluator.DiscoveryLabels(own,benchmark,events,binding,source['certified_sessions'],source['as_of'])
        rows = evaluator.evaluate(events,reader)
        metrics = evaluator.metrics(rows)
    if any(forbidden.values()) or reader.audit['confirmation_label_requests'] or reader.audit['confirmation_price_reads']:
        raise ValueError('Forbidden confirmation/network/uncertainty/profitability access')
    if [r['event_id'] for r in rows] != binding['candidate_ids'] or len(rows)!=35:
        raise ValueError('Immutable full discovery denominator changed')
    plan = json.loads((ROOT/'outcome-access-plan.json').read_bytes())
    if [(r['event_id'],r['horizon_slots'],r['expected_path']) for r in reader.trace] != [
            (r['event_id'],r['horizon'],r['scheduled_path']) for r in plan['labels']]:
        raise ValueError('Executed outcome access differs from sealed scheduled plan')
    verify_manifest()
    if before != {p:fingerprint(p) for p in before}:
        raise ValueError('Prior actual source/evidence bytes changed during execution')
    report = dict(schema='h0003_first_discovery_efficacy_v1',scope='EXPLORATORY_DISCOVERY_ONLY',
        binding=binding,evaluator_source_hash=digest(manifest['implementation_files']),
        evaluator_source_sha256=manifest['implementation_files']['richping/research_v2/strategy/h0003_efficacy.py'],
        preexecution_manifest_sha256=fingerprint(ROOT/'preexecution-manifest.json'),
        label_source_manifest_hash=digest(source),candidate_events=35,candidate_sessions=29,
        primary_horizon=16,secondary_horizons=[4,64],metrics=metrics,
        disposition=evaluator.exploratory_disposition(metrics),
        uncertainty_status='DISCOVERY_UNCERTAINTY_NOT_PREREGISTERED',
        bootstrap_interval=None,p_value=None,confirmation_status='PENDING',confirmation_outcome_access=0,
        confirmation_terminal_deadline='2027-10-21T20:00:00-04:00',
        absolute_return_is_not_relative_proof=True,profitability='NOT_ESTIMATED',profitability_calculations=0,
        outcome_access_per_execution=dict(reader.audit),forbidden_calls=forbidden,preparation_forbidden_calls=preparation,
        retained_candidate_ids=[r['event_id'] for r in rows],preserved_files=len(before),
        not_confirmation=True,no_PASS_REJECT_or_promotion=True,next_P0='INDEPENDENT_HYPOTHESIS_GENERATION_SELECTION')
    for name,body in [('event-results.json',dict(events=rows)),('discovery-report.json',report),
            ('outcome-access-audit.json',dict(scope=report['scope'],counts=dict(reader.audit),trace=reader.trace))]:
        write_new(ROOT/name,encode(body))
    audits = ROOT/'execution-audits'
    ordinal = len(list(audits.glob('run-*.json')))+1
    write_new(audits/f'run-{ordinal:04d}.json',encode(dict(execution=ordinal,report_hash=digest(report),
        access_counts=dict(reader.audit),confirmation_outcome_access=0,result_hashes={
            name:fingerprint(ROOT/name) for name in ('event-results.json','discovery-report.json','outcome-access-audit.json')})))
    return report


def repeated():
    first,second = execute(),execute()
    if first != second:
        raise ValueError('Repeated discovery not deterministic')
    proof = dict(runs=2,repeat_equal=True,report_hash=digest(first),
        result_hashes={name:fingerprint(ROOT/name) for name in ('event-results.json','discovery-report.json','outcome-access-audit.json')},
        confirmation_outcome_access=0,primary_horizon_unchanged=16,H0001_H0002_H0003_frozen_evidence_preserved=True)
    write_new(ROOT/'repeat-proof.json',encode(proof))
    return first


if __name__=='__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--seal',action='store_true',help='Metadata/source/test seal only, no price loading or outcomes')
    args = parser.parse_args()
    if args.seal:
        result = seal()
        print(json.dumps(dict(sealed=True,outcome_access=0,files=result['implementation_files']),indent=2))
    else:
        result = repeated()
        print(json.dumps({k:result[k] for k in ('metrics','disposition','confirmation_outcome_access','outcome_access_per_execution')},indent=2))
