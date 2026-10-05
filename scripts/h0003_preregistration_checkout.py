"""Verify frozen H0003 metadata from a committed Git archive, without market replay."""
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from scripts.h0003_signal_preregister import ROOT
from scripts.h0003_frequency_audit import encode, fingerprint
from scripts.h0001_long_history_audit import write_new


def prove():
    commit = subprocess.run(['git','rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
    target = Path(tempfile.mkdtemp(prefix='h0003-prereg-archive-',dir=Path('var').resolve()))
    archive = target/'snapshot.tar'
    subprocess.run(['git','archive','--format=tar',f'--output={archive}',commit],check=True)
    checkout = target/'checkout'
    checkout.mkdir()
    with tarfile.open(archive) as source:
        # Git archive is local and still reject unsafe member paths/links.
        source.extractall(checkout,filter='data')
    execution = subprocess.run([sys.executable,'-m','scripts.h0003_signal_preregister'],
        cwd=checkout,check=True,capture_output=True,text=True)
    actual = json.loads(execution.stdout)
    expected = json.loads((ROOT/'verification.json').read_bytes())
    if actual != expected or any(actual['forbidden_call_counts'].values()):
        raise ValueError('Committed checkout metadata differs or accessed forbidden scope')
    result = dict(archive_commit=commit,clean_archive_metadata_verification_equal=True,
        original_570_source_and_evidence_hashes_verified=True,
        frozen_signal_and_protocol_bindings_verified=True,
        event_stream_hash=actual['event_stream_hash'],protocol_hash=actual['protocol_hash'],
        outcome_access=0,future_price_queries=0,efficacy_calculations=0,
        verification_sha256=fingerprint(ROOT/'verification.json'))
    write_new(ROOT/'clean-checkout-proof.json',encode(result))
    return result


if __name__ == '__main__':
    print(json.dumps(prove(),indent=2))
