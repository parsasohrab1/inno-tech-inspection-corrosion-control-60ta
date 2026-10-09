"""گزارش اعتبارسنجی مدل‌ها روی داده (واقعی یا مصنوعی) — شواهد برای ارتقای TRL.

اجرا:
  python -m app.validate --demo                       # روی پایگاه داده جاری (داده مصنوعی) — خودآزمایی ابزار
  python -m app.validate --equipment e.csv --thickness t.csv [--ndt n.csv --signals DIR] [--out DIR]

فایل NDT برای ارزیابی طبقه‌بندی باید ستون‌های ndt_id, signal_file و expert_label (برچسب کارشناس) داشته باشد؛
signal_file مسیر .npy نسبت به پوشه --signals است.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .services import corrosion, ndt


# ------------------------------------------------------------ data quality
def data_quality(eq: pd.DataFrame, th: pd.DataFrame) -> dict:
    th = th.copy()
    th["measurement_date"] = pd.to_datetime(th["measurement_date"], errors="coerce")
    per_eq = th.groupby("equipment_id")["measurement_date"].nunique()
    q = {"equipment": int(len(eq)), "thickness_rows": int(len(th)),
         "missing_cells_pct": round(float(th[["equipment_id", "measurement_date", "thickness_mm"]].isna().mean().mean() * 100), 2),
         "equipment_with_thickness": int(th["equipment_id"].nunique()),
         "equipment_without_thickness": int(len(set(eq["equipment_id"]) - set(th["equipment_id"]))),
         "inspections_per_equipment": {"median": float(per_eq.median()), "min": int(per_eq.min()), "max": int(per_eq.max())},
         "equipment_with_ge4_inspections": int((per_eq >= 4).sum()),
         "thickness_increase_events": 0, "below_min_required": 0}
    m = th.merge(eq[["equipment_id", "min_required_thickness_mm"]], on="equipment_id", how="left")
    q["below_min_required"] = int((m["thickness_mm"] < m["min_required_thickness_mm"]).sum())
    g = th.sort_values("measurement_date").groupby(["equipment_id", "point_id"])["thickness_mm"].diff()
    q["thickness_increase_events"] = int((g > 0.5).sum())  # رشد غیرفیزیکی > ۰٫۵mm (نویز یا تعمیر)
    q["warnings"] = []
    if q["equipment_with_ge4_inspections"] < 30:
        q["warnings"].append("کمتر از ۳۰ تجهیز با ≥۴ بازرسی؛ بک‌تست از نظر آماری ضعیف است")
    if q["thickness_increase_events"] > 0.05 * len(th):
        q["warnings"].append("بیش از ۵٪ افزایش ضخامت: کیفیت اندازه‌گیری یا تعمیرات ثبت‌نشده را بررسی کنید")
    return q


# ----------------------------------------------------------- corrosion
def corrosion_validation(eq: pd.DataFrame, th: pd.DataFrame) -> dict:
    """بک‌تست: آخرین بازرسی را کنار می‌گذارد و MAE و پوشش بازه ۹۰٪ را می‌سنجد؛ همچنین مقایسه با خط پایه ساده."""
    th = th.copy()
    th["measurement_date"] = pd.to_datetime(th["measurement_date"]).dt.date
    mins = th.groupby(["equipment_id", "measurement_date"])["thickness_mm"].min().reset_index()
    eqd = eq.set_index("equipment_id")
    errs, base_errs, cover, rows = [], [], [], []
    for eid, g in mins.groupby("equipment_id"):
        if eid not in eqd.index or len(g) < 4:
            continue
        g = g.sort_values("measurement_date")
        hist = list(zip(g["measurement_date"], g["thickness_mm"]))
        train, (td, tv) = hist[:-1], hist[-1]
        e = eqd.loc[eid]
        r = corrosion.analyze(train, float(e["nominal_thickness_mm"]), float(e["min_required_thickness_mm"]), e["install_date"], asof=td)
        if not r.get("ok"):
            continue
        dt = (td - train[-1][0]).days / 365.25
        pred = r["current_thickness_mm"] - r["corrosion_rate"] * dt
        sd = np.sqrt((r["rate_sigma"] * dt) ** 2 + corrosion.MEAS_SIGMA ** 2)
        errs.append(abs(pred - tv))
        cover.append(abs(pred - tv) <= 1.645 * sd)
        base_errs.append(abs(train[-1][1] - tv))  # خط پایه: «ضخامت تغییر نمی‌کند»
        rows.append({"equipment_id": eid, "abs_error": round(errs[-1], 3)})
    if not errs:
        return {"n": 0, "note": "داده کافی برای بک‌تست نیست"}
    a = np.array(errs)
    return {"n": int(a.size), "mae_mm": round(float(a.mean()), 4), "median_ae_mm": round(float(np.median(a)), 4),
            "p90_ae_mm": round(float(np.percentile(a, 90)), 4), "interval90_coverage": round(float(np.mean(cover)), 3),
            "baseline_mae_mm": round(float(np.mean(base_errs)), 4), "target_mae_mm": 0.5, "meets_target": bool(a.mean() <= 0.5),
            "beats_baseline": bool(a.mean() < np.mean(base_errs)), "worst": sorted(rows, key=lambda r: -r["abs_error"])[:5]}


# ----------------------------------------------------------------- NDT
def ndt_validation(df: pd.DataFrame, signal_dir: Path) -> dict:
    """مقایسه خروجی مدل با برچسب کارشناس (expert_label)."""
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
    y, p = [], []
    skipped = 0
    for _, r in df.iterrows():
        f = signal_dir / str(r["signal_file"])
        if not f.exists() or pd.isna(r.get("expert_label")):
            skipped += 1
            continue
        a = ndt.analyze_signal(np.load(f), with_trace=False)
        y.append(str(r["expert_label"]))
        p.append(a["defect_type"])
    if len(y) < 20:
        return {"n": len(y), "skipped": skipped, "note": "حداقل ۲۰ نمونه برچسب‌خورده لازم است"}
    labels = sorted(set(y) | set(p))
    pr, rc, _f, sup = precision_recall_fscore_support(y, p, labels=labels, zero_division=0)
    yb, pb = np.array(y) != "None", np.array(p) != "None"
    tp, fp, fn = int((yb & pb).sum()), int((~yb & pb).sum()), int((yb & ~pb).sum())
    det_p, det_r = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    return {"n": len(y), "skipped": skipped, "detection": {"precision": round(det_p, 3), "recall": round(det_r, 3)},
            "per_class": {l: {"precision": round(float(a), 3), "recall": round(float(b), 3), "support": int(s)} for l, a, b, s in zip(labels, pr, rc, sup)},
            "macro_precision": round(float(pr.mean()), 3), "macro_recall": round(float(rc.mean()), 3),
            "confusion_matrix": {"labels": labels, "matrix": confusion_matrix(y, p, labels=labels).tolist()},
            "meets_targets": bool(det_p >= 0.85 and det_r >= 0.80)}


# --------------------------------------------------------------- report
def to_markdown(rep: dict) -> str:
    L = [f"# گزارش اعتبارسنجی مدل‌ها ({rep['source']})", f"تاریخ: {rep['date']}", ""]
    q = rep["data_quality"]
    L += ["## ۱. کیفیت داده", f"- تجهیزات: {q['equipment']} · ردیف ضخامت: {q['thickness_rows']} · تجهیز با ≥۴ بازرسی: {q['equipment_with_ge4_inspections']}",
          f"- سلول‌های خالی: {q['missing_cells_pct']}٪ · ضخامت زیر حداقل مجاز: {q['below_min_required']} · افزایش غیرفیزیکی ضخامت: {q['thickness_increase_events']}"]
    L += [f"- ⚠ {w}" for w in q["warnings"]]
    c = rep["corrosion"]
    L += ["", "## ۲. پیش‌بینی خوردگی (بک‌تست آخرین بازرسی)"]
    if c.get("n"):
        L += [f"- نمونه: {c['n']} تجهیز · **MAE = {c['mae_mm']} mm** (هدف ≤ {c['target_mae_mm']}) → {'✔ برآورده' if c['meets_target'] else '✖ برآورده نشد'}",
              f"- میانه {c['median_ae_mm']} · صدک ۹۰ {c['p90_ae_mm']} · پوشش بازه ۹۰٪: {c['interval90_coverage']} (مطلوب ≈ ۰٫۹)",
              f"- خط پایه «بدون تغییر»: MAE {c['baseline_mae_mm']} → مدل {'بهتر از' if c['beats_baseline'] else 'بدتر از یا برابر'} خط پایه است"]
    else:
        L.append(f"- {c.get('note')}")
    n = rep.get("ndt")
    L += ["", "## ۳. تشخیص و طبقه‌بندی عیب"]
    if n and n.get("detection"):
        L += [f"- نمونه برچسب‌خورده: {n['n']} · تشخیص: Precision {n['detection']['precision']} / Recall {n['detection']['recall']} → {'✔' if n['meets_targets'] else '✖'} (هدف ≥ ۰٫۸۵ / ۰٫۸۰)",
              f"- طبقه‌بندی (میانگین): Precision {n['macro_precision']} / Recall {n['macro_recall']}"]
        L += [f"  - {k}: P={v['precision']} R={v['recall']} (n={v['support']})" for k, v in n["per_class"].items()]
    else:
        L.append("- " + (n.get("note", "داده NDT برچسب‌خورده ارائه نشده") if n else "داده NDT برچسب‌خورده ارائه نشده"))
    L += ["", "## نتیجه‌گیری برای TRL", rep["trl_note"]]
    return "\n".join(L)


def run(eq: pd.DataFrame, th: pd.DataFrame, ndt_df: pd.DataFrame | None, signals: Path | None, source: str, real: bool) -> dict:
    rep = {"source": source, "date": date.today().isoformat(), "real_data": real,
           "data_quality": data_quality(eq, th), "corrosion": corrosion_validation(eq, th),
           "ndt": ndt_validation(ndt_df, signals) if ndt_df is not None and signals else None}
    rep["trl_note"] = ("این اجرا روی **داده مصنوعی** بوده و فقط خودآزمایی ابزار است؛ شاهدی برای TRL 5 نیست."
                       if not real else
                       "اجرای روی داده واقعی. برای TRL 5 علاوه بر این گزارش لازم است: اجرا در محیط مرتبط (اتصال به سامانه‌های واحد)، "
                       "ارزیابی کارشناسان (docs/PILOT) و برآورده شدن اهداف SRS روی داده خارج از نمونه آموزش.")
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--equipment"); ap.add_argument("--thickness"); ap.add_argument("--ndt"); ap.add_argument("--signals")
    ap.add_argument("--out", default=str(config.DATA_DIR / "validation"))
    a = ap.parse_args()
    if a.demo:
        from .db import connect
        c = connect()
        eq = pd.read_sql_query("SELECT * FROM equipment WHERE is_deleted=0", c)
        th = pd.read_sql_query("SELECT equipment_id,inspection_id,point_id,measurement_date,thickness_mm FROM thickness_measurements", c)
        nd = pd.read_sql_query("SELECT ndt_id, signal_file, defect_type AS expert_label FROM ndt_records WHERE signal_file!='' LIMIT 300", c)
        rep = run(eq, th, nd, config.DATA_DIR, "داده مصنوعی (دمو)", real=False)
    else:
        if not (a.equipment and a.thickness):
            ap.error("--equipment و --thickness لازم است (یا --demo)")
        from .normalize import read_source
        rep = run(read_source(a.equipment), read_source(a.thickness), read_source(a.ndt) if a.ndt else None,
                  Path(a.signals) if a.signals else None, "داده واقعی", real=True)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "validation.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / "validation.md").write_text(to_markdown(rep), encoding="utf-8")
    print(to_markdown(rep)); print(f"\nذخیره شد: {out}")


if __name__ == "__main__":
    main()
