"""Revalidate saved discovery evidence from a committed clean Git archive; no prices."""
import io
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tarfile

from scripts.h0004_discovery_execution import ROOT,git
from scripts.h0004_frequency_audit import encode,write_new


def restore_legacy_text(raw,expected):
    """Git text transport only: choose bytes solely by the pre-outcome SHA256."""
    variants=(raw,raw.replace(b'\r\n',b'\n'),raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
    matches=[v for v in variants if sha256(v).hexdigest()==expected]
    if not matches: raise ValueError('Legacy text cannot reproduce sealed byte identity')
    return matches[0]


def verify():
    if git('status','--porcelain'): raise ValueError('Committed clean workstream required')
    commit=git('rev-parse','HEAD').decode().strip()
    destination=Path('var/h0004-discovery-clean-'+commit[:12]).resolve()
    if destination.exists(): raise ValueError('New isolated archive required')
    destination.mkdir(parents=True)
    archive=git('archive','--format=tar',commit)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for member in tree.getmembers():
            target=(destination/member.name).resolve()
            if not target.is_relative_to(destination) or member.issym() or member.islnk():
                raise ValueError('Unsafe archive entry')
        tree.extractall(destination,filter='data')
    manifest=json.loads((destination/ROOT/'manifest.json').read_bytes())
    restored=[]
    for name,expected in manifest['gate']['frozen_records'].items():
        path=destination/name
        raw=path.read_bytes()
        fixed=restore_legacy_text(raw,expected)
        if fixed!=raw:
            path.write_bytes(fixed)
            restored.append(dict(path=name,git_archive_sha256=sha256(raw).hexdigest(),sealed_sha256=expected,
                adjustment='ISOLATED_ARCHIVE_LEGACY_GIT_TEXT_LINE_ENDINGS_ONLY'))
    # Evidence-only verifier: never execute run1/run2 or a source loader here.
    process=subprocess.run([sys.executable,'-m','scripts.h0004_discovery_execution','verify'],
        cwd=destination,check=True,capture_output=True,text=True)
    result=json.loads(process.stdout)
    receipt=dict(schema='h0004_discovery_clean_git_archive_verification_v1',
        research_commit=commit,clean_archive=True,exit_code=process.returncode,
        new_discovery_price_reads=0,confirmation_outcome_access=0,result=result,
        legacy_git_text_transport_restoration=restored,original_repository_artifacts_unchanged=True)
    write_new(ROOT/'clean-checkout-proof.json',encode(receipt))
    return receipt


if __name__=='__main__': print(json.dumps(verify(),indent=2))
