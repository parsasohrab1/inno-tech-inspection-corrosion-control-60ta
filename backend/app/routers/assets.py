"""M4 — تجهیزات، پرونده دیجیتال، بازرسی‌ها، جستجوی یکپارچه و ورود داده (M1-FR-01)."""
from __future__ import annotations

import io
import json
import sqlite3
from datetime import date, datetime

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from ..db import get_conn, one, rows, scalar
from ..security import current_user, require
from ..services import audit, engine

router = APIRouter(prefix="/api", tags=["assets"])

EQ_COLS = ["tag", "equipment_type", "material", "fluid", "location", "install_date", "design_pressure_bar",
           "design_temp_c", "nominal_thickness_mm", "min_required_thickness_mm", "criticality", "status"]
SORTS = {"tag": "e.tag", "risk": "r.risk_score DESC", "life": "r.remaining_life_years ASC",
         "health": "r.health_index ASC", "id": "e.equipment_id"}


class EquipmentIn(BaseModel):
    tag: str = Field(min_length=2)
    equipment_type: str
    material: str
    fluid: str
    location: str = ""
    install_date: date
    design_pressure_bar: float = Field(ge=0)
    design_temp_c: float
    nominal_thickness_mm: float = Field(gt=0)
    min_required_thickness_mm: float = Field(gt=0)
    criticality: int = Field(ge=1, le=5)
    status: str = "Active"


class ThicknessIn(BaseModel):
    point_id: str
    thickness_mm: float = Field(gt=0, lt=500)


class InspectionIn(BaseModel):
    equipment_id: str
    inspection_date: date
    inspection_type: str = "Periodic"
    method: str = "UT"
    remarks: str = ""
    thickness: list[ThicknessIn] = []


def _eq_or_404(conn, eid):
    e = one(conn, "SELECT * FROM equipment WHERE equipment_id=? AND is_deleted=0", (eid,))
    if not e:
        raise HTTPException(404, "تجهیز یافت نشد")
    return e


@router.get("/equipment")
def list_equipment(q: str | None = None, type: str | None = None, status: str | None = None,
                   risk_level: str | None = None, location: str | None = None, sort: str = "id",
                   page: int = 1, page_size: int = Query(25, le=200),
                   conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    where, p = ["e.is_deleted=0"], []
    if q:
        where.append("(e.tag LIKE ? OR e.equipment_id LIKE ? OR e.fluid LIKE ? OR e.material LIKE ? OR e.location LIKE ?)")
        p += [f"%{q}%"] * 5
    for col, v in (("e.equipment_type", type), ("e.status", status), ("r.risk_level", risk_level), ("e.location", location)):
        if v:
            where.append(f"{col}=?"); p.append(v)
    w = " AND ".join(where)
    base = f"FROM equipment e LEFT JOIN risk_assessments r ON r.equipment_id=e.equipment_id WHERE {w}"
    total = scalar(conn, f"SELECT COUNT(*) {base}", p)
    items = rows(conn, f"SELECT e.*, r.risk_score, r.risk_level, r.health_index, r.health_status, r.remaining_life_years, "
                       f"r.corrosion_rate_mm_per_year {base} ORDER BY {SORTS.get(sort, 'e.equipment_id')} LIMIT ? OFFSET ?",
                 p + [page_size, (max(page, 1) - 1) * page_size])
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/equipment/facets")
def facets(conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    return {k: [r[0] for r in conn.execute(f"SELECT DISTINCT {k} FROM equipment WHERE is_deleted=0 ORDER BY 1")]
            for k in ("equipment_type", "material", "fluid", "location", "status")}


@router.post("/equipment", status_code=201)
def create_equipment(body: EquipmentIn, conn: sqlite3.Connection = Depends(get_conn),
                     user=Depends(require("manager", "asset"))):
    if body.min_required_thickness_mm >= body.nominal_thickness_mm:
        raise HTTPException(422, "ضخامت حداقل مجاز باید کمتر از ضخامت اسمی باشد")
    n = (scalar(conn, "SELECT MAX(CAST(SUBSTR(equipment_id,4) AS INTEGER)) FROM equipment") or 0) + 1
    eid = f"EQ-{n:06d}"
    d = body.model_dump()
    d["install_date"] = body.install_date.isoformat()
    conn.execute(f"INSERT INTO equipment(equipment_id,{','.join(EQ_COLS)}) VALUES(?,{','.join('?' * len(EQ_COLS))})",
                 [eid] + [d[c] for c in EQ_COLS])
    audit.log(conn, user["username"], "create", "equipment", eid, d)
    return {"equipment_id": eid}


@router.put("/equipment/{eid}")
def update_equipment(eid: str, body: EquipmentIn, conn: sqlite3.Connection = Depends(get_conn),
                     user=Depends(require("manager", "asset"))):
    old = _eq_or_404(conn, eid)
    d = body.model_dump()
    d["install_date"] = body.install_date.isoformat()
    conn.execute(f"UPDATE equipment SET {','.join(c + '=?' for c in EQ_COLS)}, version=version+1 WHERE equipment_id=?",
                 [d[c] for c in EQ_COLS] + [eid])
    audit.log(conn, user["username"], "update", "equipment", eid, {"before": {c: old[c] for c in EQ_COLS}, "after": d})
    engine.recompute(conn, [eid])
    return {"ok": True}


@router.delete("/equipment/{eid}")
def delete_equipment(eid: str, conn: sqlite3.Connection = Depends(get_conn), user=Depends(require("manager"))):
    """حذف نرم — رکورد هرگز به‌صورت فیزیکی پاک نمی‌شود."""
    _eq_or_404(conn, eid)
    conn.execute("UPDATE equipment SET is_deleted=1 WHERE equipment_id=?", (eid,))
    audit.log(conn, user["username"], "soft_delete", "equipment", eid)
    return {"ok": True}


@router.get("/equipment/{eid}")
def digital_file(eid: str, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    """پرونده دیجیتال یکپارچه تجهیز."""
    e = _eq_or_404(conn, eid)
    insp = rows(conn, "SELECT i.*, (SELECT MIN(thickness_mm) FROM thickness_measurements t WHERE t.inspection_id=i.inspection_id) min_thickness_mm "
                      "FROM inspections i WHERE equipment_id=? ORDER BY inspection_date DESC", (eid,))
    ndt = rows(conn, "SELECT * FROM ndt_records WHERE equipment_id=? ORDER BY date DESC, priority_score DESC LIMIT 200", (eid,))
    imgs = rows(conn, "SELECT * FROM images WHERE equipment_id=? LIMIT 24", (eid,))
    return {"equipment": e, "risk": one(conn, "SELECT * FROM risk_assessments WHERE equipment_id=?", (eid,)),
            "plan": one(conn, "SELECT * FROM inspection_plans WHERE equipment_id=?", (eid,)),
            "inspections": insp, "ndt_records": ndt, "images": imgs,
            "alerts": rows(conn, "SELECT * FROM alerts WHERE equipment_id=? AND acknowledged=0", (eid,)),
            "summary": {"inspection_count": len(insp), "ndt_count": scalar(conn, "SELECT COUNT(*) FROM ndt_records WHERE equipment_id=?", (eid,)),
                        "open_defects": scalar(conn, "SELECT COUNT(*) FROM ndt_records WHERE equipment_id=? AND defect_type!='None' AND review_status!='rejected'", (eid,))}}


@router.get("/equipment/{eid}/thickness")
def thickness_series(eid: str, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    _eq_or_404(conn, eid)
    series = rows(conn, "SELECT measurement_date date, MIN(thickness_mm) min_mm, ROUND(AVG(thickness_mm),3) mean_mm, MAX(thickness_mm) max_mm, COUNT(*) points "
                        "FROM thickness_measurements WHERE equipment_id=? GROUP BY inspection_id ORDER BY date", (eid,))
    return {"series": series}


@router.get("/equipment/{eid}/compare")
def compare(eid: str, a: str, b: str, conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    """مقایسه نقطه‌به‌نقطه دو بازرسی (FR-M4-03)."""
    _eq_or_404(conn, eid)
    def pts(i):
        r = rows(conn, "SELECT point_id, thickness_mm FROM thickness_measurements WHERE inspection_id=? AND equipment_id=?", (i, eid))
        if not r:
            raise HTTPException(404, f"بازرسی {i} برای این تجهیز یافت نشد")
        return {x["point_id"]: x["thickness_mm"] for x in r}
    pa, pb = pts(a), pts(b)
    da = scalar(conn, "SELECT inspection_date FROM inspections WHERE inspection_id=?", (a,))
    db_ = scalar(conn, "SELECT inspection_date FROM inspections WHERE inspection_id=?", (b,))
    yrs = abs((datetime.fromisoformat(db_) - datetime.fromisoformat(da)).days) / 365.25 or None
    diff = [{"point_id": p, "a": pa[p], "b": pb[p], "delta_mm": round(pb[p] - pa[p], 2),
             "rate_mm_per_year": round((pa[p] - pb[p]) / yrs, 3) if yrs else None} for p in sorted(set(pa) & set(pb))]
    na = rows(conn, "SELECT defect_type, COUNT(*) n FROM ndt_records WHERE inspection_id=? GROUP BY defect_type", (a,))
    nb = rows(conn, "SELECT defect_type, COUNT(*) n FROM ndt_records WHERE inspection_id=? GROUP BY defect_type", (b,))
    worst = min(diff, key=lambda d: d["delta_mm"], default=None)
    return {"a": {"inspection_id": a, "date": da, "min_mm": min(pa.values()), "ndt": na},
            "b": {"inspection_id": b, "date": db_, "min_mm": min(pb.values()), "ndt": nb},
            "years_between": round(yrs, 2) if yrs else None, "points": diff, "worst_point": worst,
            "mean_delta_mm": round(sum(d["delta_mm"] for d in diff) / len(diff), 3) if diff else None}


@router.get("/inspections")
def list_inspections(equipment_id: str | None = None, page: int = 1, page_size: int = Query(25, le=200),
                     conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    w, p = ("WHERE i.equipment_id=?", [equipment_id]) if equipment_id else ("", [])
    total = scalar(conn, f"SELECT COUNT(*) FROM inspections i {w}", p)
    items = rows(conn, f"SELECT i.*, e.tag FROM inspections i JOIN equipment e USING(equipment_id) {w} "
                       "ORDER BY inspection_date DESC LIMIT ? OFFSET ?", p + [page_size, (max(page, 1) - 1) * page_size])
    return {"total": total, "items": items}


@router.post("/inspections", status_code=201)
def create_inspection(body: InspectionIn, conn: sqlite3.Connection = Depends(get_conn),
                      user=Depends(require("inspector", "ndt", "corrosion", "manager"))):
    e = _eq_or_404(conn, body.equipment_id)
    if body.inspection_date > date.today():
        raise HTTPException(422, "تاریخ بازرسی نمی‌تواند در آینده باشد")
    n = (scalar(conn, "SELECT MAX(CAST(SUBSTR(inspection_id,5) AS INTEGER)) FROM inspections") or 0) + 1
    iid = f"INS-{n:07d}"
    conn.execute("INSERT INTO inspections VALUES(?,?,?,?,?,?,?)",
                 (iid, e["equipment_id"], body.inspection_date.isoformat(), body.inspection_type, user["username"], body.method, body.remarks))
    prev = {r["point_id"]: r for r in rows(conn, "SELECT point_id, thickness_mm, measurement_date FROM thickness_measurements "
                                                 "WHERE equipment_id=? ORDER BY measurement_date", (e["equipment_id"],))}
    t0 = (scalar(conn, "SELECT MAX(CAST(SUBSTR(thickness_id,5) AS INTEGER)) FROM thickness_measurements") or 0) + 1
    warn = []
    for k, t in enumerate(body.thickness):
        pr = prev.get(t.point_id)
        rate = None
        if pr:
            dt = (body.inspection_date - date.fromisoformat(pr["measurement_date"])).days / 365.25
            rate = round(max((pr["thickness_mm"] - t.thickness_mm) / dt, 0), 4) if dt > 0 else None
        if t.thickness_mm < e["min_required_thickness_mm"]:
            warn.append(f"نقطه {t.point_id}: ضخامت کمتر از حداقل مجاز")
        conn.execute("INSERT INTO thickness_measurements VALUES(?,?,?,?,?,?,?,?,?)",
                     (f"THK-{t0 + k:08d}", iid, e["equipment_id"], t.point_id, body.inspection_date.isoformat(), t.thickness_mm,
                      e["nominal_thickness_mm"], e["min_required_thickness_mm"], rate))
    audit.log(conn, user["username"], "create", "inspection", iid, {"equipment_id": e["equipment_id"], "points": len(body.thickness)}, commit=False)
    conn.commit()
    res = engine.recompute(conn, [e["equipment_id"]])
    return {"inspection_id": iid, "warnings": warn, "recomputed": res,
            "risk": one(conn, "SELECT * FROM risk_assessments WHERE equipment_id=?", (e["equipment_id"],))}


@router.get("/search")
def search(q: str = Query(min_length=2), conn: sqlite3.Connection = Depends(get_conn), _=Depends(current_user)):
    """جستجوی یکپارچه در تجهیزات، بازرسی‌ها و عیوب."""
    like = f"%{q}%"
    return {
        "equipment": rows(conn, "SELECT equipment_id,tag,equipment_type,fluid,location,status FROM equipment WHERE is_deleted=0 AND "
                                "(tag LIKE ? OR equipment_id LIKE ? OR fluid LIKE ? OR material LIKE ? OR location LIKE ? OR equipment_type LIKE ?) LIMIT 15", [like] * 6),
        "inspections": rows(conn, "SELECT inspection_id,equipment_id,inspection_date,method,remarks FROM inspections WHERE inspection_id LIKE ? OR remarks LIKE ? LIMIT 10", [like] * 2),
        "ndt": rows(conn, "SELECT ndt_id,equipment_id,method,defect_type,result,date FROM ndt_records WHERE ndt_id LIKE ? OR defect_type LIKE ? OR result LIKE ? "
                          "ORDER BY priority_score DESC LIMIT 10", [like] * 3),
    }


# -------------------------------------------------------------------- import
REQUIRED = {
    "equipment": ["tag", "equipment_type", "material", "fluid", "install_date", "nominal_thickness_mm", "min_required_thickness_mm"],
    "inspections": ["equipment_id", "inspection_date"],
    "thickness": ["equipment_id", "inspection_id", "point_id", "measurement_date", "thickness_mm"],
    "ndt": ["equipment_id", "method", "date", "defect_type"],
}


def _read_df(file: UploadFile, raw: bytes) -> pd.DataFrame:
    name = (file.filename or "").lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(raw))
    if name.endswith(".json"):
        data = json.loads(raw.decode("utf-8-sig"))
        return pd.DataFrame(data if isinstance(data, list) else data.get("records", []))
    return pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")


@router.post("/import/{kind}")
async def import_data(kind: str, file: UploadFile = File(...), conn: sqlite3.Connection = Depends(get_conn),
                      user=Depends(require("inspector", "ndt", "manager", "asset"))):
    if kind not in REQUIRED:
        raise HTTPException(404, "نوع داده نامعتبر است: " + "/".join(REQUIRED))
    raw = await file.read()
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(413, "حجم فایل بیش از ۵۰ مگابایت است")
    try:
        df = _read_df(file, raw)
    except Exception as ex:
        raise HTTPException(422, f"فایل قابل خواندن نیست: {ex}")
    missing = [c for c in REQUIRED[kind] if c not in df.columns]
    if missing:
        raise HTTPException(422, "ستون‌های الزامی یافت نشد: " + ", ".join(missing))
    ok = bad = 0
    errors: list[dict] = []
    eq_ids = {r[0]: r for r in conn.execute("SELECT equipment_id, nominal_thickness_mm, min_required_thickness_mm FROM equipment")}
    touched = set()
    for i, r in df.iterrows():
        try:
            r = r.where(pd.notna(r), None)
            if kind == "equipment":
                if float(r["min_required_thickness_mm"]) >= float(r["nominal_thickness_mm"]):
                    raise ValueError("ضخامت حداقل ≥ اسمی")
                date.fromisoformat(str(r["install_date"])[:10])
                n = (scalar(conn, "SELECT MAX(CAST(SUBSTR(equipment_id,4) AS INTEGER)) FROM equipment") or 0) + 1
                v = [r.get(c) for c in EQ_COLS]
                v[5] = str(v[5])[:10]
                v[6] = v[6] if v[6] is not None else 0
                v[7] = v[7] if v[7] is not None else 25
                v[10] = int(v[10]) if v[10] is not None else 3
                v[11] = v[11] or "Active"
                conn.execute(f"INSERT INTO equipment(equipment_id,{','.join(EQ_COLS)}) VALUES(?,{','.join('?' * len(EQ_COLS))})", [f"EQ-{n:06d}"] + v)
            else:
                if r["equipment_id"] not in eq_ids:
                    raise ValueError("تجهیز ناشناخته")
                touched.add(r["equipment_id"])
                if kind == "inspections":
                    n = (scalar(conn, "SELECT MAX(CAST(SUBSTR(inspection_id,5) AS INTEGER)) FROM inspections") or 0) + 1
                    d = str(r["inspection_date"])[:10]
                    date.fromisoformat(d)
                    conn.execute("INSERT INTO inspections VALUES(?,?,?,?,?,?,?)",
                                 (f"INS-{n:07d}", r["equipment_id"], d, r.get("inspection_type") or "Periodic", r.get("inspector") or user["username"],
                                  r.get("method") or "UT", r.get("remarks") or ""))
                elif kind == "thickness":
                    th = float(r["thickness_mm"])
                    if not (0 < th < 500):
                        raise ValueError("ضخامت خارج از محدوده")
                    if not scalar(conn, "SELECT 1 FROM inspections WHERE inspection_id=? AND equipment_id=?", (r["inspection_id"], r["equipment_id"])):
                        raise ValueError("بازرسی ناشناخته")
                    n = (scalar(conn, "SELECT MAX(CAST(SUBSTR(thickness_id,5) AS INTEGER)) FROM thickness_measurements") or 0) + 1
                    _, nom, tm = eq_ids[r["equipment_id"]]
                    conn.execute("INSERT INTO thickness_measurements VALUES(?,?,?,?,?,?,?,?,?)",
                                 (f"THK-{n:08d}", r["inspection_id"], r["equipment_id"], r["point_id"], str(r["measurement_date"])[:10], th, nom, tm, None))
                else:
                    n = (scalar(conn, "SELECT MAX(CAST(SUBSTR(ndt_id,5) AS INTEGER)) FROM ndt_records") or 0) + 1
                    conn.execute("INSERT INTO ndt_records(ndt_id,equipment_id,inspection_id,method,date,defect_type,defect_size_mm,defect_depth_mm,"
                                 "defect_length_mm,result,confidence,inspector,priority_score) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 (f"NDT-{n:07d}", r["equipment_id"], r.get("inspection_id"), r["method"], str(r["date"])[:10], r["defect_type"],
                                  r.get("defect_size_mm") or 0, r.get("defect_depth_mm") or 0, r.get("defect_length_mm") or 0,
                                  r.get("result") or "Monitor", r.get("confidence") or 0.8, r.get("inspector") or user["username"], 0))
            ok += 1
        except Exception as ex:
            bad += 1
            if len(errors) < 50:
                errors.append({"row": int(i) + 2, "error": str(ex)})
    conn.commit()
    audit.log(conn, user["username"], "import", kind, file.filename or "", {"accepted": ok, "rejected": bad})
    if touched:
        engine.recompute(conn, sorted(touched)[:500])
    total = ok + bad
    return {"kind": kind, "total": total, "accepted": ok, "rejected": bad,
            "accept_rate": round(ok / total, 4) if total else 0, "meets_95pct": (ok / total >= 0.95) if total else False, "errors": errors}
