"""Minimal append-only paper portfolio accounting for Richping R1.

This is an execution model for research and forward paper evidence.  It never
places orders and never changes recommendation, outcome, or operational risk
state.
"""

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import json
import math
from pathlib import Path
import sqlite3

from .core import canonical, cutoff_at, digest, next_sessions, open_at, timestamp, utcnow
from .data import inspect_action_capture


LEDGER_SCHEMA = "richping_paper_ledger_v1"
FOLLOWUP_SCHEMA = "richping_maturity_followup_v1"
INITIAL_CAPITAL = Decimal("100000.00")
LOT_BUDGET = Decimal("10000.00")
POSITION_LIMIT = 5
GROSS_EXPOSURE_LIMIT = Decimal("0.50")
POSITION_NAV_LIMIT = Decimal("0.10")
SIDE_COMMISSION_BPS = Decimal("5")
SIDE_SLIPPAGE_BPS = Decimal("5")


PAPER_SCHEMA = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS manifests(
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, schema_version TEXT NOT NULL,
 created_at TEXT NOT NULL, payload TEXT NOT NULL, input_hashes TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_items(
 id TEXT PRIMARY KEY, manifest_id TEXT NOT NULL REFERENCES manifests(id),
 source_key TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(manifest_id,source_key)
);
CREATE TABLE IF NOT EXISTS followup(
 id TEXT PRIMARY KEY, source_item_id TEXT NOT NULL REFERENCES source_items(id),
 dataset_id TEXT NOT NULL, as_of TEXT NOT NULL, policy TEXT NOT NULL, payload TEXT NOT NULL,
 UNIQUE(source_item_id,dataset_id,as_of,policy)
);
CREATE TABLE IF NOT EXISTS paper_events(
 id TEXT PRIMARY KEY, portfolio_id TEXT NOT NULL, event_key TEXT NOT NULL,
 effective_at TEXT NOT NULL, known_at TEXT, recorded_at TEXT NOT NULL, payload TEXT NOT NULL,
 UNIQUE(portfolio_id,event_key)
);
CREATE TABLE IF NOT EXISTS paper_nav(
 portfolio_id TEXT NOT NULL, session TEXT NOT NULL, as_of TEXT NOT NULL,
 revision INTEGER NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(portfolio_id,session,as_of,revision)
);
COMMIT;
"""


def _d(value):
    return Decimal(str(value))


def _money(value):
    return _d(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _json_number(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _fee(notional, bps):
    return _money(_d(notional) * _d(bps) / Decimal("10000"))


def _buy_debit(price, shares, commission_bps, slippage_bps):
    notional = _money(_d(price) * shares)
    commission = _fee(notional, commission_bps)
    slippage = _fee(notional, slippage_bps)
    return notional, commission, slippage, notional + commission + slippage


def _sell_credit(price, shares, commission_bps, slippage_bps):
    notional = _money(_d(price) * shares)
    commission = _fee(notional, commission_bps)
    slippage = _fee(notional, slippage_bps)
    return notional, commission, slippage, notional - commission - slippage


def affordable_shares(budget, price, commission_bps=SIDE_COMMISSION_BPS,
                      slippage_bps=SIDE_SLIPPAGE_BPS):
    budget, price = _d(budget), _d(price)
    if budget <= 0 or price <= 0:
        return 0
    rate = Decimal("1") + (_d(commission_bps) + _d(slippage_bps)) / Decimal("10000")
    shares = int((budget / (price * rate)).to_integral_value(rounding=ROUND_DOWN))
    while shares > 0 and _buy_debit(price, shares, commission_bps, slippage_bps)[3] > budget:
        shares -= 1
    return shares


@dataclass(frozen=True)
class PaperPolicy:
    initial_capital: Decimal = INITIAL_CAPITAL
    lot_budget: Decimal = LOT_BUDGET
    position_limit: int = POSITION_LIMIT
    gross_exposure_limit: Decimal = GROSS_EXPOSURE_LIMIT
    position_nav_limit: Decimal = POSITION_NAV_LIMIT
    commission_bps: Decimal = SIDE_COMMISSION_BPS
    slippage_bps: Decimal = SIDE_SLIPPAGE_BPS

    def payload(self):
        return {"initial_capital": float(self.initial_capital), "lot_budget": float(self.lot_budget),
                "position_limit": self.position_limit,
                "gross_exposure_limit": float(self.gross_exposure_limit),
                "position_nav_limit": float(self.position_nav_limit),
                "commission_bps_per_side": float(self.commission_bps),
                "slippage_bps_per_side": float(self.slippage_bps),
                "integer_shares": True, "leverage": False, "cash_interest": 0.0,
                "holding": "next_open_to_5th_session_close"}


class PaperStore:
    """R1-only SQLite store. Existing operational Store schema is untouched."""

    def __init__(self, path, read_only=False):
        self.path = Path(path)
        if read_only:
            self.db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA query_only=ON")
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(PAPER_SCHEMA)
        for table in ("manifests", "source_items", "followup", "paper_events", "paper_nav"):
            for action in ("UPDATE", "DELETE"):
                self.db.execute(
                    f"CREATE TRIGGER IF NOT EXISTS freeze_{table}_{action} BEFORE {action} ON {table} "
                    f"BEGIN SELECT RAISE(ABORT, 'immutable {table}'); END"
                )
        self.db.commit()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def save_manifest(self, kind, payload, input_hashes=None, created_at=None):
        body = {**deepcopy(payload), "kind": kind, "schema": LEDGER_SCHEMA}
        manifest_id = digest(body)
        row = (manifest_id, kind, LEDGER_SCHEMA, created_at or utcnow(), canonical(body),
               canonical(input_hashes or {}))
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO manifests VALUES(?,?,?,?,?,?)", row)
        stored = self.db.execute("SELECT payload,input_hashes FROM manifests WHERE id=?", (manifest_id,)).fetchone()
        if stored["payload"] != row[4] or stored["input_hashes"] != row[5]:
            raise ValueError("Manifest identity collision")
        return manifest_id

    def save_source_items(self, manifest_id, items):
        with self.db:
            for item in items:
                source_key = item["source_key"]
                item_id = digest([manifest_id, source_key])
                payload = canonical(item)
                self.db.execute("INSERT OR IGNORE INTO source_items VALUES(?,?,?,?)",
                                (item_id, manifest_id, source_key, payload))
                stored = self.db.execute("SELECT payload FROM source_items WHERE id=?", (item_id,)).fetchone()[0]
                if stored != payload:
                    raise ValueError("Source item identity collision")

    def save_followup(self, manifest_id, report):
        rows = {row["source_key"]: row for row in report["source_items"]}
        with self.db:
            for source_key, row in rows.items():
                item_id = digest([manifest_id, source_key])
                payload = {"original": row["original"], "followup": row["followup"],
                           "original_as_of": row["original_as_of"],
                           "followup_as_of": row["followup_as_of"]}
                followup_id = digest([item_id, report["followup"]["dataset_id"],
                                      report["followup"]["as_of"], FOLLOWUP_SCHEMA])
                values = (followup_id, item_id, report["followup"]["dataset_id"],
                          report["followup"]["as_of"], FOLLOWUP_SCHEMA, canonical(payload))
                self.db.execute("INSERT OR IGNORE INTO followup VALUES(?,?,?,?,?,?)", values)
                stored = self.db.execute("SELECT payload FROM followup WHERE id=?", (followup_id,)).fetchone()[0]
                if stored != values[-1]:
                    raise ValueError("Follow-up identity collision")

    def save_replay(self, portfolio_id, events, nav_rows, recorded_at=None):
        recorded_at = recorded_at or utcnow()
        with self.db:
            for event in events:
                payload = canonical(event)
                event_key = event["event_key"]
                event_id = digest([portfolio_id, event_key])
                values = (event_id, portfolio_id, event_key, event["effective_at"],
                          event.get("known_at"), recorded_at, payload)
                self.db.execute("INSERT OR IGNORE INTO paper_events VALUES(?,?,?,?,?,?,?)", values)
                stored = self.db.execute("SELECT payload FROM paper_events WHERE id=?", (event_id,)).fetchone()[0]
                if stored != payload:
                    raise ValueError("Paper event identity collision")
            for row in nav_rows:
                values = (portfolio_id, row["session"], row["as_of"], row.get("revision", 1), canonical(row))
                self.db.execute("INSERT OR IGNORE INTO paper_nav VALUES(?,?,?,?,?)", values)
                stored = self.db.execute(
                    "SELECT payload FROM paper_nav WHERE portfolio_id=? AND session=? AND as_of=? AND revision=?",
                    values[:4],
                ).fetchone()[0]
                if stored != values[-1]:
                    raise ValueError("Paper NAV identity collision")

    def manifest(self, manifest_id=None):
        if manifest_id:
            row = self.db.execute("SELECT * FROM manifests WHERE id=?", (manifest_id,)).fetchone()
        else:
            row = self.db.execute("SELECT * FROM manifests ORDER BY rowid DESC LIMIT 1").fetchone()
        if not row:
            raise ValueError("No paper manifest")
        return {**dict(row), "payload": json.loads(row["payload"]),
                "input_hashes": json.loads(row["input_hashes"])}

    def source_items(self, manifest_id):
        return [json.loads(row[0]) for row in self.db.execute(
            "SELECT payload FROM source_items WHERE manifest_id=? ORDER BY source_key", (manifest_id,))]


def _valid_price(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def _bar_available(bar, as_of, mode):
    if bar is None:
        return False, "missing_or_delisted_session"
    if not _valid_price(bar.open) or not _valid_price(bar.close) or not _valid_price(bar.volume):
        return False, "invalid_or_nontrading_bar"
    if mode == "FORWARD_PAPER" and timestamp(bar.known_at) > timestamp(as_of):
        return False, "data_not_yet_known"
    return True, None


def _action_reason(dataset, ticker, session, as_of, mode, bar):
    if bar is None:
        return "missing_or_delisted_session"
    if bar.split:
        return "stock_split_requires_accounting"
    inspection = inspect_action_capture(dataset, ticker, [session], as_of=as_of,
                                        mode="shadow" if mode == "FORWARD_PAPER" else "research")
    if inspection.is_pending:
        return "data_not_yet_known"
    if inspection.has_capital_gains:
        return "unsupported_capital_gains_distribution"
    if bar.dividend > 0:
        return "unresolved_cash_dividend_entitlement"
    if not inspection.is_confirmed:
        return "action_capture_unknown"
    return None


def _event(kind, source_key, session, **values):
    return {"event_key": f"{kind}:{source_key}:{session}", "type": kind,
            "source_key": source_key, "session": session,
            "effective_at": values.pop("effective_at", cutoff_at(session).isoformat()), **values}


def replay_portfolio(dataset, source_items, start_session, end_session, *, mode="RESEARCH_FIXED_REPLAY",
                     policy=None, as_of=None, portfolio_id=None, mirror=False):
    """Replay immutable source intents into a deterministic integer-share ledger."""
    policy = policy or PaperPolicy()
    as_of = as_of or cutoff_at(end_session).isoformat()
    if start_session not in dataset.positions or end_session not in dataset.positions:
        raise ValueError("Paper period outside dataset")
    if dataset.positions[start_session] > dataset.positions[end_session]:
        raise ValueError("Invalid paper period")
    sessions = dataset.sessions[dataset.positions[start_session]:dataset.positions[end_session] + 1]
    portfolio_id = portfolio_id or digest({"schema": LEDGER_SCHEMA, "mode": mode,
        "dataset": dataset.id, "start": start_session, "end": end_session,
        "sources": [item["source_key"] for item in source_items], "policy": policy.payload(),
        "mirror": mirror})
    by_entry = {}
    normalized = []
    for source in source_items:
        item = deepcopy(source)
        snap = item["snapshot"]
        entry_session = next_sessions(snap["session"], 1)[0]
        exit_session = next_sessions(snap["session"], snap.get("holding_period", 5))[-1]
        item.update(entry_session=entry_session, exit_session=exit_session)
        normalized.append(item)
        if entry_session in dataset.positions and start_session <= entry_session <= end_session:
            by_entry.setdefault(entry_session, []).append(item)
    cash = _money(policy.initial_capital)
    positions = []
    events = [_event("INITIAL_CASH", portfolio_id, start_session,
                     effective_at=open_at(start_session).isoformat(), amount=float(cash), known_at=None)]
    nav_rows = []
    last_marks = {}
    unresolved = {}
    accepted = []
    realized = Decimal("0.00")
    confirmed_values = [policy.initial_capital]
    peak = policy.initial_capital
    confirmed_mdd = Decimal("0")
    last_confirmed_nav = policy.initial_capital

    for session in sessions:
        session_events = []
        prior_exposure = sum(last_marks.get(pos["lot_id"], Decimal("0")) for pos in positions)
        admission_block = bool(unresolved)
        available_exposure = max(Decimal("0"), policy.gross_exposure_limit * last_confirmed_nav - prior_exposure)
        for item in sorted(by_entry.get(session, []),
                           key=lambda value: (value.get("rank") or 9999, value["snapshot"]["ticker"],
                                              value["source_key"])):
            snap = item["snapshot"]
            original_ticker = snap["ticker"]
            ticker = "SPY" if mirror else original_ticker
            source_key = item["source_key"]
            reason = None
            if item.get("source_conflict"):
                reason = "SOURCE_CONFLICT"
                unresolved[f"source:{source_key}"] = reason
                admission_block = True
            elif admission_block:
                reason = "PAPER_ADMISSION_BLOCK_UNRESOLVED_NAV"
            elif not mirror and any(pos["ticker"] == ticker for pos in positions):
                reason = "ALREADY_HELD"
            elif len(positions) >= policy.position_limit:
                reason = "POSITION_LIMIT"
            signal_bar = dataset.by_ticker.get(ticker, {}).get(snap["session"])
            if reason is None and (signal_bar is None or
                                   (not mirror and not math.isclose(signal_bar.close, snap["entry_reference"], rel_tol=1e-8))):
                reason = "PRICE_VINTAGE_CHANGED"
                unresolved[f"intent:{source_key}"] = reason
                admission_block = True
            bar = dataset.by_ticker.get(ticker, {}).get(session)
            available, unavailable_reason = _bar_available(bar, as_of, mode)
            if reason is None and not available:
                reason = "PENDING_DATA" if unavailable_reason == "data_not_yet_known" else "UNFILLED_OR_UNKNOWN"
                unresolved[f"fill:{source_key}"] = unavailable_reason
                admission_block = True
            if mirror:
                planned_budget = _d(item["allocation_budget"])
                budget = min(planned_budget, cash)
                allocation_shortfall = max(Decimal("0"), planned_budget - budget)
            else:
                planned_budget = None
                allocation_shortfall = Decimal("0")
                budget = min(policy.lot_budget, policy.position_nav_limit * last_confirmed_nav,
                             available_exposure, cash)
            shares = affordable_shares(budget, bar.open, policy.commission_bps,
                                       policy.slippage_bps) if reason is None else 0
            if reason is None and shares < 1:
                reason = "INSUFFICIENT_CASH_OR_INTEGER_LOT"
            if reason is not None:
                event = _event("INTENT_REJECTED", source_key, session,
                               effective_at=open_at(session).isoformat(), ticker=ticker,
                               original_ticker=original_ticker, reason=reason,
                               allocation_budget=float(_money(budget)),
                               planned_allocation_budget=(float(_money(planned_budget))
                                                          if planned_budget is not None else None),
                               allocation_shortfall=float(_money(allocation_shortfall)))
                events.append(event); session_events.append(event)
                continue
            notional, commission, slippage, debit = _buy_debit(
                bar.open, shares, policy.commission_bps, policy.slippage_bps
            )
            if debit > cash:
                raise AssertionError("Paper cash would become negative")
            cash -= debit
            available_exposure = max(Decimal("0"), available_exposure - debit)
            lot_id = digest([portfolio_id, source_key, session])
            position = {"lot_id": lot_id, "source_key": source_key, "ticker": ticker,
                        "original_ticker": original_ticker, "shares": shares,
                        "entry_session": session, "exit_session": item["exit_session"],
                        "entry_price": _money(bar.open), "cost_basis": debit,
                        "unit_unresolved": False}
            positions.append(position)
            accepted.append({"source_key": source_key, "allocation_budget": float(_money(budget)),
                             "planned_allocation_budget": (float(_money(planned_budget))
                                                           if planned_budget is not None else None),
                             "allocation_shortfall": float(_money(allocation_shortfall)),
                             "debit": float(debit), "shares": shares, "entry_session": session,
                             "exit_session": item["exit_session"]})
            event = _event("BUY_FILL", source_key, session, effective_at=open_at(session).isoformat(),
                           known_at=bar.known_at, ticker=ticker, shares=shares,
                           price=float(_money(bar.open)), notional=float(notional),
                           commission=float(commission), slippage=float(slippage),
                           cash_debit=float(debit), allocation_budget=float(_money(budget)),
                           planned_allocation_budget=(float(_money(planned_budget))
                                                      if planned_budget is not None else None),
                           allocation_shortfall=float(_money(allocation_shortfall)))
            events.append(event); session_events.append(event)

        marks = {}
        exits = []
        for position in sorted(positions, key=lambda value: value["source_key"]):
            bar = dataset.by_ticker.get(position["ticker"], {}).get(session)
            available, unavailable_reason = _bar_available(bar, as_of, mode)
            if not available:
                reason = unavailable_reason
                unresolved[f"mark:{position['lot_id']}:{session}"] = reason
                event = _event("VALUATION_UNRESOLVED", position["source_key"], session,
                               ticker=position["ticker"], reason=reason)
                events.append(event); session_events.append(event)
                continue
            action_reason = _action_reason(dataset, position["ticker"], session, as_of, mode, bar)
            if action_reason:
                unresolved[f"action:{position['lot_id']}:{session}"] = action_reason
                if action_reason == "stock_split_requires_accounting":
                    position["unit_unresolved"] = True
                event = _event("CORPORATE_ACTION_UNRESOLVED", position["source_key"], session,
                               ticker=position["ticker"], reason=action_reason,
                               dividend=bar.dividend, split=bar.split, known_at=bar.known_at)
                events.append(event); session_events.append(event)
            if session == position["exit_session"]:
                if position["unit_unresolved"]:
                    event = _event("EXIT_UNRESOLVED", position["source_key"], session,
                                   ticker=position["ticker"], reason="share_units_unresolved")
                    events.append(event); session_events.append(event)
                else:
                    notional, commission, slippage, credit = _sell_credit(
                        bar.close, position["shares"], policy.commission_bps, policy.slippage_bps
                    )
                    cash += credit
                    pnl = credit - position["cost_basis"]
                    realized += pnl
                    event = _event("SELL_FILL", position["source_key"], session,
                                   ticker=position["ticker"], shares=position["shares"],
                                   price=float(_money(bar.close)), notional=float(notional),
                                   commission=float(commission), slippage=float(slippage),
                                   cash_credit=float(credit), realized_pnl=float(pnl), known_at=bar.known_at)
                    events.append(event); session_events.append(event)
                    exits.append(position)
                    continue
            marks[position["lot_id"]] = _money(_d(bar.close) * position["shares"])
        for position in exits:
            positions.remove(position)
            last_marks.pop(position["lot_id"], None)
        last_marks.update(marks)

        market_value = sum((last_marks.get(pos["lot_id"], Decimal("0")) for pos in positions), Decimal("0"))
        unrealized = sum((last_marks.get(pos["lot_id"], Decimal("0")) - pos["cost_basis"]
                          for pos in positions if pos["lot_id"] in last_marks), Decimal("0"))
        known_component = cash + market_value
        nav_status = "UNRESOLVED" if unresolved else "CONFIRMED"
        nav = None if unresolved else _money(known_component)
        mdd = None
        if nav is not None:
            last_confirmed_nav = nav
            confirmed_values.append(nav)
            peak = max(peak, nav)
            confirmed_mdd = min(confirmed_mdd, nav / peak - Decimal("1"))
            mdd = confirmed_mdd
        row = {"session": session, "as_of": as_of, "revision": 1,
               "nav_status": nav_status, "nav": _json_number(nav),
               "known_component": float(_money(known_component)), "cash": float(_money(cash)),
               "market_value": float(_money(market_value)), "realized_pnl": float(_money(realized)),
               "unrealized_pnl": float(_money(unrealized)), "mdd": _json_number(mdd),
               "confirmed_prefix_mdd": float(confirmed_mdd),
               "gross_exposure": (float(market_value / nav) if nav and nav != 0 else None),
               "positions": [{**{k: v for k, v in pos.items() if k not in {"entry_price", "cost_basis"}},
                               "entry_price": float(pos["entry_price"]),
                               "cost_basis": float(pos["cost_basis"]),
                               "mark_value": float(last_marks[pos["lot_id"]]) if pos["lot_id"] in last_marks else None}
                              for pos in positions],
               "unresolved": [{"key": key, "reason": value} for key, value in sorted(unresolved.items())],
               "session_event_keys": [event["event_key"] for event in session_events]}
        nav_rows.append(row)

    if cash < 0:
        raise AssertionError("Negative paper cash")
    result = {"schema": LEDGER_SCHEMA, "portfolio_id": portfolio_id, "mode": mode,
              "dataset_id": dataset.id, "period": {"start": start_session, "end": end_session},
              "as_of": as_of, "policy": policy.payload(), "source_items": len(source_items),
              "accepted_fills": len(accepted), "accepted": accepted,
              "rejections": dict(Counter(event["reason"] for event in events
                                          if event["type"] == "INTENT_REJECTED")),
              "final": nav_rows[-1] if nav_rows else None, "events": events, "nav_rows": nav_rows,
              "account_metrics": {"return": (float(nav_rows[-1]["nav"] / float(policy.initial_capital) - 1)
                                                     if nav_rows and nav_rows[-1]["nav"] is not None else None),
                                  "mdd": nav_rows[-1]["mdd"] if nav_rows else None,
                                  "confirmed_prefix_mdd": float(confirmed_mdd)},
              "evidence": "RESEARCH_REPLAY" if mode.startswith("RESEARCH") else "FORWARD_PAPER",
              "alpha": "INSUFFICIENT_EVIDENCE"}
    return result


def spy_buy_and_hold(dataset, start_session, end_session, policy=None, as_of=None):
    policy = policy or PaperPolicy()
    as_of = as_of or cutoff_at(end_session).isoformat()
    entry = dataset.by_ticker.get("SPY", {}).get(start_session)
    exit_bar = dataset.by_ticker.get("SPY", {}).get(end_session)
    if not entry or not exit_bar or not _valid_price(entry.open) or not _valid_price(exit_bar.close):
        return {"status": "COMPARISON_INCOMPLETE", "reason": "missing_SPY_price", "nav": None}
    shares = affordable_shares(policy.initial_capital, entry.open, policy.commission_bps, policy.slippage_bps)
    _, _, _, debit = _buy_debit(entry.open, shares, policy.commission_bps, policy.slippage_bps)
    _, _, _, credit = _sell_credit(exit_bar.close, shares, policy.commission_bps, policy.slippage_bps)
    price_only_nav = policy.initial_capital - debit + credit
    reasons = set()
    period = dataset.sessions[dataset.positions[start_session]:dataset.positions[end_session] + 1]
    for session in period:
        bar = dataset.by_ticker.get("SPY", {}).get(session)
        available, reason = _bar_available(bar, as_of, "RESEARCH_FIXED_REPLAY")
        if not available:
            reasons.add(reason)
            continue
        action = _action_reason(dataset, "SPY", session, as_of, "RESEARCH_FIXED_REPLAY", bar)
        if action:
            reasons.add(action)
    complete = not reasons
    return {"status": "COMPLETE" if complete else "COMPARISON_INCOMPLETE",
            "reasons": sorted(reasons), "initial_capital": float(policy.initial_capital),
            "shares": shares, "cash_remainder_after_entry": float(policy.initial_capital - debit),
            "price_only_diagnostic_nav": float(price_only_nav),
            "nav": float(price_only_nav) if complete else None,
            "return": float(price_only_nav / policy.initial_capital - 1) if complete else None,
            "dividend_total_return_verified": complete}


def paper_report(dataset, source_items, start_session, end_session, *, mode="RESEARCH_FIXED_REPLAY",
                 policy=None, as_of=None, manifest_id=None):
    policy = policy or PaperPolicy()
    candidate_portfolio_id = digest([manifest_id, "CANDIDATE"]) if manifest_id else None
    candidate = replay_portfolio(dataset, source_items, start_session, end_session,
                                 mode=mode, policy=policy, as_of=as_of,
                                 portfolio_id=candidate_portfolio_id)
    stress_policy = PaperPolicy(
        initial_capital=policy.initial_capital, lot_budget=policy.lot_budget,
        position_limit=policy.position_limit, gross_exposure_limit=policy.gross_exposure_limit,
        position_nav_limit=policy.position_nav_limit,
        commission_bps=policy.commission_bps * 2, slippage_bps=policy.slippage_bps * 2,
    )
    stress_portfolio_id = digest([manifest_id, "CANDIDATE_2X_COST"]) if manifest_id else None
    stress = replay_portfolio(dataset, source_items, start_session, end_session,
                              mode=mode, policy=stress_policy, as_of=as_of,
                              portfolio_id=stress_portfolio_id)
    accepted = {row["source_key"]: row for row in candidate["accepted"]}
    mirror_items = []
    for item in source_items:
        if item["source_key"] not in accepted:
            continue
        snap = deepcopy(item["snapshot"])
        spy_bar = dataset.by_ticker.get("SPY", {}).get(snap["session"])
        if spy_bar is None:
            continue
        snap.update(ticker="SPY", entry_reference=spy_bar.close,
                    stop_reference=spy_bar.close * .9, target_reference=spy_bar.close * 1.2)
        mirror_items.append({**deepcopy(item), "snapshot": snap,
                             "allocation_budget": accepted[item["source_key"]]["allocation_budget"]})
    substitute = replay_portfolio(dataset, mirror_items, start_session, end_session,
                                  mode=mode, policy=policy, as_of=as_of,
                                  portfolio_id=digest([candidate["portfolio_id"], "SPY_SUBSTITUTE"]), mirror=True)
    buy_hold = spy_buy_and_hold(dataset, start_session, end_session, policy, as_of)
    comparison_reasons = []
    if buy_hold["status"] != "COMPLETE":
        comparison_reasons.extend(f"buy_hold:{reason}" for reason in buy_hold.get("reasons", []))
    if substitute["final"] and substitute["final"]["nav_status"] != "CONFIRMED":
        comparison_reasons.extend(f"substitute:{item['reason']}" for item in substitute["final"]["unresolved"])
    if any(row.get("allocation_shortfall", 0) > 0 for row in substitute["accepted"]):
        comparison_reasons.append("substitute:allocation_shortfall")
    if substitute["accepted_fills"] < len(mirror_items):
        comparison_reasons.append("substitute:allocation_or_fill_shortfall")
    if candidate["final"] and candidate["final"]["nav_status"] != "CONFIRMED":
        comparison_reasons.extend(f"candidate:{item['reason']}" for item in candidate["final"]["unresolved"])
    return {"schema": LEDGER_SCHEMA, "mode": mode, "dataset_id": dataset.id,
            "period": {"start": start_session, "end": end_session}, "candidate": candidate,
            "candidate_2x_cost_stress": stress,
            "comparisons": {"status": "COMPLETE" if not comparison_reasons else "COMPARISON_INCOMPLETE",
                            "reasons": sorted(set(comparison_reasons)),
                            "SPY_buy_and_hold": buy_hold,
                            "SPY_cash_waiting_substitute": substitute,
                            "assumptions": {"same_initial_capital": float(policy.initial_capital),
                                "same_period": True, "integer_shares": True,
                                "cash_interest": 0.0, "costs_per_side_bps":
                                    float(policy.commission_bps + policy.slippage_bps),
                                "dividend_total_return_required": True}},
            "diagnostic_separation": {"recommendation_metrics_are_account_metrics": False,
                                      "cohort_drawdown_is_account_mdd": False},
            "alpha": "INSUFFICIENT_EVIDENCE"}


def persist_paper_report(store, manifest_id, report):
    candidate = report["candidate"]
    store.save_replay(candidate["portfolio_id"], candidate["events"], candidate["nav_rows"])
    stress = report["candidate_2x_cost_stress"]
    store.save_replay(stress["portfolio_id"], stress["events"], stress["nav_rows"])
    substitute = report["comparisons"]["SPY_cash_waiting_substitute"]
    store.save_replay(substitute["portfolio_id"], substitute["events"], substitute["nav_rows"])


def operational_replay_sources(database, dataset, config, start_session, end_session):
    """Run the existing rolling scan/risk path inside an isolated research DB."""
    from .engine import Engine
    from .pipeline import scan
    from .store import Store

    engine = Engine(dataset, config)
    items, reports = [], []
    with Store(database) as store:
        store.save_dataset(dataset)
        for session in dataset.sessions[dataset.positions[start_session]:dataset.positions[end_session] + 1]:
            report = scan(store, dataset, config, session, mode="research", engine=engine)
            reports.append({"session": session, "state": report["state"],
                            "state_reason": report["state_reason"],
                            "recommendations": len(report["recommendations"])})
            for snapshot in report["recommendations"]:
                items.append({"source_key": f"operational|{report['run_id']}|{snapshot['ticker']}",
                              "session": session, "ticker": snapshot["ticker"],
                              "rank": snapshot["rank"], "score": snapshot["score"],
                              "regime": snapshot["regime"], "snapshot": snapshot,
                              "provenance": "ISOLATED_RESEARCH_OPERATIONAL_REPLAY"})
    return items, {"sessions": len(reports), "recommendations": len(items),
                   "state_reasons": dict(Counter(row["state_reason"] for row in reports)),
                   "reports": reports}


def forward_source_items(source_db, manifest, dataset, as_of):
    """Read only post-registration shadow snapshots eligible for forward paper."""
    from .store import Store

    created_at = manifest["created_at"]
    start = manifest["payload"]["start_session"]
    items = []
    with Store(source_db, read_only=True) as store:
        rows = store.db.execute(
            "SELECT r.id run_id,r.session,r.created_at,r.body,q.ticker,q.rank,q.snapshot "
            "FROM runs r JOIN recommendations q ON q.run_id=r.id "
            "WHERE r.mode='shadow' AND r.status='SUCCEEDED' AND r.created_at>=? AND r.session>=? "
            "ORDER BY r.session,q.rank,q.ticker,r.created_at,r.id", (created_at, start)
        ).fetchall()
        grouped = {}
        for row in rows:
            body = json.loads(row["body"])
            snapshot = json.loads(row["snapshot"])
            if timestamp(body["cutoff"]) >= timestamp(open_at(next_sessions(row["session"], 1)[0])):
                continue
            if timestamp(body["cutoff"]) > timestamp(as_of):
                continue
            if snapshot.get("data_id") != dataset.id:
                # A newer dataset may be used only if the frozen signal close still matches;
                # replay_portfolio performs that check before any fill.
                pass
            key = (row["session"], row["ticker"], snapshot.get("holding_period", 5))
            grouped.setdefault(key, []).append((row, snapshot))
        decision_fields = ("ticker", "session", "entry_reference", "stop_reference", "target_reference",
                           "holding_period", "cost", "outcome_version", "risk_cohort_id")
        for key, candidates in sorted(grouped.items()):
            first_row, first = candidates[0]
            signatures = {canonical({field: snap.get(field) for field in decision_fields})
                          for _, snap in candidates}
            conflict = len(signatures) > 1
            items.append({"source_key": f"forward|{first_row['run_id']}|{first_row['ticker']}",
                          "session": first_row["session"], "ticker": first_row["ticker"],
                          "rank": first_row["rank"], "score": first.get("score"),
                          "regime": first.get("regime"), "snapshot": first,
                          "provenance": "FROZEN_FORWARD_SHADOW_SNAPSHOT",
                          "registered_after": created_at,
                          "duplicate_sources_ignored": 0 if conflict else len(candidates) - 1,
                          "source_conflict": ([row["run_id"] for row, _ in candidates] if conflict else None)})
    return items


def stored_paper_summary(store, manifest_id=None):
    manifest = store.manifest(manifest_id)
    groups = []
    candidate_id = digest([manifest["id"], "CANDIDATE"])
    portfolio_ids = [candidate_id, digest([manifest["id"], "CANDIDATE_2X_COST"]),
                     digest([candidate_id, "SPY_SUBSTITUTE"])]
    for portfolio_id in portfolio_ids:
        row = store.db.execute(
            "SELECT payload FROM paper_nav WHERE portfolio_id=? ORDER BY session DESC,as_of DESC,revision DESC LIMIT 1",
            (portfolio_id,)).fetchone()
        final = json.loads(row[0]) if row else None
        groups.append({"portfolio_id": portfolio_id, "final": final,
                       "events": store.db.execute("SELECT count(*) FROM paper_events WHERE portfolio_id=?",
                                                  (portfolio_id,)).fetchone()[0]})
    return {"schema": LEDGER_SCHEMA, "manifest": manifest, "portfolios": groups,
            "source_items": store.db.execute("SELECT count(*) FROM source_items WHERE manifest_id=?",
                                             (manifest["id"],)).fetchone()[0],
            "note": "Stored paper evidence only; recommendation metrics and account metrics are separate"}


def format_paper_report(report):
    candidate = report["candidate"]
    stress = report["candidate_2x_cost_stress"]
    final = candidate["final"] or {}
    comparison = report["comparisons"]
    lines = ["# Richping R1 paper portfolio", "",
             f"- Evidence: **{candidate['evidence']}** / {candidate['mode']}",
             f"- Period: {candidate['period']['start']} to {candidate['period']['end']}",
             f"- Initial virtual capital: ${candidate['policy']['initial_capital']:,.2f} (research assumption, not a user budget)",
             f"- Source recommendations: {candidate['source_items']}; virtual fills: {candidate['accepted_fills']}",
             f"- Cash: ${final.get('cash', 0):,.2f}; holdings: {len(final.get('positions', []))}",
             f"- NAV status: **{final.get('nav_status', 'N/A')}**; NAV: {final.get('nav')}",
             f"- Realized / unrealized P&L: {final.get('realized_pnl')} / {final.get('unrealized_pnl')}",
             f"- Account MDD: {candidate['account_metrics']['mdd']}; confirmed-prefix MDD: {candidate['account_metrics']['confirmed_prefix_mdd']}",
             f"- 2x-cost stress NAV / MDD: {stress['final'].get('nav') if stress['final'] else None} / {stress['account_metrics']['mdd']}",
             f"- Unresolved items: {len(final.get('unresolved', []))}", ""]
    if final.get("positions"):
        lines += ["## Holdings", ""]
        for pos in final["positions"]:
            lines.append(f"- {pos['ticker']} {pos['shares']} shares; cost {pos['cost_basis']}; mark {pos['mark_value']}; exit {pos['exit_session']}")
        lines.append("")
    if final.get("unresolved"):
        lines += ["## Unresolved accounting", ""]
        for item in final["unresolved"]:
            lines.append(f"- {item['key']}: {item['reason']}")
        lines.append("")
    lines += ["## SPY comparisons", "",
              f"- Status: **{comparison['status']}**",
              f"- Buy-and-hold NAV: {comparison['SPY_buy_and_hold'].get('nav')}; price-only diagnostic: {comparison['SPY_buy_and_hold'].get('price_only_diagnostic_nav')}",
              f"- Cash-waiting substitute NAV: {comparison['SPY_cash_waiting_substitute']['final'].get('nav') if comparison['SPY_cash_waiting_substitute']['final'] else None}",
              f"- Incomplete reasons: {json.dumps(comparison['reasons'], sort_keys=True)}", "",
              "Recommendation returns and cohort drawdown remain separate from account return/MDD.",
              "Alpha: INSUFFICIENT EVIDENCE. No orders were placed."]
    return "\n".join(lines) + "\n"
