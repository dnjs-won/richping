"""Verify committed H0003 bindings and published evidence without new price reads."""
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from scripts.h0003_first_efficacy import ROOT
from scripts.h0002_frequency_audit import encode,fingerprint
from scripts.h0001_long_history_audit import write_new


def prove():
    commit = subprocess.run(['git','rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
    target = Path(tempfile.mkdtemp(prefix='h0003-efficacy-archive-',dir=Path('var').resolve()))
    archive = target/'snapshot.tar'
    subprocess.run(['git','archive','--format=tar',f'--output={archive}',commit],check=True)
    checkout = target/'checkout'
    checkout.mkdir()
    with tarfile.open(archive) as source:
        source.extractall(checkout,filter='data')
    execution = subprocess.run([sys.executable,'-m','scripts.h0003_efficacy_verify'],
        cwd=checkout,check=True,capture_output=True,text=True)
    actual = json.loads(execution.stdout)
    expected = json.loads((ROOT/'verification.json').read_bytes())
    if actual!=expected or actual['verification_price_queries'] or actual['confirmation_outcome_access']:
        raise ValueError('Committed published evidence/source binding mismatch')
    result = dict(archive_commit=commit,clean_archive_metadata_and_published_result_verification_equal=True,
        report_hash=actual['report_hash'],result_hashes=actual['result_hashes'],
        preserved_files_verified=actual['preserved_files'],protocol_hash=actual['protocol_hash'],
        signal_freeze_hash=actual['signal_freeze_hash'],event_stream_hash=actual['event_stream_hash'],
        new_price_queries=0,confirmation_outcome_access=0,
        verification_sha256=fingerprint(ROOT/'verification.json'))
    write_new(ROOT/'clean-checkout-proof.json',encode(result))
    return result


if __name__=='__main__':
    print(json.dumps(prove(),indent=2))
