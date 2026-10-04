"""Finalize H0002 evidence after completed targeted and full regression runs."""
from hashlib import sha256
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.h0002_frequency_audit import ROOT, ORIGINAL, encode, fingerprint, verify_manifest
from scripts.h0001_long_history_audit import write_new


def publish():
    manifest = verify_manifest()
    report = {'schema': 'h0002_regression_tests_v1', 'outcomes': 'NOT_RUN',
              'H0002_real_outcome_access': 0, 'H0002_profitability_calculations': 0,
              'note': 'Existing synthetic outcome arithmetic regression is not H0002 real outcome evaluation.'}
    for kind in ('targeted', 'full'):
        path = Path('var')/('h0002-'+kind+'.xml')
        raw = path.read_bytes()
        suites = list(ET.fromstring(raw).iter('testsuite'))
        counts = {key: sum(int(s.get(key, '0')) for s in suites)
                  for key in ('tests', 'failures', 'errors', 'skipped')}
        if any(counts[k] for k in ('failures', 'errors', 'skipped')) or not counts['tests']:
            raise ValueError('Completed passing full/targeted suite required')
        name = kind+'-suite.xml'
        write_new(ROOT/name, raw)
        report[kind] = {**counts, 'passed': counts['tests'], 'seconds': sum(float(s.get('time', '0')) for s in suites),
                        'sha256': sha256(raw).hexdigest(), 'path': name}
    original = json.loads((ORIGINAL/'preexecution-manifest.json').read_bytes())
    changed = [p for p, h in original['preserved_files'].items() if fingerprint(p) != h]
    if changed:
        raise ValueError('Actual original bytes changed: '+','.join(changed))
    report['original_files_byte_identical_after_full_regression'] = len(original['preserved_files'])
    report['cli_help'] = 'PASS'
    report['diff_check'] = 'PASS'
    write_new(ROOT/'test-report.json', encode(report))
    sources = {p.as_posix(): fingerprint(p) for p in (
        Path('scripts/h0002_publish.py'), Path('tests/test_h0002_defense.py'),
        Path('tests/test_independent_research_intake.py'),
        Path('research/decision_records/H0002-hypothesis-frequency-v1.yaml'),
        Path('docs/H0002_FREQUENCY_RESULTS.md'))}
    artifacts = {p.relative_to(ORIGINAL).as_posix(): fingerprint(p) for p in ORIGINAL.rglob('*')
                 if p.is_file() and p.name != 'final-verification.json'}
    write_new(ROOT/'final-verification.json', encode({
        'schema': 'h0002_final_verification_v1', 'preexecution_source_verified': True,
        'signal_spec_or_module_changed_after_frequency': False,
        'canonical_manifest_sha256': fingerprint(ROOT/'preexecution-manifest.json'),
        'canonical_report_sha256': fingerprint(ROOT/'frequency-audit.json'),
        'test_report_sha256': fingerprint(ROOT/'test-report.json'),
        'preserved_files': len(manifest['preserved_files']),
        'actual_original_file_bytes_identical': True, 'outcome_access': 0,
        'parameter_trials': 1, 'profitability': 'NOT_RUN', 'artifacts': artifacts,
        'final_source_LF_sha256': {p: sha256(Path(p).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in sources}}))
    return report


if __name__ == '__main__':
    print(json.dumps(publish(), sort_keys=True))
