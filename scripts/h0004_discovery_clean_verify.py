"""Revalidate saved discovery evidence from a committed clean Git archive; no prices."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

from scripts.h0004_discovery_execution import ROOT,git
from scripts.h0004_frequency_audit import encode,write_new


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
    # Evidence-only verifier: never execute run1/run2 or a source loader here.
    process=subprocess.run([sys.executable,'-m','scripts.h0004_discovery_execution','verify'],
        cwd=destination,check=True,capture_output=True,text=True)
    result=json.loads(process.stdout)
    receipt=dict(schema='h0004_discovery_clean_git_archive_verification_v1',
        research_commit=commit,clean_archive=True,exit_code=process.returncode,
        new_discovery_price_reads=0,confirmation_outcome_access=0,result=result)
    write_new(ROOT/'clean-checkout-proof.json',encode(receipt))
    return receipt


if __name__=='__main__': print(json.dumps(verify(),indent=2))
