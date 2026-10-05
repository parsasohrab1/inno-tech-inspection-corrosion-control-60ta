import sqlite3
from typing import Any, Iterable

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  full_name TEXT, role TEXT NOT NULL,
  password_hash TEXT, is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS equipment(
  equipment_id TEXT PRIMARY KEY, tag TEXT NOT NULL, equipment_type TEXT, material TEXT,
  fluid TEXT, location TEXT, install_date TEXT, design_pressure_bar REAL, design_temp_c REAL,
  nominal_thickness_mm REAL, min_required_thickness_mm REAL, criticality INTEGER, status TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_eq_tag ON equipment(tag);
CREATE TABLE IF NOT EXISTS inspections(
  inspection_id TEXT PRIMARY KEY, equipment_id TEXT NOT NULL, inspection_date TEXT NOT NULL,
  inspection_type TEXT, inspector TEXT, method TEXT, remarks TEXT
);
CREATE INDEX IF NOT EXISTS ix_insp_eq ON inspections(equipment_id, inspection_date);
CREATE TABLE IF NOT EXISTS thickness_measurements(
  thickness_id TEXT PRIMARY KEY, inspection_id TEXT NOT NULL, equipment_id TEXT NOT NULL,
  point_id TEXT, measurement_date TEXT, thickness_mm REAL, nominal_thickness_mm REAL,
  min_required_thickness_mm REAL, corrosion_rate_mm_per_year REAL
);
CREATE INDEX IF NOT EXISTS ix_thk_eq ON thickness_measurements(equipment_id, measurement_date);
CREATE INDEX IF NOT EXISTS ix_thk_insp ON thickness_measurements(inspection_id);
CREATE TABLE IF NOT EXISTS ndt_records(
  ndt_id TEXT PRIMARY KEY, equipment_id TEXT NOT NULL, inspection_id TEXT, method TEXT, date TEXT,
  defect_type TEXT, defect_size_mm REAL, defect_depth_mm REAL, defect_length_mm REAL, result TEXT,
  confidence REAL, inspector TEXT, signal_file TEXT, priority_score REAL DEFAULT 0,
  review_status TEXT NOT NULL DEFAULT 'pending', reviewed_by TEXT, reviewed_at TEXT, review_comment TEXT
);
CREATE INDEX IF NOT EXISTS ix_ndt_eq ON ndt_records(equipment_id);
CREATE INDEX IF NOT EXISTS ix_ndt_review ON ndt_records(review_status, priority_score);
CREATE TABLE IF NOT EXISTS images(
  image_id TEXT PRIMARY KEY, file TEXT, label TEXT, equipment_id TEXT
);
CREATE TABLE IF NOT EXISTS risk_assessments(
  equipment_id TEXT PRIMARY KEY, min_thickness_mm REAL, health_index REAL,
  corrosion_rate_mm_per_year REAL, remaining_life_years REAL, rl_low REAL, rl_high REAL,
  pof_score REAL, cof_score REAL, pof_category INTEGER, cof_category INTEGER,
  risk_score REAL, risk_level TEXT, p_critical_1y REAL, p_critical_3y REAL, p_critical_5y REAL,
  health_status TEXT, trend TEXT, assessed_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_risk_score ON risk_assessments(risk_score DESC);
CREATE TABLE IF NOT EXISTS inspection_plans(
  equipment_id TEXT PRIMARY KEY, recommended_date TEXT, priority TEXT, recommended_method TEXT,
  risk_level TEXT, remaining_life_years REAL, interval_years REAL, standard TEXT, rationale TEXT,
  overdue INTEGER DEFAULT 0, plan_status TEXT NOT NULL DEFAULT 'proposed'
);
CREATE TABLE IF NOT EXISTS alerts(
  alert_id INTEGER PRIMARY KEY AUTOINCREMENT, equipment_id TEXT, severity TEXT, message TEXT,
  created_at TEXT, acknowledged INTEGER NOT NULL DEFAULT 0, acknowledged_by TEXT, kind TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_alert ON alerts(equipment_id, kind) WHERE acknowledged=0;
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, username TEXT, action TEXT NOT NULL,
  entity TEXT, entity_id TEXT, detail TEXT, prev_hash TEXT, hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT,'audit_log is immutable'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT,'audit_log is immutable'); END;
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def init_db() -> None:
    c = connect()
    try:
        c.executescript(SCHEMA)
        c.commit()
    finally:
        c.close()


def get_conn():
    """FastAPI dependency."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def rows(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def one(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> dict | None:
    r = conn.execute(sql, tuple(params)).fetchone()
    return dict(r) if r else None


def scalar(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()):
    r = conn.execute(sql, tuple(params)).fetchone()
    return r[0] if r else None
