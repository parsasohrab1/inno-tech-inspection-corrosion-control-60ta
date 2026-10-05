"""M2 — نرخ خوردگی، پیش‌بینی ضخامت، عمر باقیمانده، شاخص سلامت و احتمال بحرانی شدن."""
from __future__ import annotations

from datetime import date, datetime

import numpy as np
from scipy.stats import norm

MEAS_SIGMA = 0.25  # mm — عدم قطعیت اندازه‌گیری
MAX_LIFE = 100.0
EPS = 1e-4


def _d(s) -> date:
    return s if isinstance(s, date) else datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def _years(a: date, b: date) -> float:
    return (b - a).days / 365.25


def health_status(hi: float) -> str:
    return "بحرانی" if hi < 0.3 else "ضعیف" if hi < 0.5 else "متوسط" if hi < 0.75 else "خوب"


def analyze(history: list[tuple], nominal: float, t_min: float, install_date,
            rate_multiplier: float = 1.0, defect_penalty: float = 0.0,
            horizon_years: int = 5, asof: date | None = None) -> dict:
    """history: [(date, min_thickness_mm), ...] به ترتیب زمانی.

    نرخ حاکم = max(نرخ بلندمدت LT، نرخ کوتاه‌مدت ST) مطابق رویه API 510/570.
    """
    asof = asof or date.today()
    inst = _d(install_date)
    pts = sorted((_d(d), float(t)) for d, t in history)
    if not pts:
        return {"ok": False, "reason": "no_thickness_data"}
    last_d, cur = pts[-1]
    age = max(_years(inst, last_d), 0.25)
    lt = max((nominal - cur) / age, 0.0)

    # ST: رگرسیون روی ۳ اندازه‌گیری آخر
    st, se = lt, max(0.1 * lt, 0.02)
    recent = pts[-3:]
    if len(recent) >= 2:
        t0 = recent[0][0]
        x = np.array([_years(t0, d) for d, _ in recent])
        y = np.array([v for _, v in recent])
        if np.ptp(x) > 0.2:
            A = np.vstack([x, np.ones_like(x)]).T
            coef, res, *_ = np.linalg.lstsq(A, y, rcond=None)
            st = max(-coef[0], 0.0)
            if len(x) > 2:
                resid = y - A @ coef
                s2 = float(resid @ resid) / (len(x) - 2)
                se = float(np.sqrt(s2 / max(np.sum((x - x.mean()) ** 2), 1e-9)))
            else:
                se = float(np.sqrt(2) * MEAS_SIGMA / max(np.ptp(x), 0.2))
    # بلندمدت با همه نقاط (و نقطه نصب)
    if len(pts) >= 3:
        x = np.array([_years(inst, d) for d, _ in pts] + [0.0])
        y = np.array([v for _, v in pts] + [nominal])
        slope = np.polyfit(x, y, 1)[0]
        lt = max(lt, -slope) if -slope > 0 else lt
    rate = max(lt, st) * rate_multiplier
    sigma_r = max(se * rate_multiplier, 0.1 * rate, 0.01)
    trend = ("شتاب‌گیرنده" if st > 1.3 * lt and st > 0.05 else "کاهنده" if st < 0.7 * lt else "پایدار")

    margin = cur - t_min
    rl = MAX_LIFE if rate < EPS else min(max(margin, 0) / rate, MAX_LIFE)
    r_hi, r_lo = rate + 1.645 * sigma_r, max(rate - 1.645 * sigma_r, EPS)
    rl_low = min(max(margin, 0) / r_hi, MAX_LIFE)
    rl_high = min(max(margin, 0) / r_lo, MAX_LIFE)

    # پیش‌بینی ضخامت (فصلی) تا افق
    years_since = _years(last_d, asof)
    forecast = []
    steps = int(horizon_years * 4)
    for k in range(0, steps + 1):
        h = k * 0.25 + max(years_since, 0)
        mean = cur - rate * h
        sd = float(np.sqrt((sigma_r * h) ** 2 + MEAS_SIGMA ** 2))
        forecast.append({"years_ahead": round(k * 0.25, 2),
                         "date": _add_years(asof, k * 0.25).isoformat(),
                         "thickness_mm": round(mean, 3), "lower": round(mean - 1.645 * sd, 3),
                         "upper": round(mean + 1.645 * sd, 3)})

    def p_crit(hz):
        h = max(years_since, 0) + hz
        mean = cur - rate * h
        sd = float(np.sqrt((sigma_r * h) ** 2 + MEAS_SIGMA ** 2))
        return float(norm.cdf((t_min - mean) / sd))

    p1, p3, p5 = p_crit(1), p_crit(3), p_crit(5)
    margin_ratio = float(np.clip(margin / max(nominal - t_min, 1e-6), 0, 1))
    life_factor = float(min(1.0, rl / 20.0))
    hi = float(np.clip(0.55 * margin_ratio + 0.45 * life_factor - defect_penalty, 0, 1))
    if margin <= 0:
        hi = min(hi, 0.05)
    return {
        "ok": True, "current_thickness_mm": round(cur, 3), "last_inspection_date": last_d.isoformat(),
        "nominal_thickness_mm": nominal, "min_required_thickness_mm": t_min,
        "corrosion_rate_lt": round(lt, 4), "corrosion_rate_st": round(st, 4),
        "corrosion_rate": round(rate, 4), "rate_sigma": round(sigma_r, 4), "trend": trend,
        "remaining_life_years": round(rl, 2), "rl_low": round(rl_low, 2), "rl_high": round(rl_high, 2),
        "health_index": round(hi, 3), "health_status": health_status(hi),
        "p_critical_1y": round(p1, 4), "p_critical_3y": round(p3, 4), "p_critical_5y": round(p5, 4),
        "forecast": forecast, "n_points": len(pts),
        "critical_date": (_add_years(last_d, rl).isoformat() if rl < MAX_LIFE else None),
    }


def _add_years(d: date, y: float) -> date:
    try:
        return date.fromordinal(d.toordinal() + int(round(y * 365.25)))
    except ValueError:
        return date(9999, 12, 31)


def backtest(histories: dict[str, dict], limit: int = 400) -> dict:
    """آخرین اندازه‌گیری را کنار می‌گذارد، از قبلی‌ها پیش‌بینی می‌کند و MAE را برمی‌گرداند."""
    errs, rows = [], []
    for eid, h in histories.items():
        pts = sorted(h["history"])
        if len(pts) < 4:
            continue
        train, (td, tv) = pts[:-1], pts[-1]
        r = analyze(train, h["nominal"], h["t_min"], h["install"], asof=_d(td))
        if not r.get("ok"):
            continue
        dt = _years(_d(train[-1][0]), _d(td))
        pred = r["current_thickness_mm"] - r["corrosion_rate"] * dt
        e = abs(pred - tv)
        errs.append(e)
        rows.append({"equipment_id": eid, "predicted": round(pred, 3), "actual": round(tv, 3), "abs_error": round(e, 3)})
        if len(errs) >= limit:
            break
    if not errs:
        return {"n": 0}
    a = np.array(errs)
    return {"n": int(a.size), "mae_mm": round(float(a.mean()), 4), "median_ae_mm": round(float(np.median(a)), 4),
            "p90_ae_mm": round(float(np.percentile(a, 90)), 4), "target_mae_mm": 0.5,
            "meets_target": bool(a.mean() <= 0.5), "worst": sorted(rows, key=lambda r: -r["abs_error"])[:5]}
