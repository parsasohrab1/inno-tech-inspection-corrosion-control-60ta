"""موتور محاسبه: بارگذاری تاریخچه از DB، ارزیابی ریسک/برنامه، و تولید هشدار."""
from __future__ import annotations

import smtplib
import sqlite3
from datetime import date, datetime, timezone
from email.message import EmailMessage

from .. import config
from ..db import rows
from . import risk


def load_histories(conn: sqlite3.Connection, ids: list[str] | None = None) -> dict[str, list[tuple]]:
    sql = ("SELECT equipment_id, measurement_date d, MIN(thickness_mm) m FROM thickness_measurements "
           "{w} GROUP BY equipment_id, inspection_id ORDER BY equipment_id, d")
    if ids:
        ph = ",".join("?" * len(ids))
        cur = conn.execute(sql.format(w=f"WHERE equipment_id IN ({ph})"), ids)
    else:
        cur = conn.execute(sql.format(w=""))
    out: dict[str, list[tuple]] = {}
    for r in cur:
        out.setdefault(r[0], []).append((r[1], r[2]))
    return out


def load_ndt_summary(conn: sqlite3.Connection, ids: list[str] | None = None) -> dict[str, dict]:
    sql = ("SELECT equipment_id, defect_type, result, review_status FROM ndt_records "
           "WHERE defect_type!='None' AND review_status!='rejected' AND date>=date('now','-5 years') {w}")
    if ids:
        ph = ",".join("?" * len(ids))
        cur = conn.execute(sql.format(w=f"AND equipment_id IN ({ph})"), ids)
    else:
        cur = conn.execute(sql.format(w=""))
    out: dict[str, dict] = {}
    for eid, dt, res, _st in cur:
        s = out.setdefault(eid, {"reject": 0, "monitor": 0, "types": set()})
        s["reject"] += res == "Reject"
        s["monitor"] += res == "Monitor"
        s["types"].add(dt)
    return out


def last_inspections(conn: sqlite3.Connection) -> dict[str, str]:
    return {r[0]: r[1] for r in conn.execute("SELECT equipment_id, MAX(inspection_date) FROM inspections GROUP BY equipment_id")}


def recompute(conn: sqlite3.Connection, ids: list[str] | None = None, alerts: bool = True) -> dict:
    sql = "SELECT * FROM equipment WHERE is_deleted=0"
    params: list = []
    if ids:
        sql += " AND equipment_id IN (%s)" % ",".join("?" * len(ids))
        params = ids
    eqs = rows(conn, sql, params)
    hist = load_histories(conn, ids)
    nd = load_ndt_summary(conn, ids)
    li = last_inspections(conn)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n_ok = n_plans = 0
    for eq in eqs:
        eid = eq["equipment_id"]
        a = risk.assess(eq, hist.get(eid, []), nd.get(eid, {}), last_inspection=li.get(eid))
        if not a:
            continue
        p = a.pop("plan")
        conn.execute(
            "INSERT OR REPLACE INTO risk_assessments(equipment_id,min_thickness_mm,health_index,corrosion_rate_mm_per_year,"
            "remaining_life_years,rl_low,rl_high,pof_score,cof_score,pof_category,cof_category,risk_score,risk_level,"
            "p_critical_1y,p_critical_3y,p_critical_5y,health_status,trend,assessed_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, a["min_thickness_mm"], a["health_index"], a["corrosion_rate_mm_per_year"], a["remaining_life_years"],
             a["rl_low"], a["rl_high"], a["pof_score"], a["cof_score"], a["pof_category"], a["cof_category"],
             a["risk_score"], a["risk_level"], a["p_critical_1y"], a["p_critical_3y"], a["p_critical_5y"],
             a["health_status"], a["trend"], now))
        n_ok += 1
        if eq["status"] in ("Active", "Standby"):
            old = conn.execute("SELECT plan_status FROM inspection_plans WHERE equipment_id=?", (eid,)).fetchone()
            status = old[0] if old and old[0] in ("scheduled", "done") else "proposed"
            conn.execute(
                "INSERT OR REPLACE INTO inspection_plans(equipment_id,recommended_date,priority,recommended_method,risk_level,"
                "remaining_life_years,interval_years,standard,rationale,overdue,plan_status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (eid, p["recommended_date"], p["priority"], p["recommended_method"], p["risk_level"],
                 p["remaining_life_years"], p["interval_years"], p["standard"], p["rationale"], p["overdue"], status))
            n_plans += 1
        else:
            conn.execute("DELETE FROM inspection_plans WHERE equipment_id=?", (eid,))
        if alerts and eq["status"] != "Out of Service":
            _alerts(conn, eq, a, now)
    conn.commit()
    return {"assessed": n_ok, "plans": n_plans}


def _alerts(conn, eq, a, now):
    eid, tag = eq["equipment_id"], eq["tag"]
    sev = msg = None
    if a["p_critical_5y"] >= 0.5 or a["remaining_life_years"] < 2:
        sev, msg = "critical", (f"{tag}: احتمال بحرانی شدن تا ۵ سال {a['p_critical_5y']*100:.0f}٪، "
                                f"عمر باقیمانده {a['remaining_life_years']:.1f} سال، شاخص سلامت {a['health_index']:.2f}")
    elif a["remaining_life_years"] < 5 or a["p_critical_3y"] >= 0.3 or a["health_index"] < 0.2:
        sev, msg = "high", f"{tag}: عمر باقیمانده {a['remaining_life_years']:.1f} سال؛ احتمال بحرانی ۳ ساله {a['p_critical_3y']*100:.0f}٪"
    if sev:
        cur = conn.execute("SELECT alert_id,severity FROM alerts WHERE equipment_id=? AND kind='corrosion' AND acknowledged=0", (eid,)).fetchone()
        if cur:
            conn.execute("UPDATE alerts SET severity=?, message=?, created_at=? WHERE alert_id=?", (sev, msg, now, cur[0]))
        else:
            conn.execute("INSERT INTO alerts(equipment_id,severity,message,created_at,kind) VALUES(?,?,?,?,'corrosion')", (eid, sev, msg, now))
            if sev == "critical":
                send_email(f"[هشدار بحرانی] {tag}", msg)
    else:
        conn.execute("DELETE FROM alerts WHERE equipment_id=? AND kind='corrosion' AND acknowledged=0", (eid,))


def send_email(subject: str, body: str, to: str | None = None) -> bool:
    """ارسال ایمیل هشدار در صورت پیکربندی SMTP (در غیر این صورت فقط داشبورد)."""
    if not config.SMTP_HOST or not (to or config.SMTP_USER):
        return False
    try:
        m = EmailMessage()
        m["Subject"], m["From"], m["To"] = subject, config.SMTP_FROM, to or config.SMTP_USER
        m.set_content(body)
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as s:
            s.starttls()
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(m)
        return True
    except Exception:
        return False


def today() -> date:
    return date.today()
