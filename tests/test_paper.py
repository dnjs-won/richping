from dataclasses import replace
from decimal import Decimal
import json

import pytest

from richping.core import OUTCOME_VERSION_V3, cutoff_at, sessions
from richping.cli import main
from richping.data import Bar, Dataset, create_action_capture, static_members
from richping.engine import observe
from richping.maturity import maturity_followup
from richping.paper import PaperPolicy, PaperStore, paper_report, persist_paper_report, replay_portfolio
from richping.store import Store


def ledger_dataset(dividend_session=None, future_multiplier=1.0):
    days = sessions("2024-01-02", "2024-01-12")[:8]
    prices = {
        "ALFA": [(100, 100), (100, 100), (100, 105), (100, 95), (100, 100), (100, 110), (110, 111), (111, 112)],
        "BETA": [(50, 50)] * 8,
        "SPY": [(200, 200), (200, 200), (200, 204), (204, 202), (202, 210), (210, 220), (220, 221), (221, 222)],
        "QQQ": [(150, 150)] * 8,
    }
    bars = []
    events = []
    for ticker, values in prices.items():
        for index, (opening, close) in enumerate(values):
            if index > 5:
                opening *= future_multiplier
                close *= future_multiplier
            dividend = 1.0 if ticker == "ALFA" and days[index] == dividend_session else 0.0
            bars.append(Bar(ticker, days[index], opening, max(opening, close) + 1,
                            min(opening, close) - 1, close, 1_000_000,
                            cutoff_at(days[index]).isoformat(), dividend=dividend))
            if dividend:
                events.append({"ticker": ticker, "session": days[index], "field": "Dividends",
                               "amount": dividend, "known_at": cutoff_at(days[index]).isoformat()})
    info = {ticker: {"capital_gains_status": "not_applicable_by_provider",
                     "instrument_type": "SYNTHETIC", "quote_currency": "USD",
                     "query_intervals": [{"start": days[0], "end": days[-1],
                                          "capital_gains_status": "not_applicable_by_provider"}]}
            for ticker in prices}
    capture = create_action_capture("synthetic", {}, cutoff_at(days[-1]).isoformat(), info, events)
    metadata = {"source": "paper-fixture", "quality": "synthetic",
                "price_basis": "fixture-no-adjustments", "action_capture": capture}
    return Dataset(bars, metadata,
                   static_members(("ALFA", "BETA"), days[0], days[-1], cutoff_at(days[0]).isoformat())), days


def source_item(data, days, ticker="ALFA", signal_index=0, rank=1, source_key=None):
    bar = data.by_ticker[ticker][days[signal_index]]
    return {"source_key": source_key or f"source-{ticker}-{signal_index}",
            "session": days[signal_index], "ticker": ticker, "rank": rank,
            "score": 80.0, "regime": "RISK_ON_LOW_VOL", "provenance": "TEST",
            "snapshot": {"ticker": ticker, "session": days[signal_index], "regime": "RISK_ON_LOW_VOL",
                         "entry_reference": bar.close, "stop_reference": bar.close - 10,
                         "target_reference": bar.close + 20, "cost": .002,
                         "holding_period": 5, "outcome_version": OUTCOME_VERSION_V3}}


def test_hand_calculated_cash_pnl_mdd_and_spy_comparisons():
    data, days = ledger_dataset()
    report = paper_report(data, [source_item(data, days)], days[1], days[5])
    account = report["candidate"]
    assert account["accepted_fills"] == 1
    buy = next(event for event in account["events"] if event["type"] == "BUY_FILL")
    assert buy["shares"] == 99
    assert buy["cash_debit"] == 9909.90
    assert [row["nav"] for row in account["nav_rows"]] == pytest.approx(
        [99990.10, 100485.10, 99495.10, 99990.10, 100969.20]
    )
    assert account["final"]["cash"] == pytest.approx(100969.20)
    assert account["final"]["realized_pnl"] == pytest.approx(969.20)
    assert account["final"]["unrealized_pnl"] == 0
    assert account["account_metrics"]["mdd"] == pytest.approx(99495.10 / 100485.10 - 1)
    assert report["candidate_2x_cost_stress"]["final"]["nav"] < account["final"]["nav"]
    assert report["comparisons"]["status"] == "COMPLETE"
    assert report["comparisons"]["SPY_cash_waiting_substitute"]["final"]["nav"] == pytest.approx(100959.42)
    assert report["comparisons"]["SPY_buy_and_hold"]["nav"] == pytest.approx(109770.42)


def test_gap_integer_cash_and_same_ticker_recommendation_order():
    data, days = ledger_dataset()
    changed = [replace(bar, open=125.0, high=max(bar.high, 126.0))
               if bar.ticker == "ALFA" and bar.session == days[1] else bar for bar in data.bars]
    data = Dataset(changed, data.metadata, data.members)
    items = [source_item(data, days, signal_index=0),
             source_item(data, days, signal_index=1, source_key="repeat")]
    result = replay_portfolio(data, items, days[1], days[6])
    buy = next(event for event in result["events"] if event["type"] == "BUY_FILL")
    assert buy["shares"] == 79
    assert result["nav_rows"][0]["cash"] == pytest.approx(90115.12)
    assert result["rejections"]["ALREADY_HELD"] == 1
    assert next(event for event in result["events"] if event.get("source_key") == "repeat")["type"] == "INTENT_REJECTED"


def test_unresolved_dividend_never_becomes_zero_or_confirmed_nav():
    base, days = ledger_dataset()
    data, _ = ledger_dataset(dividend_session=days[2])
    result = replay_portfolio(data, [source_item(data, days)], days[1], days[5])
    assert result["final"]["nav_status"] == "UNRESOLVED"
    assert result["final"]["nav"] is None
    assert result["account_metrics"]["return"] is None
    assert any(item["reason"] == "unresolved_cash_dividend_entitlement"
               for item in result["final"]["unresolved"])
    assert any(event["type"] == "SELL_FILL" for event in result["events"])
    assert base.id != data.id


def test_spy_mirror_cash_shortfall_is_explicit():
    data, days = ledger_dataset()
    item = source_item(data, days)
    item["allocation_budget"] = 10_000.0
    result = replay_portfolio(
        data, [item], days[1], days[5], mirror=True,
        policy=PaperPolicy(initial_capital=Decimal("150.00")),
    )
    assert result["accepted_fills"] == 0
    rejected = next(event for event in result["events"] if event["type"] == "INTENT_REJECTED")
    assert rejected["reason"] == "INSUFFICIENT_CASH_OR_INTEGER_LOT"
    assert rejected["planned_allocation_budget"] == 10000.0
    assert rejected["allocation_shortfall"] == 9850.0


def test_conflicting_source_is_quarantined_before_fill():
    data, days = ledger_dataset()
    item = source_item(data, days)
    item["source_conflict"] = ["model-a", "model-b"]
    result = replay_portfolio(data, [item], days[1], days[5])
    assert result["accepted_fills"] == 0
    assert result["final"]["nav_status"] == "UNRESOLVED"
    assert result["rejections"] == {"SOURCE_CONFLICT": 1}


def test_future_bars_do_not_change_past_paper_and_store_is_idempotent(tmp_path):
    data, days = ledger_dataset()
    changed, _ = ledger_dataset(future_multiplier=4.0)
    item = source_item(data, days)
    first = paper_report(data, [item], days[1], days[5])
    second = paper_report(changed, [source_item(changed, days)], days[1], days[5])
    economic = lambda report: [
        {key: row[key] for key in ("session", "nav_status", "nav", "cash", "market_value",
                                    "realized_pnl", "unrealized_pnl", "mdd")}
        for row in report["candidate"]["nav_rows"]
    ]
    assert economic(first) == economic(second)
    db = tmp_path / "paper.db"
    with PaperStore(db) as store:
        manifest = store.save_manifest("RESEARCH_FIXED_REPLAY", {"dataset": data.id})
        store.save_source_items(manifest, [item])
        persist_paper_report(store, manifest, first)
        counts = tuple(store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                       for table in ("manifests", "source_items", "paper_events", "paper_nav"))
        persist_paper_report(store, manifest, first)
        assert counts == tuple(store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                               for table in ("manifests", "source_items", "paper_events", "paper_nav"))


def test_maturity_followup_preserves_original_and_resolves_only_pending(tmp_path):
    data, days = ledger_dataset()
    snapshots = [source_item(data, days, signal_index=0), source_item(data, days, ticker="BETA", signal_index=2)]
    original_end = days[5]
    original_as_of = cutoff_at(original_end).isoformat()
    records, predictions = [], []
    for item in snapshots:
        snap = item["snapshot"]
        outcome = observe(snap, data, 5, original_as_of)
        record = {"fold": 1, "phase": "oos", "session": snap["session"], "ticker": snap["ticker"],
                  "regime": snap["regime"], "score": item["score"],
                  "features": {"price": snap["entry_reference"],
                               "atr": (snap["entry_reference"] - snap["stop_reference"]) / 2},
                  "outcome_status": outcome["status"], "outcome_reason": outcome.get("reason"),
                  "evaluation_eligible": outcome["status"] == "COMPLETE",
                  "net_return": outcome.get("net_return")}
        records.append(record)
        if outcome["status"] == "COMPLETE":
            predictions.append({**outcome, "session": snap["session"], "ticker": snap["ticker"]})
    validation = {"specification": {"dataset": data.id, "model": "fixture", "cost": .002,
                                     "config": {"horizon": 5}},
                  "folds": [{"oos": {"start": days[0], "end": original_end}}],
                  "oos_predictions": predictions}
    failure = {"contract": {"dataset_id": data.id}, "oos_selected_records": records}
    source_db = tmp_path / "source.db"
    validation_path = tmp_path / "validation.json"
    failure_path = tmp_path / "failure.json"
    validation_path.write_text(json.dumps(validation), encoding="utf-8")
    failure_path.write_text(json.dumps(failure), encoding="utf-8")
    with Store(source_db) as store:
        store.save_dataset(data)
    before = source_db.read_bytes()
    report = maturity_followup(source_db, validation_path, failure_path,
                               followup_as_of=cutoff_at(days[-1]).isoformat())
    assert report["verification"]["selected_records"] == 2
    assert report["original"]["outcomes"] == {"COMPLETE": 1, "PENDING": 1, "UNRESOLVED": 0}
    assert report["followup"]["outcomes"] == {"COMPLETE": 2, "PENDING": 0, "UNRESOLVED": 0}
    assert report["transitions"] == {"COMPLETE->COMPLETE": 1, "PENDING->COMPLETE": 1}
    assert source_db.read_bytes() == before


def test_forward_paper_registration_is_future_only_and_does_not_touch_source(tmp_path, capsys):
    data, _ = ledger_dataset()
    source_db = tmp_path / "operations.db"
    paper_db = tmp_path / "paper.db"
    with Store(source_db) as store:
        store.save_dataset(data)
    before = source_db.read_bytes()
    assert main(["paper-init", "--source-db", str(source_db), "--paper-db", str(paper_db)]) == 0
    initialized = json.loads(capsys.readouterr().out)
    assert initialized["status"] == "WAITING_FOR_FUTURE_SHADOW_SNAPSHOTS"
    assert initialized["start_session"] > data.end
    assert source_db.read_bytes() == before
    assert main(["paper-advance", "--source-db", str(source_db), "--paper-db", str(paper_db),
                 "--as-of", cutoff_at(data.end).isoformat(), "--output-dir", str(tmp_path / "output")]) == 0
    waiting = json.loads(capsys.readouterr().out)
    assert waiting["status"] == "WAITING_FOR_START_SESSION"
    assert source_db.read_bytes() == before
