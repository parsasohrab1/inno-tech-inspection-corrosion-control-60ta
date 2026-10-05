"""M1 — پیش‌پردازش سیگنال، شناسایی/طبقه‌بندی عیب و اولویت‌بندی (PAUT/ToFD A-scan)."""
from __future__ import annotations

import json

import numpy as np
from scipy.signal import find_peaks, savgol_filter
from scipy.stats import kurtosis

from .. import config

N_SAMPLES = 1024
BACKWALL_START = 0.82
DEFECT_TYPES = ["Crack", "Corrosion", "Porosity", "Slag", "Lack of Fusion", "Lamination"]
ALL_CLASSES = DEFECT_TYPES + ["None"]
FA = {"Crack": "ترک", "Corrosion": "خوردگی", "Porosity": "تخلخل", "Slag": "سرباره",
      "Lack of Fusion": "عدم ذوب", "Lamination": "لایه‌ای شدن", "None": "بدون عیب"}
SEVERITY = {"Crack": 1.0, "Lack of Fusion": 0.9, "Corrosion": 0.8, "Lamination": 0.7,
            "Slag": 0.5, "Porosity": 0.4, "None": 0.0}
MODEL_PATH = config.MODEL_DIR / "ndt_rf.joblib"
CARD_PATH = config.MODEL_DIR / "ndt_model_card.json"


# ---------------------------------------------------------------- generator
def _pulse(t, pos, width, amp, flat=False):
    z = np.abs((t - pos) / width)
    return amp * np.exp(-(z ** (6 if flat else 2)) / 2)


def make_signal(defect: str, rng: np.random.Generator, n: int = N_SAMPLES) -> np.ndarray:
    """A-scan مصنوعی با امضای متفاوت برای هر نوع عیب."""
    t = np.linspace(0, 1, n)
    x = rng.normal(0, 0.04, n)
    bw_pos = rng.uniform(0.88, 0.92)
    bw_amp = 1.0
    pos = rng.uniform(0.2, 0.72)
    if defect == "Crack":
        w = rng.uniform(0.006, 0.012)
        x += _pulse(t, pos, w, rng.uniform(0.7, 1.4))
        for _ in range(rng.integers(1, 4)):
            x += _pulse(t, pos + rng.uniform(0.012, 0.035), w, rng.uniform(0.12, 0.3))
        bw_amp = rng.uniform(0.6, 0.95)
    elif defect == "Corrosion":
        x += _pulse(t, pos, rng.uniform(0.03, 0.06), rng.uniform(0.3, 0.7))
        bw_amp = rng.uniform(0.4, 0.8)
        bw_pos -= rng.uniform(0, 0.04)
    elif defect == "Porosity":
        for _ in range(rng.integers(3, 7)):
            x += _pulse(t, pos + rng.uniform(-0.05, 0.05), rng.uniform(0.005, 0.01), rng.uniform(0.15, 0.35))
        bw_amp = rng.uniform(0.8, 1.0)
    elif defect == "Slag":
        w = rng.uniform(0.015, 0.025)
        x += _pulse(t, pos, w, rng.uniform(0.4, 0.8)) + _pulse(t, pos + w, w * 0.8, rng.uniform(0.2, 0.5))
        bw_amp = rng.uniform(0.7, 0.95)
    elif defect == "Lack of Fusion":
        x += _pulse(t, pos, rng.uniform(0.008, 0.014), rng.uniform(0.8, 1.5))
        bw_amp = rng.uniform(0.3, 0.7)
    elif defect == "Lamination":
        x += _pulse(t, pos, rng.uniform(0.04, 0.08), rng.uniform(1.2, 2.0), flat=True)
        bw_amp = rng.uniform(0.02, 0.2)
    x += _pulse(t, bw_pos, 0.012, bw_amp)
    return x.astype(np.float32)


# --------------------------------------------------------------- processing
def preprocess(x) -> dict:
    """نرمال‌سازی (حذف DC)، نویززدایی (Savitzky–Golay) و برآورد نویز (MAD)."""
    x = np.asarray(x, dtype=np.float64).ravel()
    if x.size < 64:
        raise ValueError("سیگنال بسیار کوتاه است (حداقل ۶۴ نمونه)")
    if not np.all(np.isfinite(x)):
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    x = x - np.median(x)
    smooth = savgol_filter(x, 9, 3)
    env = np.abs(smooth)
    resid = x - smooth
    sigma = max(1.4826 * np.median(np.abs(resid - np.median(resid))), 1e-6)
    peak = max(float(np.max(env)), 1e-9)
    return {"raw": x, "smooth": smooth, "env": env, "sigma": sigma, "ref": peak}


def _features(env: np.ndarray, sigma: float):
    n = env.size
    t = np.arange(n) / (n - 1)
    thr = max(6 * sigma, 0.1)
    idx, _ = find_peaks(env, height=thr, prominence=thr * 0.6, distance=max(2, n // 200))
    peaks = [{"pos": float(t[i]), "amp": float(env[i]), "i": int(i)} for i in idx]
    zone = [p for p in peaks if p["pos"] < BACKWALL_START]
    bw = [p for p in peaks if p["pos"] >= BACKWALL_START]
    bw_amp = max((p["amp"] for p in bw), default=0.0)
    if zone:
        main = max(zone, key=lambda p: p["amp"])
        half = main["amp"] / 2
        i = main["i"]
        lo = i
        while lo > 0 and env[lo] > half:
            lo -= 1
        hi = i
        while hi < n - 1 and env[hi] > half:
            hi += 1
        width = (hi - lo) / n
        seg = env[max(0, lo - 5): hi + 6]
        flat = float(np.mean(seg > 0.9 * main["amp"]))
        others = [p for p in zone if p is not main]
        n_sec = len(others)
        sec_ratio = max((p["amp"] for p in others), default=0.0) / main["amp"]
        amp = main["amp"]
        spread = max(p["pos"] for p in zone) - min(p["pos"] for p in zone)
    else:
        width = flat = n_sec = sec_ratio = amp = spread = 0.0
    energy_zone = float(np.sum(env[t < BACKWALL_START] ** 2) / (np.sum(env ** 2) + 1e-9))
    feats = np.array([amp, width, flat, len(zone), n_sec, sec_ratio, spread, bw_amp,
                      float(kurtosis(env)), energy_zone])
    return feats, zone


# -------------------------------------------------------------------- model
_model = None


def train_model(n_per_class: int | None = None, seed: int = 7) -> dict:
    import os
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import precision_recall_fscore_support

    n_per_class = n_per_class or int(os.getenv("NDT_TRAIN_PER_CLASS", "600"))
    rng = np.random.default_rng(seed)
    X, y = [], []
    for cls in ALL_CLASSES:
        for _ in range(n_per_class):
            p = preprocess(make_signal(cls, rng))
            f, _z = _features(p["env"], p["sigma"])
            X.append(f)
            y.append(cls)
    X, y = np.array(X), np.array(y)
    perm = rng.permutation(len(y))
    X, y = X[perm], y[perm]
    cut = int(len(y) * 0.75)
    clf = RandomForestClassifier(n_estimators=150, random_state=seed, n_jobs=1, class_weight="balanced")
    clf.fit(X[:cut], y[:cut])
    pred = clf.predict(X[cut:])
    pr, rc, _f1, sup = precision_recall_fscore_support(y[cut:], pred, labels=ALL_CLASSES, zero_division=0)
    yb, pb = y[cut:] != "None", pred != "None"
    tp = int(np.sum(yb & pb))
    fp = int(np.sum(~yb & pb))
    fn = int(np.sum(yb & ~pb))
    card = {
        "model": "RandomForest(150) روی ویژگی‌های A-scan",
        "training_data": "سیگنال مصنوعی با امضای متفاوت برای هر نوع عیب",
        "n_train": int(cut), "n_test": int(len(y) - cut),
        "detection": {"precision": round(tp / max(tp + fp, 1), 4), "recall": round(tp / max(tp + fn, 1), 4)},
        "per_class": {c: {"precision": round(float(a), 4), "recall": round(float(b), 4), "support": int(s)}
                      for c, a, b, s in zip(ALL_CLASSES, pr, rc, sup)},
        "macro_precision": round(float(np.mean(pr)), 4), "macro_recall": round(float(np.mean(rc)), 4),
        "targets": {"precision": 0.85, "recall": 0.80},
        "note": "اعتبارسنجی نهایی باید با داده واقعی انجام شود؛ تأیید کارشناس الزامی است.",
    }
    joblib.dump(clf, MODEL_PATH)
    CARD_PATH.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    global _model
    _model = clf
    return card


def get_model():
    global _model
    if _model is None:
        import joblib
        if not MODEL_PATH.exists():
            train_model()
        _model = joblib.load(MODEL_PATH)
    return _model


def model_card() -> dict:
    if not CARD_PATH.exists():
        train_model()
    return json.loads(CARD_PATH.read_text(encoding="utf-8"))


def priority_level(score: float) -> str:
    return "فوری" if score >= 70 else "بالا" if score >= 45 else "متوسط" if score >= 20 else "پایین"


def analyze_signal(samples, wall_thickness_mm: float = 30.0, with_trace: bool = True) -> dict:
    p = preprocess(samples)
    feats, zone = _features(p["env"], p["sigma"])
    snr = p["ref"] / p["sigma"]
    n = p["env"].size
    size = depth = length = prio = 0.0
    if not zone:
        best, conf, probs = "None", (0.9 if snr > 10 else 0.6), {"None": 1.0}
    else:
        clf = get_model()
        pr = clf.predict_proba([feats])[0]
        probs = {c: round(float(v), 4) for c, v in zip(clf.classes_, pr)}
        best = max(probs, key=probs.get)
        conf = probs[best]
        if best != "None":
            main = max(zone, key=lambda z: z["amp"])
            depth = main["pos"] * wall_thickness_mm
            length = max(feats[1] * wall_thickness_mm * 2.5, 0.5)
            size = max(length * (0.4 + 0.6 * min(main["amp"], 1.5) / 1.5), 0.5)
            amp_f = min(main["amp"] / p["ref"], 1.5) / 1.5
            prio = round(100 * conf * (0.6 * SEVERITY.get(best, 0.5) + 0.4 * amp_f), 1)
    out = {
        "defect_type": best, "defect_type_fa": FA[best], "confidence": round(float(conf), 3),
        "defect_detected": best != "None",
        "class_probabilities": probs,
        "defect_size_mm": round(float(size), 2), "defect_depth_mm": round(float(depth), 2),
        "defect_length_mm": round(float(length), 2),
        "snr": round(float(snr), 1), "priority_score": float(prio), "priority_level": priority_level(prio),
        "suggested_result": "Reject" if prio >= 70 else "Monitor" if prio >= 20 else "Accept",
        "indications": [{"position": round(z["pos"], 3), "amplitude": round(z["amp"], 3)} for z in zone],
        "requires_expert_review": True,
    }
    if with_trace:
        step = max(1, n // 512)
        out["trace"] = {"x": [round(i / (n - 1), 4) for i in range(0, n, step)],
                        "raw": [round(float(v), 4) for v in p["raw"][::step]],
                        "filtered": [round(float(v), 4) for v in p["env"][::step]]}
    return out


# -------------------------------------------------------------------- image
def analyze_image(img) -> dict:
    """تشخیص عیب در تصویر خاکستری (خط پایه: آستانه‌گذاری + مؤلفه‌های متصل)."""
    from scipy import ndimage as ndi
    a = np.asarray(img.convert("L"), dtype=np.float64)
    med = np.median(a)
    mad = max(1.4826 * np.median(np.abs(a - med)), 1.0)
    mask = a > med + 5.5 * mad
    lab, n = ndi.label(mask)
    sizes = ndi.sum(mask, lab, range(1, n + 1)) if n else []
    keep = [i + 1 for i, s in enumerate(sizes) if s >= 4]
    area = int(sum(sizes[i - 1] for i in keep)) if keep else 0
    detected = area >= 40
    bbox = None
    if detected:
        ys, xs = np.where(np.isin(lab, keep))
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    conf = min(0.99, 0.5 + area / 400) if detected else min(0.99, 0.95 - area / 100)
    return {"label": "defect" if detected else "no_defect", "label_fa": "دارای عیب" if detected else "بدون عیب",
            "confidence": round(float(conf), 3), "bright_area_px": area, "bbox": bbox, "components": len(keep),
            "size": [int(a.shape[1]), int(a.shape[0])]}
