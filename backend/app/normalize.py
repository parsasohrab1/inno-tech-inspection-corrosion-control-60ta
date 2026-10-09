"""تبدیل داده واقعی (CSV/Excel/SQL با ستون‌های دلخواه) به ساختار استاندارد سامانه.

مثال نگاشت (mapping.json):
{
  "kind": "thickness",
  "columns": {"asset": "equipment_id", "survey": "inspection_id", "cml": "point_id",
              "date": "measurement_date", "wt_in": "thickness_mm"},
  "units": {"thickness_mm": "in"},
  "date_format": "%d/%m/%Y"
}
اجرا:  python -m app.normalize data.csv mapping.json out.csv
        python -m app.normalize "sqlite:///plant.db::SELECT ... FROM ..." mapping.json out.csv
"""
from __future__ import annotations

import json
import sqlite3
import sys

import pandas as pd

STANDARD = {
    "equipment": ["tag", "equipment_type", "material", "fluid", "location", "install_date", "design_pressure_bar",
                  "design_temp_c", "nominal_thickness_mm", "min_required_thickness_mm", "criticality", "status"],
    "inspections": ["equipment_id", "inspection_date", "inspection_type", "inspector", "method", "remarks"],
    "thickness": ["equipment_id", "inspection_id", "point_id", "measurement_date", "thickness_mm"],
    "ndt": ["equipment_id", "inspection_id", "method", "date", "defect_type", "defect_size_mm", "defect_depth_mm",
            "defect_length_mm", "result", "confidence", "inspector", "signal_file", "expert_label"],
}
UNIT_FACTORS = {("in", "mm"): 25.4, ("mil", "mm"): 0.0254, ("cm", "mm"): 10.0, ("psi", "bar"): 0.0689476,
                ("mpa", "bar"): 10.0, ("kpa", "bar"): 0.01, ("f", "c"): None, ("k", "c"): None}
DATE_COLS = {"install_date", "inspection_date", "measurement_date", "date"}


def read_source(src: str) -> pd.DataFrame:
    """CSV / Excel / JSON یا `sqlite:///path.db::SQL` ؛ برای سایر DBها از SQLAlchemy (در صورت نصب) استفاده می‌شود."""
    if "::" in src:
        dsn, sql = src.split("::", 1)
        if dsn.startswith("sqlite:///"):
            con = sqlite3.connect(dsn[len("sqlite:///"):])
            try:
                return pd.read_sql_query(sql, con)
            finally:
                con.close()
        try:
            from sqlalchemy import create_engine  # type: ignore
        except ImportError:
            raise SystemExit("برای PostgreSQL/Oracle/SQL Server: pip install sqlalchemy و درایور مربوطه")
        return pd.read_sql_query(sql, create_engine(dsn))
    low = src.lower()
    if low.endswith((".xlsx", ".xls")):
        return pd.read_excel(src)
    if low.endswith(".json"):
        return pd.DataFrame(json.load(open(src, encoding="utf-8-sig")))
    return pd.read_csv(src, encoding="utf-8-sig")


def convert_unit(s: pd.Series, frm: str, to: str) -> pd.Series:
    frm, to = frm.lower(), to.lower()
    if frm == "f" and to == "c":
        return (s - 32) * 5 / 9
    if frm == "k" and to == "c":
        return s - 273.15
    f = UNIT_FACTORS.get((frm, to))
    if f is None:
        raise ValueError(f"تبدیل واحد {frm}→{to} پشتیبانی نمی‌شود")
    return s * f


def normalize(df: pd.DataFrame, mapping: dict) -> tuple[pd.DataFrame, dict]:
    kind = mapping["kind"]
    if kind not in STANDARD:
        raise ValueError("kind نامعتبر: " + "/".join(STANDARD))
    df = df.rename(columns=mapping.get("columns", {}))
    report = {"input_rows": len(df), "dropped": {}, "warnings": []}
    for col, spec in mapping.get("units", {}).items():
        if col in df:
            frm, to = (spec.split("->") if "->" in spec else (spec, "mm" if col.endswith("_mm") else "bar" if col.endswith("_bar") else "c"))
            df[col] = convert_unit(pd.to_numeric(df[col], errors="coerce"), frm.strip(), to.strip())
    for col in DATE_COLS & set(df.columns):
        parsed = pd.to_datetime(df[col], format=mapping.get("date_format"), errors="coerce", dayfirst=mapping.get("dayfirst", False))
        bad = int(parsed.isna().sum() - df[col].isna().sum())
        if bad:
            report["warnings"].append(f"{bad} تاریخ نامعتبر در ستون {col}")
        df[col] = parsed.dt.strftime("%Y-%m-%d")
    keep = [c for c in STANDARD[kind] if c in df.columns]
    missing = [c for c in STANDARD[kind][:4 if kind != "equipment" else 6] if c not in df.columns]
    if missing:
        report["warnings"].append("ستون‌های کلیدی یافت نشد: " + ", ".join(missing))
    out = df[keep].copy()
    n0 = len(out)
    req = {"equipment": ["tag"], "inspections": ["equipment_id", "inspection_date"], "thickness": ["equipment_id", "inspection_id", "measurement_date", "thickness_mm"],
           "ndt": ["equipment_id", "date"]}[kind]
    out = out.dropna(subset=[c for c in req if c in out.columns])
    report["dropped"]["missing_key"] = n0 - len(out)
    if kind == "thickness" and "thickness_mm" in out:
        out["thickness_mm"] = pd.to_numeric(out["thickness_mm"], errors="coerce").round(3)
        n1 = len(out)
        out = out[(out["thickness_mm"] > 0) & (out["thickness_mm"] < 500)]
        report["dropped"]["thickness_out_of_range"] = n1 - len(out)
        n2 = len(out)
        out = out.drop_duplicates(["equipment_id", "inspection_id", "point_id"])
        report["dropped"]["duplicates"] = n2 - len(out)
    report["output_rows"] = len(out)
    return out, report


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    src, mp, dst = sys.argv[1:]
    mapping = json.load(open(mp, encoding="utf-8"))
    out, rep = normalize(read_source(src), mapping)
    out.to_csv(dst, index=False, encoding="utf-8-sig")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
