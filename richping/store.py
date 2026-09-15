from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from .core import canonical, utcnow
from .data import Bar, Dataset


SCHEMA = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS datasets(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, metadata TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bars(dataset_id TEXT REFERENCES datasets(id), ticker TEXT, session TEXT,
 body TEXT NOT NULL, PRIMARY KEY(dataset_id,ticker,session));
CREATE TABLE IF NOT EXISTS members(dataset_id TEXT REFERENCES datasets(id), ticker TEXT, body TEXT NOT NULL,
 PRIMARY KEY(dataset_id,ticker));
CREATE TABLE IF NOT EXISTS model_versions(id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, dataset_id TEXT REFERENCES datasets(id),
 model_id TEXT REFERENCES model_versions(id), session TEXT, mode TEXT CHECK(mode IN ('research','shadow')),
 status TEXT CHECK(status IN ('RUNNING','SUCCEEDED','FAILED')), attempts INTEGER NOT NULL,
 error TEXT, body TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recommendations(id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(id),
 ticker TEXT, rank INTEGER, snapshot TEXT NOT NULL, UNIQUE(run_id,ticker), UNIQUE(run_id,rank));
CREATE TABLE IF NOT EXISTS outcomes(recommendation_id TEXT REFERENCES recommendations(id), horizon INTEGER,
 dataset_id TEXT REFERENCES datasets(id), status TEXT NOT NULL, body TEXT NOT NULL,
 PRIMARY KEY(recommendation_id,horizon,dataset_id));
CREATE TABLE IF NOT EXISTS risk_state(model_id TEXT REFERENCES model_versions(id), mode TEXT,
 state TEXT NOT NULL, since_session TEXT NOT NULL, PRIMARY KEY(model_id,mode));
CREATE TABLE IF NOT EXISTS experiments(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
 status TEXT NOT NULL, specification TEXT NOT NULL, result TEXT);
CREATE INDEX IF NOT EXISTS runs_session ON runs(model_id,mode,session);
PRAGMA user_version=1;
COMMIT;
"""


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            raise ValueError("Unsupported database schema")
        self.db.executescript(SCHEMA)
        for table in ("datasets", "bars", "members", "model_versions", "recommendations", "outcomes"):
            for action in ("UPDATE", "DELETE"):
                self.db.execute(f"CREATE TRIGGER IF NOT EXISTS freeze_{table}_{action} BEFORE {action} ON {table} "
                                f"BEGIN SELECT RAISE(ABORT, 'immutable {table}'); END")
        self.db.commit()

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def save_dataset(self, dataset):
        with self.db:
            if self.db.execute("SELECT 1 FROM datasets WHERE id=?", (dataset.id,)).fetchone():
                return dataset.id
            self.db.execute("INSERT INTO datasets VALUES(?,?,?)", (dataset.id, utcnow(), canonical(dataset.metadata)))
            self.db.executemany("INSERT INTO bars VALUES(?,?,?,?)",
                [(dataset.id, b.ticker, b.session, canonical(asdict(b))) for b in dataset.bars])
            self.db.executemany("INSERT INTO members VALUES(?,?,?)",
                [(dataset.id, m["ticker"], canonical(m)) for m in dataset.members])
        return dataset.id

    def load_dataset(self, dataset_id=None):
        if dataset_id is None:
            row = self.db.execute("SELECT id FROM datasets ORDER BY rowid DESC LIMIT 1").fetchone()
            if row is None:
                raise ValueError("No dataset. Run demo, import-csv or sync first.")
            dataset_id = row[0]
        row = self.db.execute("SELECT metadata FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown dataset")
        bars = [Bar(**json.loads(r[0])) for r in self.db.execute("SELECT body FROM bars WHERE dataset_id=?", (dataset_id,))]
        members = [json.loads(r[0]) for r in self.db.execute("SELECT body FROM members WHERE dataset_id=?", (dataset_id,))]
        result = Dataset(bars, json.loads(row[0]), members)
        if result.id != dataset_id:
            raise ValueError("Dataset content hash mismatch")
        return result

    def save_model(self, config):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO model_versions VALUES(?,?)",
                            (config.model_id, canonical(config.payload())))

    def latest_report(self):
        row = self.db.execute("SELECT body FROM runs WHERE status='SUCCEEDED' ORDER BY session DESC, rowid DESC LIMIT 1").fetchone()
        if not row:
            raise ValueError("No successful report")
        return json.loads(row[0])
