"""M1–M3: تحلیل NDT، پیش‌بینی خوردگی، ریسک، برنامه بازرسی، هشدارها و داشبورد."""
from __future__ import annotations

import io
import json
import sqlite3
import time
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel, Field

from .. import config
from ..db import get_conn, one, rows, scalar
from ..security import current_user, require
from ..services import audit, corrosion, engine, ndt, risk

router = APIRouter(prefix="/api", tags=["analytics"])


def _eq(conn, eid):
    e = one(conn, "SELECT * FROM equipment WHERE equipment_id=? AND is_deleted=0", (eid,))
    if not e:
        raise HTTPException(404, "تجهیز یافت نشد")
    return e


# ------------------------------------------------------------------ M1 / NDT
def _parse_signal(name: str, raw: bytes) -> np.ndarray:
    name = (name or "").lower()
    try:
        if name.endswith(".npy"):
            arr = np.load(io.BytesIO(raw), allow_pickle=False)
        elif name.endswith(".json"):
            d = json.loads(raw.decode("utf-8-sig"))
            arr = np.array(d["samples"] if isinstance(d, dict) else d, dtype=float)
        else:
            arr = pd.read_csv(io.BytesIO(raw), header=None, encoding="utf-8-sig").select_dtypes("number").to_numpy()
            if arr.ndim == 2 and arr.shape[1] > 1:
                arr = arr[:, -1]
        return np.asarray(arr, dtype=float).ravel()
    except Exception as ex:
        raise HTTPException(422, f"فایل سیگنال قابل خواندن نیست: {ex}")


@router.post("/ndt/analyze")
async def analyze_ndt(file: UploadFile | None = File(None), ndt_id: str | None = Form(None),
                      equipment_id: str | None = Form(None), method: str = Form("PAUT"),
                      wall_thickness_mm: float = Form(30.0), save: bool = Form(False),
                      conn: sqlite3.Connection = Depends(get_conn), user=Depends(require("inspector", "ndt"))):
    """تحلیل سیگنال PAUT/ToFD: پیش‌پردازش → شناسایی → طبقه‌بندی → اولویت‌بندی (FR-M1-02…05)."""
    t0 = time.time()
    if ndt_id:
        rec = one(conn, "SELECT * FROM ndt_records WHERE ndt_id=?", (ndt_id,))
        if not rec or not rec["signal_file"]:
            raise HTTPException(404, "سیگنالی برای این رکورد موجود نیست")
        samples = np.load(config.DATA_DIR / rec["signal_file"])
        equipment_id = rec["equipment_id"]
    elif file:
        raw = await file.read()
        if len(raw) > 20 * 1024 * 1024:
            raise HTTPException(413, "حجم فایل زیاد است")
        samples = _parse_signal(file.filename or "", raw)
    else:
        raise HTTPException(422, "فایل سیگنال یا ndt_id لازم است")
    try:
        res = ndt.analyze_signal(samples, wall_thickness_mm)
    except ValueError as ex:
        raise HTTPException(422, str(ex))
    res["elapsed_s"] = round(time.time() - t0, 3)
    if save and not ndt_id:
        if not equipment_id:
            raise HTTPException(422, "برای ذخیره، equipment_id لازم است")
        _eq(conn, equipment_id)
        n = (scalar(conn, "SELECT MAX(CAST(SUBSTR(ndt_id,5) AS INTEGER)) FROM ndt_records") or 0) + 1
        nid = f"NDT-{n:07d}"
        np.save(config.SIGNAL_DIR / f"{nid}.npy", np.asarray(samples, dtype=np.float32))
        conn.execute("INSERT INTO ndt_records(ndt_id,equipment_id,inspection_id,method,date,defect_type,defect_size_mm,defect_depth_mm,defect_length_mm,"
                     "result,confidence,inspector,signal_file,priority_score,review_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,'pending')",
                     (nid, equipment_id, None, method, date.today().isoformat(), res["defect_type"], res["defect_size_mm"], res["defect_depth_mm"],
                      res["defect_length_mm"], res["suggested_result"], res["confidence"], user["username"],
                      f"{config.SIGNAL_DIR.name}/{nid}.npy", res["priority_score"]))
        audit.log(conn, user["username"], "ndt_analyze_save", "ndt", nid, {"defect": res["defect_type"], "conf": res["confidence"]})
        res["ndt_id"] = nid
    return res


@router.post("/ndt/analyze-image")
async def analyze_ndt_image(file: UploadFile = File(...), _=Depends(require("inspector", "ndt"))):
    raw = await file.read()
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:
        raise HTTPException(422, "تصویر نامعتبر است")
    return ndt.analyze_image(img)


@router.get("/images/{image_id}")
def image_file(image_id: str, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    r = one(conn, "SELECT file FROM images WHERE image_id=?", (image_id,))
    if not r or not (config.DATA_DIR / r["file"]).exists():
        raise HTTPException(404, "تصویر یافت نشد")
    return FileResponse(config.DATA_DIR / r["file"], media_type="image/png")


@router.get("/ndt/model-card")
def model_card(_=Depends(current_user)):
    return ndt.model_card()


@router.get("/ndt/queue")
def review_queue(limit: int = Query(30, le=200), min_priority: float = 0, equipment_id: str | None = None,
                 conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    """فهرست موارد مشکوک مرتب‌شده بر اساس اولویت برای بررسی کارشناس (FR-M1-05)."""
    sql = ("SELECT n.*, e.tag, e.equipment_type FROM ndt_records n JOIN equipment e USING(equipment_id) "
           "WHERE n.review_status='pending' AND n.defect_type!='None' AND n.priority_score>=?")
    p: list = [min_priority]
    if equipment_id:
        sql += " AND n.equipment_id=?"; p.append(equipment_id)
    items = rows(conn, sql + " ORDER BY n.priority_score DESC, n.confidence DESC LIMIT ?", p + [limit])
    for it in items:
        it["priority_level"] = ndt.priority_level(it["priority_score"])
        it["defect_type_fa"] = ndt.FA.get(it["defect_type"], it["defect_type"])
    return {"total_pending": scalar(conn, "SELECT COUNT(*) FROM ndt_records WHERE review_status='pending' AND defect_type!='None'"), "items": items}


@router.get("/ndt/records")
def ndt_records(equipment_id: str | None = None, defect_type: str | None = None, review_status: str | None = None,
                method: str | None = None, page: int = 1, page_size: int = Query(25, le=200),
                conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    where, p = ["1=1"], []
    for col, v in (("n.equipment_id", equipment_id), ("n.defect_type", defect_type), ("n.review_status", review_status), ("n.method", method)):
        if v:
            where.append(f"{col}=?"); p.append(v)
    w = " AND ".join(where)
    total = scalar(conn, f"SELECT COUNT(*) FROM ndt_records n WHERE {w}", p)
    items = rows(conn, f"SELECT n.*, e.tag FROM ndt_records n JOIN equipment e USING(equipment_id) WHERE {w} "
                       "ORDER BY n.date DESC, n.priority_score DESC LIMIT ? OFFSET ?", p + [page_size, (max(page, 1) - 1) * page_size])
    return {"total": total, "items": items}


@router.get("/ndt/{ndt_id}")
def ndt_detail(ndt_id: str, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    r = one(conn, "SELECT n.*, e.tag FROM ndt_records n JOIN equipment e USING(equipment_id) WHERE ndt_id=?", (ndt_id,))
    if not r:
        raise HTTPException(404, "رکورد NDT یافت نشد")
    if r["signal_file"] and (config.DATA_DIR / r["signal_file"]).exists():
        r["analysis"] = ndt.analyze_signal(np.load(config.DATA_DIR / r["signal_file"]))
    return r


class Review(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    defect_type: str | None = None
    result: str | None = Field(None, pattern="^(Accept|Monitor|Reject)$")
    comment: str = ""


@router.post("/ndt/{ndt_id}/review")
def review_ndt(ndt_id: str, body: Review, conn: sqlite3.Connection = Depends(get_conn), user=Depends(require("ndt", "inspector"))):
    """Human-in-the-Loop: تأیید/رد خروجی هوش مصنوعی توسط کارشناس (FR-M1-06)."""
    r = one(conn, "SELECT * FROM ndt_records WHERE ndt_id=?", (ndt_id,))
    if not r:
        raise HTTPException(404, "رکورد NDT یافت نشد")
    if body.defect_type and body.defect_type not in ndt.ALL_CLASSES:
        raise HTTPException(422, "نوع عیب نامعتبر است")
    status = "approved" if body.decision == "approve" else "rejected"
    conn.execute("UPDATE ndt_records SET review_status=?, reviewed_by=?, reviewed_at=?, review_comment=?, defect_type=COALESCE(?,defect_type), "
                 "result=COALESCE(?,result) WHERE ndt_id=?",
                 (status, user["username"], datetime.now(timezone.utc).isoformat(timespec="seconds"), body.comment, body.defect_type, body.result, ndt_id))
    audit.log(conn, user["username"], f"ndt_{body.decision}", "ndt", ndt_id,
              {"before": {"defect_type": r["defect_type"], "result": r["result"]}, "after": {"defect_type": body.defect_type, "result": body.result}, "comment": body.comment})
    engine.recompute(conn, [r["equipment_id"]])
    return {"ok": True, "review_status": status}


# ----------------------------------------------------------------- M2
_metrics_cache: dict = {}


@router.get("/predictions/metrics")
def prediction_metrics(refresh: bool = False, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    """بک‌تست: خطای MAE پیش‌بینی ضخامت نسبت به آخرین اندازه‌گیری واقعی."""
    if refresh or "m" not in _metrics_cache:
        eqs = {r["equipment_id"]: r for r in rows(conn, "SELECT * FROM equipment WHERE is_deleted=0")}
        h = engine.load_histories(conn)
        H = {k: {"history": v, "nominal": eqs[k]["nominal_thickness_mm"], "t_min": eqs[k]["min_required_thickness_mm"],
                 "install": eqs[k]["install_date"]} for k, v in h.items() if k in eqs}
        _metrics_cache["m"] = corrosion.backtest(H, limit=1000)
    return _metrics_cache["m"]


@router.get("/predictions/corrosion/{eid}")
def predict_corrosion(eid: str, horizon_years: int = Query(5, ge=1, le=15), rate_multiplier: float = Query(1.0, gt=0, le=5),
                      conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    e = _eq(conn, eid)
    hist = engine.load_histories(conn, [eid]).get(eid, [])
    nd = engine.load_ndt_summary(conn, [eid]).get(eid, {})
    pen = min(0.25, 0.08 * nd.get("reject", 0) + 0.03 * nd.get("monitor", 0))
    r = corrosion.analyze(hist, e["nominal_thickness_mm"], e["min_required_thickness_mm"], e["install_date"],
                          rate_multiplier=rate_multiplier, defect_penalty=pen, horizon_years=horizon_years)
    if not r.get("ok"):
        raise HTTPException(422, "داده ضخامت‌سنجی برای این تجهیز موجود نیست")
    r["history"] = [{"date": d, "min_mm": m} for d, m in hist]
    r["equipment_id"], r["tag"] = eid, e["tag"]
    r["requires_expert_review"] = True
    return r


# ----------------------------------------------------------------- M3
@router.get("/risk/ranking")
def risk_ranking(limit: int = Query(50, le=1000), level: str | None = None, type: str | None = None,
                 status: str | None = None, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    sql = ("SELECT r.*, e.tag, e.equipment_type, e.fluid, e.location, e.status, e.criticality FROM risk_assessments r "
           "JOIN equipment e USING(equipment_id) WHERE e.is_deleted=0")
    p: list = []
    for col, v in (("r.risk_level", level), ("e.equipment_type", type), ("e.status", status)):
        if v:
            sql += f" AND {col}=?"; p.append(v)
    items = rows(conn, sql + " ORDER BY r.risk_score DESC LIMIT ?", p + [limit])
    for i, it in enumerate(items, 1):
        it["rank"] = i
    return {"items": items}


@router.get("/risk/heatmap")
def risk_heatmap(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    rs = rows(conn, "SELECT r.equipment_id, e.tag, r.risk_score, r.pof_category, r.cof_category FROM risk_assessments r "
                    "JOIN equipment e USING(equipment_id) WHERE e.is_deleted=0 AND e.status!='Out of Service'")
    return risk.heatmap(rs)


class Scenario(BaseModel):
    name: str = "سناریو"
    rate_multiplier: float = Field(1.0, gt=0, le=5)
    temp_delta: float = 0
    pressure_delta: float = 0
    fluid: str | None = None
    inspection_delay_months: float = Field(0, ge=0, le=60)


class WhatIf(BaseModel):
    equipment_id: str
    scenarios: list[Scenario] = Field(min_length=1, max_length=6)


@router.post("/risk/what-if")
def what_if(body: WhatIf, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    """تحلیل What-If (FR-M3-04): مقایسه ریسک پایه با سناریوهای عملیاتی."""
    e = _eq(conn, body.equipment_id)
    hist = engine.load_histories(conn, [e["equipment_id"]]).get(e["equipment_id"], [])
    nd = engine.load_ndt_summary(conn, [e["equipment_id"]]).get(e["equipment_id"], {})
    li = engine.last_inspections(conn).get(e["equipment_id"])
    out = []
    for name, ov in [("پایه", {})] + [(s.name, s.model_dump(exclude={"name"})) for s in body.scenarios]:
        a = risk.assess(e, hist, nd, overrides=ov, last_inspection=li)
        if not a:
            raise HTTPException(422, "داده ضخامت‌سنجی موجود نیست")
        out.append({"name": name, "overrides": ov, **{k: a[k] for k in ("risk_score", "risk_level", "remaining_life_years", "rl_low", "rl_high",
                    "health_index", "corrosion_rate_mm_per_year", "p_critical_5y", "pof_category", "cof_category")}, "plan": a["plan"]})
    for s in out[1:]:
        s["delta_risk"] = round(s["risk_score"] - out[0]["risk_score"], 2)
        s["delta_life_years"] = round(s["remaining_life_years"] - out[0]["remaining_life_years"], 2)
    return {"equipment_id": e["equipment_id"], "tag": e["tag"], "results": out}


@router.post("/risk/recompute")
def recompute(equipment_id: str | None = None, conn: sqlite3.Connection = Depends(get_conn),
              user=Depends(require("corrosion", "rbi", "manager"))):
    res = engine.recompute(conn, [equipment_id] if equipment_id else None)
    _metrics_cache.clear()
    audit.log(conn, user["username"], "recompute", "risk", equipment_id or "ALL", res)
    return res


@router.get("/plans")
def plans(priority: str | None = None, overdue: bool | None = None, plan_status: str | None = None, method: str | None = None,
          within_days: int | None = None, page: int = 1, page_size: int = Query(25, le=500),
          conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    where, p = ["1=1"], []
    for col, v in (("p.priority", priority), ("p.plan_status", plan_status), ("p.recommended_method", method)):
        if v:
            where.append(f"{col}=?"); p.append(v)
    if overdue is not None:
        where.append("p.overdue=?"); p.append(int(overdue))
    if within_days is not None:
        where.append("p.recommended_date<=date('now', ?)"); p.append(f"+{int(within_days)} days")
    w = " AND ".join(where)
    total = scalar(conn, f"SELECT COUNT(*) FROM inspection_plans p WHERE {w}", p)
    items = rows(conn, f"SELECT p.*, e.tag, e.equipment_type, e.location, r.risk_score FROM inspection_plans p JOIN equipment e USING(equipment_id) "
                       f"LEFT JOIN risk_assessments r USING(equipment_id) WHERE {w} ORDER BY p.priority, p.recommended_date LIMIT ? OFFSET ?",
                 p + [page_size, (max(page, 1) - 1) * page_size])
    return {"total": total, "items": items,
            "by_priority": rows(conn, "SELECT priority, COUNT(*) n, SUM(overdue) overdue FROM inspection_plans GROUP BY priority ORDER BY priority"),
            "active_equipment": scalar(conn, "SELECT COUNT(*) FROM equipment WHERE is_deleted=0 AND status IN ('Active','Standby')"),
            "plans_total": scalar(conn, "SELECT COUNT(*) FROM inspection_plans")}


class PlanPatch(BaseModel):
    plan_status: str | None = Field(None, pattern="^(proposed|scheduled|done)$")
    recommended_date: date | None = None


@router.patch("/plans/{eid}")
def patch_plan(eid: str, body: PlanPatch, conn: sqlite3.Connection = Depends(get_conn), user=Depends(require("rbi", "manager"))):
    if not one(conn, "SELECT 1 x FROM inspection_plans WHERE equipment_id=?", (eid,)):
        raise HTTPException(404, "برنامه‌ای برای این تجهیز نیست")
    if body.plan_status:
        conn.execute("UPDATE inspection_plans SET plan_status=? WHERE equipment_id=?", (body.plan_status, eid))
    if body.recommended_date:
        conn.execute("UPDATE inspection_plans SET recommended_date=?, overdue=? WHERE equipment_id=?",
                     (body.recommended_date.isoformat(), int(body.recommended_date < date.today()), eid))
    audit.log(conn, user["username"], "plan_update", "plan", eid, body.model_dump(mode="json", exclude_none=True))
    return {"ok": True}


# ----------------------------------------------------------- alerts / dashboard
@router.get("/alerts")
def alerts(include_ack: bool = False, limit: int = 50, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    w = "" if include_ack else "WHERE a.acknowledged=0"
    return rows(conn, f"SELECT a.*, e.tag FROM alerts a JOIN equipment e USING(equipment_id) {w} "
                      "ORDER BY CASE severity WHEN 'critical' THEN 0 ELSE 1 END, created_at DESC LIMIT ?", (limit,))


@router.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: int, conn: sqlite3.Connection = Depends(get_conn), user=Depends(require("corrosion", "rbi", "manager", "hse", "inspector"))):
    conn.execute("UPDATE alerts SET acknowledged=1, acknowledged_by=? WHERE alert_id=?", (user["username"], alert_id))
    audit.log(conn, user["username"], "alert_ack", "alert", str(alert_id))
    return {"ok": True}


@router.get("/dashboard")
def dashboard(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    kpi = one(conn, "SELECT COUNT(*) total, SUM(status='Active') active, SUM(status='Standby') standby, SUM(status='Out of Service') oos "
                    "FROM equipment WHERE is_deleted=0")
    avg = one(conn, "SELECT ROUND(AVG(health_index),3) avg_health, ROUND(AVG(corrosion_rate_mm_per_year),3) avg_rate, "
                    "SUM(remaining_life_years<5) life_lt5, SUM(remaining_life_years<2) life_lt2 FROM risk_assessments")
    return {
        "kpi": {**kpi, **avg, "pending_review": scalar(conn, "SELECT COUNT(*) FROM ndt_records WHERE review_status='pending' AND defect_type!='None'"),
                "overdue_plans": scalar(conn, "SELECT COUNT(*) FROM inspection_plans WHERE overdue=1"),
                "open_alerts": scalar(conn, "SELECT COUNT(*) FROM alerts WHERE acknowledged=0"),
                "inspections_last_year": scalar(conn, "SELECT COUNT(*) FROM inspections WHERE inspection_date>=date('now','-1 year')")},
        "risk_levels": rows(conn, "SELECT risk_level level, COUNT(*) n FROM risk_assessments GROUP BY 1"),
        "health": rows(conn, "SELECT health_status status, COUNT(*) n FROM risk_assessments GROUP BY 1"),
        "defects": rows(conn, "SELECT defect_type, COUNT(*) n FROM ndt_records WHERE defect_type!='None' AND review_status!='rejected' GROUP BY 1 ORDER BY n DESC"),
        "risk_by_type": rows(conn, "SELECT e.equipment_type type, ROUND(AVG(r.risk_score),1) avg_risk, COUNT(*) n FROM risk_assessments r JOIN equipment e USING(equipment_id) "
                                   "WHERE e.is_deleted=0 GROUP BY 1 ORDER BY avg_risk DESC"),
        "plans_by_month": rows(conn, "SELECT substr(recommended_date,1,7) month, COUNT(*) n, SUM(priority='P1') p1 FROM inspection_plans "
                                     "WHERE recommended_date<=date('now','+12 months') GROUP BY 1 ORDER BY 1"),
        "top_risk": rows(conn, "SELECT r.equipment_id, e.tag, e.equipment_type, r.risk_score, r.risk_level, r.remaining_life_years, r.health_index "
                               "FROM risk_assessments r JOIN equipment e USING(equipment_id) WHERE e.is_deleted=0 ORDER BY r.risk_score DESC LIMIT 10"),
        "alerts": rows(conn, "SELECT a.alert_id,a.equipment_id,a.severity,a.message,a.created_at,e.tag FROM alerts a JOIN equipment e USING(equipment_id) "
                             "WHERE a.acknowledged=0 ORDER BY CASE severity WHEN 'critical' THEN 0 ELSE 1 END, a.created_at DESC LIMIT 8"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
