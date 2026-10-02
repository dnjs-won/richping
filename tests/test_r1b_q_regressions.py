"""Independent R1-B Q counterexamples, kept small enough to inspect by hand."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json

import pytest

from richping.core import cutoff_at, open_at
from richping.data import Dataset
from richping.maturity import maturity_followup
from richping.paper import PaperPolicy, PaperStore, paper_report, persist_paper_report, replay_portfolio, spy_buy_and_hold
from richping.store import Store
from test_paper import ledger_dataset, source_item


def test_forward_decision_is_frozen_across_later_capture_and_idempotent(tmp_path):
    data, days = ledger_dataset()
    absent = Dataset(data.bars, {k: v for k, v in data.metadata.items() if k != "action_capture"}, data.members)
    item = source_item(data, days)
    item.update(provenance="FROZEN_FORWARD_SHADOW_SNAPSHOT", issuance_provenance="REAL_TIME",
                run_created_at=cutoff_at(days[0]).isoformat(),
                run_issued_at=cutoff_at(days[0]).isoformat(),
                paper_intent_recorded_at=cutoff_at(days[0]).isoformat())
    db = tmp_path / "paper.db"
    with PaperStore(db) as store:
        manifest = store.save_manifest("FORWARD_PAPER", {"test": True})
        first = paper_report(absent, [item], days[1], days[1], mode="FORWARD_PAPER", manifest_id=manifest)
        assert first["candidate"]["accepted_fills"] == 0
        persist_paper_report(store, manifest, first)
        prior = {"candidate": store.decision_events(first["candidate"]["portfolio_id"]),
                 "stress": store.decision_events(first["candidate_2x_cost_stress"]["portfolio_id"]),
                 "substitute": store.decision_events(
                     first["comparisons"]["SPY_cash_waiting_substitute"]["portfolio_id"])}
        acquired = Dataset(data.bars,
                           {**data.metadata, "action_capture": {**data.metadata["action_capture"],
                               "captured_at": cutoff_at(days[1]).isoformat()}}, data.members)
        later = paper_report(acquired, [item], days[1], days[5], mode="FORWARD_PAPER",
                             manifest_id=manifest, prior_decisions=prior)
        events = later["candidate"]["events"]
        assert any(e["type"] == "INTENT_REJECTED" for e in events)
        assert not any(e["type"] == "BUY_FILL" for e in events)
        assert later["candidate_2x_cost_stress"]["accepted_fills"] == 0
        persist_paper_report(store, manifest, later)
        persist_paper_report(store, manifest, later)
        assert all(json.loads(row[0])["type"] != "BUY_FILL" for row in store.db.execute(
            "SELECT payload FROM paper_events WHERE portfolio_id=?", (later["candidate"]["portfolio_id"],)))
        assert store.db.execute("SELECT count(*) FROM paper_nav WHERE portfolio_id=? AND session=?",
            (later["candidate"]["portfolio_id"], days[1])).fetchone()[0] == 2


def test_forward_requires_preopen_run_and_recorded_intent(tmp_path):
    data, days = ledger_dataset()
    source = tmp_path / "source.db"
    with Store(source) as store:
        store.save_dataset(data)
        for name, created in [("good", cutoff_at(days[0]).isoformat()),
                              ("late", cutoff_at(days[1]).isoformat()),
                              ("published_late", cutoff_at(days[0]).isoformat()),
                              ("missing_issue", cutoff_at(days[0]).isoformat()),
                              ("legacy", "invalid")]:
            snap = source_item(data, days)["snapshot"]
            snap["ticker"] = "ALFA"
            body = {"cutoff": cutoff_at(days[0]).isoformat(),
                    "issuance_provenance": "REAL_TIME",
                    "issued_at": cutoff_at(days[1]).isoformat() if name == "published_late"
                    else cutoff_at(days[0]).isoformat()}
            if name == "missing_issue":
                del body["issued_at"]
            store.db.execute("INSERT INTO runs(id,dataset_id,session,mode,status,attempts,body,created_at) "
                             "VALUES(?,?,?,'shadow','SUCCEEDED',1,?,?)",
                             (name, data.id, days[0], json.dumps(body), created))
            store.db.execute("INSERT INTO recommendations(id,run_id,ticker,rank,snapshot) VALUES(?,?,?,?,?)",
                             (name, name, "ALFA", 1, json.dumps(snap)))
        store.db.commit()
    from richping.paper import forward_source_items
    manifest = {"created_at": cutoff_at(days[0]).isoformat(),
                "payload": {"start_session": days[1]}}
    items = forward_source_items(source, manifest, data, cutoff_at(days[1]).isoformat())
    assert len(items) == 1 and items[0]["source_key"].startswith("forward|good|")
    report = replay_portfolio(data, items, days[1], days[1], mode="FORWARD_PAPER")
    assert report["accepted_fills"] == 0
    assert report["rejections"] == {"FORWARD_INTENT_NOT_PREOPEN": 1}


def test_observation_revision_preserves_prior_event_and_source(tmp_path):
    data, days = ledger_dataset()
    event = {"event_key": "VALUATION_UNRESOLVED:lot:day", "type": "VALUATION_UNRESOLVED",
             "source_key": "lot", "session": days[1], "effective_at": cutoff_at(days[1]).isoformat(),
             "reason": "missing_bar", "observation_dataset_id": data.id}
    nav = {"session": days[1], "as_of": cutoff_at(days[1]).isoformat(),
           "revision": 1, "observation_dataset_id": data.id,
           "session_event_keys": [event["event_key"]]}
    with PaperStore(tmp_path / "revisions.db") as store:
        store.save_replay("portfolio", [event], [nav])
        changed = {**event, "reason": "data_not_yet_known", "observation_dataset_id": "later-vintage"}
        revised_nav = {**nav, "observation_dataset_id": "later-vintage",
                       "session_event_keys": [event["event_key"]]}
        store.save_replay("portfolio", [changed], [revised_nav])
        store.save_replay("portfolio", [changed], [revised_nav])
        recorded = [json.loads(row[0]) for row in store.db.execute(
            "SELECT payload FROM paper_events WHERE portfolio_id='portfolio' ORDER BY rowid")]
        assert len(recorded) == 2
        assert recorded[0] == event
        assert recorded[1]["supersedes"]
        assert recorded[1]["revision_reason"] == "later_observation_or_dataset_vintage"
        assert revised_nav["revision"] == 2
        assert revised_nav["session_event_keys"] == [recorded[1]["event_key"]]


def test_unknown_share_units_quarantine_sale_cash_and_following_buy():
    data, days = ledger_dataset()
    bars = [replace(b, split=2.0) if b.ticker == "ALFA" and b.session == days[2] else b for b in data.bars]
    changed = Dataset(bars, data.metadata, data.members)
    items = [source_item(changed, days), source_item(changed, days, ticker="BETA", signal_index=5)]
    result = replay_portfolio(changed, items, days[1], days[6])
    assert not any(e["type"] == "SELL_FILL" for e in result["events"])
    assert any(e["type"] == "EXIT_UNRESOLVED" for e in result["events"])
    assert result["final"]["cash"] == result["nav_rows"][0]["cash"]
    assert result["final"]["realized_pnl"] == 0
    assert result["final"]["nav"] is None
    assert not any(e["type"] == "BUY_FILL" and e["ticker"] == "BETA" for e in result["events"])


def test_missing_action_capture_after_forward_buy_cannot_certify_sale(tmp_path):
    data, days = ledger_dataset()
    known = Dataset(data.bars, {**data.metadata,
                    "action_capture": {**data.metadata["action_capture"],
                                       "captured_at": cutoff_at(days[1]).isoformat()}}, data.members)
    unknown = Dataset(data.bars, {k: v for k, v in data.metadata.items() if k != "action_capture"}, data.members)
    item = source_item(known, days)
    item.update(provenance="FROZEN_FORWARD_SHADOW_SNAPSHOT", issuance_provenance="REAL_TIME",
                run_created_at=cutoff_at(days[0]).isoformat(),
                run_issued_at=cutoff_at(days[0]).isoformat(),
                paper_intent_recorded_at=cutoff_at(days[0]).isoformat())
    with PaperStore(tmp_path / "paper.db") as store:
        manifest = store.save_manifest("FORWARD_PAPER", {"test": True})
        initial = paper_report(known, [item], days[1], days[1], mode="FORWARD_PAPER", manifest_id=manifest)
        assert initial["candidate"]["accepted_fills"] == 1
        persist_paper_report(store, manifest, initial)
        prior = {"candidate": store.decision_events(initial["candidate"]["portfolio_id"])}
        later = paper_report(unknown, [item], days[1], days[5], mode="FORWARD_PAPER",
                             manifest_id=manifest, prior_decisions=prior)["candidate"]
        assert later["accepted_fills"] == 1
        assert not any(e["type"] == "SELL_FILL" for e in later["events"])
        assert any(e["type"] == "EXIT_UNRESOLVED" for e in later["events"])
        assert later["final"]["cash"] == initial["candidate"]["final"]["cash"]
        assert later["final"]["nav"] is None


def test_spy_missing_pair_stays_in_candidate_denominator():
    data, days = ledger_dataset()
    bars = [b for b in data.bars if not (b.ticker == "SPY" and b.session == days[0])]
    changed = Dataset(bars, data.metadata, data.members)
    report = paper_report(changed, [source_item(changed, days)], days[1], days[5])
    assert report["candidate"]["accepted_fills"] == 1
    assert report["comparisons"]["status"] == "COMPARISON_INCOMPLETE"
    assert report["comparisons"]["pairing"]["denominator"] == 1
    assert report["comparisons"]["pairing"]["matched"] == 0


def test_spy_integer_allocation_shortfall_and_complete_pairing():
    data, days = ledger_dataset()
    policy = PaperPolicy(initial_capital=Decimal("150.00"),
                         position_nav_limit=Decimal("1"), gross_exposure_limit=Decimal("1"))
    shortfall = paper_report(data, [source_item(data, days)], days[1], days[5], policy=policy)
    assert shortfall["candidate"]["accepted_fills"] == 1
    assert shortfall["comparisons"]["pairing"]["denominator"] == 1
    assert shortfall["comparisons"]["pairing"]["matched"] == 0
    assert shortfall["comparisons"]["status"] == "COMPARISON_INCOMPLETE"
    normal = paper_report(data, [source_item(data, days)], days[1], days[5])
    assert normal["comparisons"]["pairing"]["denominator"] == 1
    assert normal["comparisons"]["pairing"]["matched"] == 1


def test_forward_spy_interim_mark_has_no_sale_cost_and_blocks_future_known_data():
    data, days = ledger_dataset()
    data = Dataset(data.bars, {**data.metadata,
                   "action_capture": {**data.metadata["action_capture"],
                                      "captured_at": cutoff_at(days[1]).isoformat()}}, data.members)
    interim = spy_buy_and_hold(data, days[1], days[2], mode="FORWARD_PAPER",
                               as_of=cutoff_at(days[2]).isoformat())
    assert interim["status"] == "COMPARISON_INCOMPLETE"
    assert interim["sale_event"] is None
    assert interim["price_only_diagnostic_nav"] > 100000
    settled = spy_buy_and_hold(data, days[1], days[2], mode="FORWARD_PAPER",
                               as_of=cutoff_at(days[2]).isoformat(), liquidate=True)
    assert settled["status"] == "COMPLETE"
    assert settled["sale_event"]["cash_credit"] > 0
    assert settled["nav"] < interim["price_only_diagnostic_nav"]
    future = [replace(b, known_at=cutoff_at(days[5]).isoformat())
              if b.ticker == "SPY" and b.session == days[2] else b for b in data.bars]
    changed = Dataset(future, data.metadata, data.members)
    blocked = spy_buy_and_hold(changed, days[1], days[2], mode="FORWARD_PAPER",
                               as_of=cutoff_at(days[2]).isoformat())
    assert blocked["status"] == "COMPARISON_INCOMPLETE"
    assert "data_not_yet_known" in blocked["reasons"]


@pytest.mark.parametrize("mutation", ["return", "status", "duplicate", "missing"])
def test_maturity_rejects_prediction_tampering(tmp_path, mutation):
    from richping.engine import observe
    data, days = ledger_dataset()
    source = tmp_path / "source.db"
    with Store(source) as store:
        store.save_dataset(data)
    item = source_item(data, days)
    outcome = observe(item["snapshot"], data, 5, cutoff_at(days[5]).isoformat())
    record = {"fold": 1, "phase": "oos", "session": days[0], "ticker": "ALFA",
              "regime": item["regime"], "score": 80.0,
              "features": {"price": 100.0, "atr": 5.0}, "outcome_status": outcome["status"],
              "outcome_reason": outcome.get("reason"), "net_return": outcome.get("net_return")}
    prediction = {**outcome, "session": days[0], "ticker": "ALFA", "regime": item["regime"]}
    predictions = [prediction]
    if mutation == "return":
        predictions[0]["net_return"] += .01
    elif mutation == "status":
        predictions[0]["status"] = "PENDING"
    elif mutation == "duplicate":
        predictions.append(deepcopy(prediction))
    else:
        predictions.clear()
    validation = {"specification": {"dataset": data.id, "cost": .002, "config": {"horizon": 5}},
                  "folds": [{"oos": {"start": days[0], "end": days[5]}}],
                  "oos_predictions": predictions}
    vpath, fpath = tmp_path / "validation.json", tmp_path / "failure.json"
    vpath.write_text(json.dumps(validation), encoding="utf-8")
    fpath.write_text(json.dumps({"oos_selected_records": [record]}), encoding="utf-8")
    with pytest.raises(ValueError, match="SOURCE_RECONSTRUCTION_UNVERIFIED"):
        maturity_followup(source, vpath, fpath)
