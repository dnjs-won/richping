"""Offline counts only. Run explicitly against a saved immutable vintage."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
from collections import Counter
from hashlib import sha256
import json
from unittest.mock import patch

from richping.core import digest
from richping.research_v2.contracts import ReplayContext, payload
from richping.research_v2.store import ResearchStore
from richping.research_v2.strategy.entry_15m import (
    contract_hash, measure_completed_15m, evaluate_temporal,
)


def mechanical_counts(dataset):
    observations = measure_completed_15m(ReplayContext(
        max(b.known_at for b in dataset.bars), dataset.bars), dataset.bars[0].symbol)
    memory, temporal, trace = None, Counter(), []
    for observation in observations:
        # Isolated primitive exercise: no fabricated Daily permission/1H ACTIVE.
        memory = evaluate_temporal(memory, observation, scope_ref="UNGATED_MECHANICAL_ONLY")
        temporal[memory.event] += 1
        trace.append(payload(memory))
    return {"bars": len(observations),
        "MACD_READY": sum(o.line is not None for o in observations),
        "MACD_UNAVAILABLE": sum(o.line is None for o in observations),
        "relative_READY": sum(o.raw != "UNAVAILABLE" for o in observations),
        "relative_UNAVAILABLE": sum(o.raw == "UNAVAILABLE" for o in observations),
        "first_relative_READY_N": next((o.index+1 for o in observations if o.raw != "UNAVAILABLE"), None),
        "extreme_count": sum(o.raw == "DOWNSIDE_EXTREME" for o in observations),
        "GC_count": sum(o.gc is True for o in observations),
        "GC_UNAVAILABLE": sum(o.gc is None for o in observations),
        "GC_AND_price_count": sum(o.gc is True and o.price is True for o in observations),
        "ungated_15m_trigger_count": temporal["TRIGGER"], "temporal_events": dict(temporal),
        "ENTRY_CANDIDATE_count": None, "ENTRY_CANDIDATE_status": "NOT_EVALUATED_DAILY_PIT_AND_COMPOSER_UNAVAILABLE",
        "trace_hash": digest(trace), "contract_hash": contract_hash(),
        "profitability": "NOT_RUN", "forward_returns": "NOT_RUN", "MFE_MAE": "NOT_RUN"}


def offline_check(store_path, dataset_id):
    original = sha256(Path(store_path).read_bytes()).hexdigest()
    def denied(*args, **kwargs):
        raise AssertionError("Network disabled during mechanical exercise")
    with patch('socket.socket.connect', denied), patch('socket.socket.connect_ex', denied), patch('socket.create_connection', denied):
        results = []
        for _ in range(2):
            with ResearchStore(store_path, read_only=True) as store:
                dataset = store.load_dataset(dataset_id)  # validates stored content hash
                results.append({"dataset_id": dataset.dataset_id, "content_hash": dataset.content_hash,
                                "counts": mechanical_counts(dataset)})
    if results[0] != results[1] or original != sha256(Path(store_path).read_bytes()).hexdigest():
        raise AssertionError("Offline repeated results or immutable DB differ")
    return {**results[0], "store_path": str(Path(store_path).resolve()),
        "network_disabled": True, "network_calls": 0, "provider_client_imported": 'yfinance' in sys.modules,
        "read_only_store": True, "store_sha256_before_after": original,
        "deterministic_repeated_exercise": True,
        "scope": "REAL_SAVED_DATA_PRIMITIVE_MECHANICS_NOT_COMPOSED_H0001_OR_PIT",
        "preregistration_sha256": sha256((Path(__file__).resolve().parents[1] /
            'research/decision_records/H0001-15m-entry-preregistration-v1.yaml').read_bytes().replace(b'\r\n', b'\n')).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', required=True)
    parser.add_argument('--dataset-id', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = offline_check(args.store, args.dataset_id)
    if report['provider_client_imported']:
        raise AssertionError('Provider client unexpectedly imported')
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
