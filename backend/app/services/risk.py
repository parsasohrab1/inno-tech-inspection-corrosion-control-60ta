"""M3 — ارزیابی ریسک (احتمال × پیامد، الهام‌گرفته از API 580/581) و برنامه بازرسی مبتنی بر ریسک."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from .. import config
from . import corrosion

FLUID_HAZARD = {"Acid Gas": 1.0, "Natural Gas": 0.9, "Hydrocarbon": 0.85, "Crude Oil": 0.8,
                "Steam": 0.6, "Water": 0.3, "Cooling Water": 0.25}
TYPE_FACTOR = {"Vessel": 1.0, "Column": 1.0, "Heat Exchanger": 0.9, "Pipeline": 0.85,
               "Storage Tank": 0.95, "Compressor": 0.8, "Pump": 0.6}
LEVEL_FA = {"Low": "کم", "Medium": "متوسط", "High": "زیاد"}
STANDARD = {"Vessel": "API 510", "Column": "API 510", "Heat Exchanger": "API 510", "Pipeline": "API 570",
            "Storage Tank": "API 653", "Pump": "API 580", "Compressor": "API 580"}
MAX_INTERVAL = {"High": 1.0, "Medium": 3.0, "Low": 5.0}
CAT_EDGES = [0.12, 0.28, 0.48, 0.72]


def _cat(v: float) -> int:
    return 1 + int(sum(v > e for e in CAT_EDGES))


def risk_level(score: float) -> str:
    return "High" if score >= config.RISK_HIGH else "Medium" if score >= config.RISK_MEDIUM else "Low"


def consequence(eq: dict, overrides: dict | None = None) -> float:
    o = overrides or {}
    fluid = o.get("fluid") or eq.get("fluid")
    press = float(eq.get("design_pressure_bar") or 0) + float(o.get("pressure_delta", 0))
    temp = float(eq.get("design_temp_c") or 0) + float(o.get("temp_delta", 0))
    crit = int(eq.get("criticality") or 3)
    base = (0.45 * crit / 5 + 0.30 * FLUID_HAZARD.get(fluid, 0.6)
            + 0.15 * min(max(press, 0) / 120, 1.2) + 0.10 * min(max(temp, 0) / 450, 1.2))
    return float(np.clip(base * TYPE_FACTOR.get(eq.get("equipment_type"), 0.8) * 1.05, 0, 1))


def probability(c: dict, defect_factor: float) -> float:
    rl_term = float(np.clip(1 - c["remaining_life_years"] / 15.0, 0, 1))
    pof = (0.40 * c["p_critical_5y"] + 0.25 * rl_term + 0.20 * (1 - c["health_index"]) + 0.15 * defect_factor)
    return float(np.clip(pof, 0, 1))


def method_for(level: str, eq_type: str, defect_types: set[str]) -> str:
    if defect_types & {"Crack", "Lack of Fusion"}:
        return "PAUT + ToFD"
    if "Corrosion" in defect_types or level == "High":
        return "PAUT" if eq_type != "Pump" else "VT + UT"
    if level == "Medium":
        return "UT"
    return "VT"


def assess(eq: dict, history: list[tuple], ndt: dict, overrides: dict | None = None,
           last_inspection: str | None = None, asof: date | None = None) -> dict | None:
    """ارزیابی کامل یک تجهیز؛ overrides برای تحلیل What-If."""
    o = overrides or {}
    asof = asof or date.today()
    n_rej, n_mon = ndt.get("reject", 0), ndt.get("monitor", 0)
    penalty = min(0.25, 0.08 * n_rej + 0.03 * n_mon)
    c = corrosion.analyze(history, eq["nominal_thickness_mm"], eq["min_required_thickness_mm"],
                          eq["install_date"], rate_multiplier=float(o.get("rate_multiplier", 1.0)),
                          defect_penalty=penalty, asof=asof)
    if not c.get("ok"):
        return None
    defect_factor = penalty / 0.25
    pof = probability(c, defect_factor)
    cof = consequence(eq, o)
    score = float(np.clip(100 * np.sqrt(pof * cof) * (0.5 + 0.5 * pof), 0, 100))
    level = risk_level(score)

    interval = min(c["remaining_life_years"] * 0.5, MAX_INTERVAL[level])
    interval = max(round(interval, 2), 0.25)
    delay = float(o.get("inspection_delay_months", 0)) / 12.0
    base = _d(last_inspection) if last_inspection else asof
    rec = base + timedelta(days=int(interval * 365.25) + int(delay * 365.25))
    overdue = rec < asof
    if overdue:
        rec = asof + timedelta(days=14 if level == "High" else 45)
    prio = "P1" if level == "High" else "P2" if level == "Medium" else "P3"
    method = method_for(level, eq["equipment_type"], ndt.get("types", set()))
    rationale = (f"ریسک {LEVEL_FA[level]} (امتیاز {score:.0f})؛ عمر باقیمانده {c['remaining_life_years']:.1f} سال، "
                 f"نرخ خوردگی {c['corrosion_rate']:.2f} mm/y؛ فاصله بازرسی = min(½ عمر باقیمانده، سقف سطح ریسک) = {interval:.1f} سال"
                 + ("؛ مهلت بازرسی گذشته است" if overdue else ""))
    return {
        "min_thickness_mm": c["current_thickness_mm"], "health_index": c["health_index"],
        "corrosion_rate_mm_per_year": c["corrosion_rate"], "remaining_life_years": c["remaining_life_years"],
        "rl_low": c["rl_low"], "rl_high": c["rl_high"], "pof_score": round(pof, 4), "cof_score": round(cof, 4),
        "pof_category": _cat(pof), "cof_category": _cat(cof), "risk_score": round(score, 2), "risk_level": level,
        "p_critical_1y": c["p_critical_1y"], "p_critical_3y": c["p_critical_3y"], "p_critical_5y": c["p_critical_5y"],
        "health_status": c["health_status"], "trend": c["trend"],
        "plan": {"recommended_date": rec.isoformat(), "priority": prio, "recommended_method": method,
                 "risk_level": level, "remaining_life_years": c["remaining_life_years"],
                 "interval_years": interval, "standard": STANDARD.get(eq["equipment_type"], "API 580"),
                 "rationale": rationale, "overdue": int(overdue)},
    }


def _d(s) -> date:
    return corrosion._d(s)


def heatmap(rows: list[dict]) -> dict:
    grid = [[{"count": 0, "equipment": []} for _ in range(5)] for _ in range(5)]
    for r in sorted(rows, key=lambda r: -r["risk_score"]):
        cell = grid[r["pof_category"] - 1][r["cof_category"] - 1]
        cell["count"] += 1
        if len(cell["equipment"]) < 8:
            cell["equipment"].append({"equipment_id": r["equipment_id"], "tag": r.get("tag"), "risk_score": r["risk_score"]})
    return {"pof_axis": [1, 2, 3, 4, 5], "cof_axis": [1, 2, 3, 4, 5], "grid": grid}
