"""A separate SQLite evidence file. Reject foreign databases before any DDL."""

from pathlib import Path
from contextlib import closing
import json
import sqlite3

from ..core import canonical, digest, timestamp
from .contracts import AVAILABILITY_VERSION, Checkpoint, StrategyState, payload
from .market_data import MarketDataset

SCHEMA_VERSION = 1
APPLICATION_ID = 0x52505632
TABLES = ("v2_metadata", "v2_datasets", "v2_bars", "v2_replay_runs",
          "v2_traces", "v2_checkpoints", "v2_results")
SCHEMA = """
CREATE TABLE v2_metadata(id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE v2_datasets(id TEXT PRIMARY KEY, content_hash TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE v2_bars(dataset_id TEXT NOT NULL REFERENCES v2_datasets(id),
 symbol TEXT NOT NULL, timeframe TEXT NOT NULL, end_at TEXT NOT NULL,
 sequence INTEGER NOT NULL, body TEXT NOT NULL,
 PRIMARY KEY(dataset_id,symbol,timeframe,end_at), UNIQUE(dataset_id,sequence));
CREATE TABLE v2_replay_runs(id TEXT PRIMARY KEY,
 dataset_id TEXT NOT NULL REFERENCES v2_datasets(id), body TEXT NOT NULL);
CREATE TABLE v2_traces(run_id TEXT NOT NULL REFERENCES v2_replay_runs(id),
 sequence INTEGER NOT NULL, event_id TEXT NOT NULL UNIQUE,
 trace_hash TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(run_id,sequence));
CREATE TABLE v2_checkpoints(run_id TEXT NOT NULL, sequence INTEGER NOT NULL,
 body TEXT NOT NULL, PRIMARY KEY(run_id,sequence),
 FOREIGN KEY(run_id,sequence) REFERENCES v2_traces(run_id,sequence));
CREATE TABLE v2_results(run_id TEXT PRIMARY KEY REFERENCES v2_replay_runs(id), body TEXT NOT NULL);
"""


class ResearchStore:
    def __init__(self, path):
        self.path = Path(path)
        # Read-only preflight prevents even journal/schema changes to a foreign DB.
        if self.path.exists():
            with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as probe:
                self._check_schema(probe, allow_empty=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        try:
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("PRAGMA recursive_triggers=ON")
            self.db.execute("BEGIN IMMEDIATE")
            empty = self._check_schema(self.db, allow_empty=True)
            if empty:
                for statement in SCHEMA.split(";"):
                    if statement.strip():
                        self.db.execute(statement)
                self.db.execute(f"PRAGMA application_id={APPLICATION_ID}")
                self.db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                self.db.execute("INSERT INTO v2_metadata VALUES(?,?)",
                                ("schema", canonical({"version": SCHEMA_VERSION,
                                                       "schema_hash": digest(SCHEMA)})))
                for table in TABLES:
                    for action in ("UPDATE", "DELETE"):
                        self.db.execute(f"CREATE TRIGGER freeze_{table}_{action} BEFORE {action} ON {table} "
                                        f"BEGIN SELECT RAISE(ABORT, 'immutable {table}'); END")
                    # Also block REPLACE's implicit deletion on external connections,
                    # where recursive_triggers may be disabled. Idempotency is handled
                    # by comparing existing rows before issuing INSERT.
                    keys = self._keys(table)
                    match = " AND ".join(f"{k}=NEW.{k}" for k in keys)
                    if table == "v2_bars":
                        match = f"({match}) OR (dataset_id=NEW.dataset_id AND sequence=NEW.sequence)"
                    elif table == "v2_traces":
                        match = f"({match}) OR event_id=NEW.event_id"
                    self.db.execute(f"CREATE TRIGGER freeze_{table}_INSERT BEFORE INSERT ON {table} "
                        f"WHEN EXISTS(SELECT 1 FROM {table} WHERE {match}) "
                        f"BEGIN SELECT RAISE(ABORT, 'immutable identity {table}'); END")
            self.db.commit()
        except Exception:
            self.db.rollback()
            self.db.close()
            raise

    @staticmethod
    def _keys(table):
        if table == "v2_bars":
            return ("dataset_id", "symbol", "timeframe", "end_at")
        if table in {"v2_traces", "v2_checkpoints"}:
            return ("run_id", "sequence")
        return ("run_id",) if table == "v2_results" else ("id",)

    @staticmethod
    def _check_schema(db, allow_empty=False):
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version = db.execute("PRAGMA user_version").fetchone()[0]
        app = db.execute("PRAGMA application_id").fetchone()[0]
        if not tables and version == 0 and app == 0 and allow_empty:
            return True
        if tables != set(TABLES) or version != SCHEMA_VERSION or app != APPLICATION_ID:
            raise ValueError("Foreign/legacy database or unsupported v2 schema")
        row = db.execute("SELECT body FROM v2_metadata WHERE id='schema'").fetchone()
        if row is None or row[0] != canonical({"version": SCHEMA_VERSION, "schema_hash": digest(SCHEMA)}):
            raise ValueError("V2 schema provenance mismatch")
        triggers = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        if not {f"freeze_{t}_{a}" for t in TABLES for a in ("INSERT", "UPDATE", "DELETE")} <= triggers:
            raise ValueError("Missing v2 immutability guards")
        return False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.db.close()

    def _insert(self, table, columns, values):
        keys = self._keys(table)
        where = " AND ".join(f"{key}=?" for key in keys)
        key_values = tuple(values[columns.index(k)] for k in keys)
        existing = self.db.execute(f"SELECT {','.join(columns)} FROM {table} WHERE {where}", key_values).fetchone()
        if existing is not None:
            if tuple(existing) != tuple(values):
                raise ValueError(f"Content/identity collision: {table}")
            return
        try:
            self.db.execute(f"INSERT INTO {table}({','.join(columns)}) VALUES({','.join('?' for _ in values)})", values)
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Content/identity or reference collision: {table}") from exc

    def save_dataset(self, dataset):
        with self.db:
            self._insert("v2_datasets", ("id", "content_hash", "body"),
                (dataset.dataset_id, dataset.content_hash,
                 canonical({"manifest": payload(dataset.manifest), "gaps": payload(dataset.gaps),
                            "bar_count": len(dataset.bars)})))
            for i, bar in enumerate(dataset.bars):
                self._insert("v2_bars", ("dataset_id", "symbol", "timeframe", "end_at", "sequence", "body"),
                             (*bar.identity, i, canonical(payload(bar))))
        return dataset.dataset_id

    def load_dataset(self, dataset_id):
        row = self.db.execute("SELECT content_hash,body FROM v2_datasets WHERE id=?", (dataset_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown dataset")
        records = [json.loads(r[0]) for r in self.db.execute(
            "SELECT body FROM v2_bars WHERE dataset_id=? ORDER BY sequence", (dataset_id,))]
        result = MarketDataset.from_records(dataset_id, records, json.loads(row[1])["manifest"])
        if result.content_hash != row[0]:
            raise ValueError("Dataset content hash mismatch")
        return result

    def begin_run(self, specification):
        run_id = digest(specification)
        with self.db:
            self._insert("v2_replay_runs", ("id", "dataset_id", "body"),
                         (run_id, specification["dataset_id"], canonical(specification)))
        return run_id

    def save_step(self, trace, checkpoint):
        event = trace.event
        expected = Checkpoint(event.run_id, event.sequence, event.as_of, trace.decision.state,
                              trace.hash, trace.visible_hash)
        if checkpoint != expected:
            raise ValueError("Checkpoint/trace mismatch")
        with self.db:
            if self.db.execute("SELECT 1 FROM v2_results WHERE run_id=?", (event.run_id,)).fetchone():
                if not self.db.execute("SELECT 1 FROM v2_traces WHERE run_id=? AND sequence=?",
                                       (event.run_id, event.sequence)).fetchone():
                    raise ValueError("Cannot extend a finalized replay run")
            run = self.db.execute("SELECT body FROM v2_replay_runs WHERE id=?", (event.run_id,)).fetchone()
            if run is None:
                raise ValueError("Unknown replay run")
            spec = json.loads(run[0])
            if trace.strategy_id != spec["strategy_id"] or trace.specification_hash != spec["specification_hash"]:
                raise ValueError("Trace strategy provenance mismatch")
            if spec.get("availability_contract") != AVAILABILITY_VERSION:
                raise ValueError("Trace availability contract mismatch")
            if any(b.dataset_id != spec["dataset_id"] for b in event.completed):
                raise ValueError("Trace dataset provenance mismatch")
            previous = self.db.execute("SELECT trace_hash,body FROM v2_traces WHERE run_id=? AND sequence=?",
                                       (event.run_id, event.sequence - 1)).fetchone()
            if event.sequence < 0 or (event.sequence == 0 and trace.previous_hash is not None):
                raise ValueError("Invalid trace origin")
            if event.sequence > 0 and (previous is None or previous[0] != trace.previous_hash
                    or json.loads(previous[1])["decision"]["state"] != payload(trace.state_before)):
                raise ValueError("Broken trace/state chain")
            self._insert("v2_traces", ("run_id", "sequence", "event_id", "trace_hash", "body"),
                         (event.run_id, event.sequence, event.id, trace.hash,
                          canonical({**payload(trace), "intent_records": trace.intent_records})))
            self._insert("v2_checkpoints", ("run_id", "sequence", "body"),
                         (event.run_id, event.sequence, canonical(payload(checkpoint))))

    def finish_run(self, run_id, result):
        with self.db:
            self._insert("v2_results", ("run_id", "body"), (run_id, canonical(result)))

    def load_checkpoint(self, run_id, sequence):
        row = self.db.execute("SELECT body FROM v2_checkpoints WHERE run_id=? AND sequence=?",
                              (run_id, sequence)).fetchone()
        if row is None:
            raise ValueError("Unknown checkpoint")
        value = json.loads(row[0])
        return Checkpoint(value["run_id"], value["sequence"], timestamp(value["as_of"]),
                          StrategyState.loads(canonical(value["state"])), value["trace_hash"], value["visible_hash"])
