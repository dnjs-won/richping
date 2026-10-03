"""Separate-process offline proof on saved REAL data; never calls a provider."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import socket
import sys

from richping.research_v2.data_cli import offline_proof
from richping.research_v2.store import ResearchStore


def deny_network(*args, **kwargs):
    raise AssertionError("Network forbidden during saved-dataset proof")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    socket.socket = deny_network
    socket.create_connection = deny_network
    assert "yfinance" not in sys.modules
    path = Path(args.store)
    before = sha256(path.read_bytes()).hexdigest()
    results = []
    for _ in range(2):
        with ResearchStore(path, read_only=True) as store:
            results.append(offline_proof(store.load_dataset(args.dataset_id)))
    assert results[0] == results[1]
    after = sha256(path.read_bytes()).hexdigest()
    assert before == after and "yfinance" not in sys.modules
    body = {**results[0], "identical_repeated_result": True,
            "db_file_unchanged": True, "db_file_sha256": after,
            "network_disabled": "socket.socket and socket.create_connection raise",
            "provider_module_imported": False, "reloads": 2}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(body, indent=2), encoding="utf-8")
    print(json.dumps(body))


if __name__ == "__main__":
    main()
