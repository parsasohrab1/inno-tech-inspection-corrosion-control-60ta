"""تولید داده مصنوعی (طبق پیوست SRS) و بارگذاری در پایگاه داده.

اجرا:  python -m app.seed [--reset]
"""
from __future__ import annotations

import random
import sys
import time
from datetime import date, datetime, timedelta

import numpy as np
from PIL import Image, ImageDraw

from . import config
from .db import connect, init_db, scalar
from .security import hash_password
from .services import audit, engine, ndt

EQUIP_TYPES = ["Vessel", "Pipeline", "Storage Tank", "Heat Exchanger", "Column", "Pump", "Compressor"]
MATERIALS = ["Carbon Steel A516", "Stainless Steel 304", "Stainless Steel 316", "Alloy Steel", "Duplex"]
FLUIDS = ["Crude Oil", "Natural Gas", "Water", "Steam", "Acid Gas", "Hydrocarbon", "Cooling Water"]
LOCATIONS = ["Unit 100", "Unit 200", "Unit 300", "Unit 400", "Utility", "Tank Farm"]
NDT_METHODS = ["PAUT", "ToFD", "UT", "RT", "VT", "MT", "PT"]
FLUID_F = {"Crude Oil": 1.2, "Natural Gas": 0.7, "Water": 1.6, "Steam": 0.9, "Acid Gas": 2.2, "Hydrocarbon": 1.0, "Cooling Water": 1.8}
DEMO_USERS = [
    ("admin", "مدیر سیستم", "admin"), ("manager", "مدیر بازرسی و تعمیرات", "manager"),
    ("asset", "مدیر دارایی", "asset"), ("inspector", "بازرس فنی", "inspector"),
    ("ndt", "کارشناس NDT", "ndt"), ("corrosion", "مهندس خوردگی", "corrosion"),
    ("rbi", "کارشناس RBI", "rbi"), ("hse", "مدیر HSE", "hse"),
]


def base_rate(material, fluid, temp, pressure, rng):
    base = rng.uniform(0.01, 0.06) if ("Stainless" in material or "Duplex" in material) else rng.uniform(0.05, 0.30)
    return base * FLUID_F[fluid] * (1 + max(0, (temp - 50) / 300)) * (1 + pressure / 150)


def seed(reset: bool = False, n_eq: int | None = None, n_ndt: int | None = None,
         n_sig: int | None = None, n_img: int | None = None, verbose: bool = True) -> dict:
    n_eq = n_eq or config.SEED_EQUIPMENT
    n_ndt = config.SEED_NDT if n_ndt is None else n_ndt
    n_sig = config.SEED_SIGNALS if n_sig is None else n_sig
    n_img = config.SEED_IMAGES if n_img is None else n_img
    if reset and config.DB_PATH.exists():
        for ext in ("", "-wal", "-shm"):
            p = config.DB_PATH.with_name(config.DB_PATH.name + ext)
            p.exists() and p.unlink()
    init_db()
    conn = connect()
    if scalar(conn, "SELECT COUNT(*) FROM equipment") > 0:
        conn.close()
        return {"skipped": True}
    log = (lambda m: print(f"[seed] {m}", flush=True)) if verbose else (lambda m: None)
    t0 = time.time()
    rng = np.random.default_rng(42)
    random.seed(42)
    today = date.today()

    # ---- users
    conn.executemany("INSERT INTO users(username,full_name,role,password_hash,is_active) VALUES(?,?,?,?,1)",
                     [(u, n, r, hash_password(config.DEMO_PASSWORD)) for u, n, r in DEMO_USERS])
    conn.executemany("INSERT INTO users(username,full_name,role,password_hash,is_active) VALUES(?,?,?,NULL,0)",
                     [(f"INS-{i:04d}", f"بازرس {i}", "inspector") for i in range(1, 151)] +
                     [(f"NDT-{i:04d}", f"کارشناس NDT {i}", "ndt") for i in range(1, 43)])

    # ---- equipment / inspections / thickness
    eq_rows, insp_rows, thk_rows = [], [], []
    insp_by_eq: dict[str, list[tuple]] = {}
    iid = tid = 1
    for i in range(1, n_eq + 1):
        eq_id = f"EQ-{i:06d}"
        et = random.choice(EQUIP_TYPES)
        mat, fluid = random.choice(MATERIALS), random.choice(FLUIDS)
        inst = today - timedelta(days=random.randint(365 * 2, 365 * 30))
        nominal = random.choice([6, 8, 10, 12, 14, 16, 20, 25, 30, 35])
        t_min = round(nominal * random.uniform(0.5, 0.8), 2)
        pressure, temp = round(random.uniform(1, 120), 2), random.randint(40, 450)
        status = random.choices(["Active", "Standby", "Out of Service"], weights=[0.8, 0.12, 0.08])[0]
        eq_rows.append((eq_id, f"{et[:2].upper()}-{100 + i}", et, mat, fluid, random.choice(LOCATIONS), inst.isoformat(),
                        pressure, temp, nominal, t_min, random.choices([1, 2, 3, 4, 5], weights=[1, 2, 3, 3, 2])[0], status))
        age = (today - inst).days / 365.25
        cr = base_rate(mat, fluid, temp, pressure, rng)
        allowable = nominal - t_min
        cr = min(cr, allowable * random.choices([rng.uniform(0.15, 0.7), rng.uniform(0.7, 1.05)], weights=[0.9, 0.1])[0] / age)
        accel = rng.uniform(0, 0.8) if random.random() < 0.25 else 0.0
        n_pts = random.randint(10, 25)
        pf = rng.lognormal(0, 0.12, n_pts)
        offs = rng.normal(0, 0.12, n_pts)
        d = inst
        n_ins = random.randint(5, 20)
        prev_t = np.full(n_pts, float(nominal))
        prev_d = inst
        for k in range(n_ins):
            d = d + timedelta(days=random.randint(180, 720))
            if d > today:
                break
            ins_id = f"INS-{iid:07d}"
            iid += 1
            insp_rows.append((ins_id, eq_id, d.isoformat(), random.choice(["Periodic", "Risk-Based", "Post-Repair", "Baseline"]),
                              f"INS-{random.randint(1, 150):04d}", random.choice(["UT", "PAUT", "ToFD", "VT", "RT"]), ""))
            insp_by_eq.setdefault(eq_id, []).append((ins_id, d.isoformat()))
            y = (d - inst).days / 365.25
            loss = cr * (y + accel * y * y / max(age, 1))
            thk = nominal - loss * pf + offs + rng.normal(0, 0.12, n_pts)
            thk = np.maximum(thk, t_min * 0.55)
            dt = max((d - prev_d).days / 365.25, 0.05)
            for p in range(n_pts):
                r = max((prev_t[p] - thk[p]) / dt, 0.0)
                thk_rows.append((f"THK-{tid:08d}", ins_id, eq_id, f"P-{p + 1:03d}", d.isoformat(), round(float(thk[p]), 2),
                                 nominal, t_min, round(float(r), 4)))
                tid += 1
            prev_t, prev_d = thk, d
    conn.executemany("INSERT INTO equipment(equipment_id,tag,equipment_type,material,fluid,location,install_date,design_pressure_bar,"
                     "design_temp_c,nominal_thickness_mm,min_required_thickness_mm,criticality,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", eq_rows)
    conn.executemany("INSERT INTO inspections VALUES(?,?,?,?,?,?,?)", insp_rows)
    conn.executemany("INSERT INTO thickness_measurements VALUES(?,?,?,?,?,?,?,?,?)", thk_rows)
    conn.commit()
    log(f"equipment={len(eq_rows)} inspections={len(insp_rows)} thickness={len(thk_rows)} ({time.time() - t0:.1f}s)")

    # ---- NDT records + signals
    if n_ndt:
        eq_ids = [r[0] for r in eq_rows if r[0] in insp_by_eq]
        ndt_rows = []
        sig_left = n_sig
        for i in range(1, n_ndt + 1):
            eq_id = random.choice(eq_ids)
            ins_id, ins_date = random.choice(insp_by_eq[eq_id])
            method = random.choice(NDT_METHODS)
            w = [0.15, 0.25, 0.10, 0.08, 0.07, 0.05, 0.30] if method in ("PAUT", "ToFD") else [0.05, 0.20, 0.10, 0.05, 0.05, 0.05, 0.50]
            defect = random.choices(ndt.DEFECT_TYPES + ["None"], weights=w)[0]
            if defect != "None":
                size, depth, length = round(random.uniform(0.5, 20), 2), round(random.uniform(0.5, 10), 2), round(random.uniform(1, 50), 2)
                result = random.choices(["Accept", "Monitor", "Reject"], weights=[0.5, 0.3, 0.2])[0]
            else:
                size = depth = length = 0.0
                result = "Accept"
            sig = ""
            prio = round(ndt.SEVERITY[defect] * random.uniform(30, 100), 1) if defect != "None" else 0.0
            if method in ("PAUT", "ToFD") and sig_left > 0:
                fn = f"{config.SIGNAL_DIR.name}/NDT-{i:07d}.npy"
                np.save(config.SIGNAL_DIR / f"NDT-{i:07d}.npy", ndt.make_signal(defect, rng))
                sig, sig_left = fn, sig_left - 1
            st = random.choices(["pending", "approved"], weights=[0.08, 0.92])[0] if defect != "None" else "approved"
            ndt_rows.append((f"NDT-{i:07d}", eq_id, ins_id, method, ins_date, defect, size, depth, length, result,
                             round(random.uniform(0.6, 0.99), 3), f"NDT-{random.randint(1, 42):04d}", sig, prio, st,
                             "ndt" if st == "approved" and defect != "None" else None))
        conn.executemany("INSERT INTO ndt_records(ndt_id,equipment_id,inspection_id,method,date,defect_type,defect_size_mm,"
                         "defect_depth_mm,defect_length_mm,result,confidence,inspector,signal_file,priority_score,review_status,reviewed_by) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ndt_rows)
        conn.commit()
        log(f"ndt={len(ndt_rows)} signals={n_sig - sig_left} ({time.time() - t0:.1f}s)")

    # ---- images
    if n_img:
        recs = []
        eqs = [r[0] for r in eq_rows]
        for i in range(n_img):
            img = Image.fromarray(np.clip(rng.normal(128, 20, (256, 256)), 0, 255).astype(np.uint8))
            label = random.choices(["defect", "no_defect"], weights=[0.4, 0.6])[0]
            if label == "defect":
                dr = ImageDraw.Draw(img)
                x1, y1 = random.randint(20, 200), random.randint(20, 200)
                x2, y2 = x1 + random.randint(10, 50), y1 + random.randint(10, 50)
                dr.ellipse([x1, y1, x2, y2], outline=255, width=3)
                dr.line([x1, y1, x2, y2], fill=255, width=2)
            img.save(config.IMAGE_DIR / f"IMG-{i:06d}.png")
            recs.append((f"IMG-{i:06d}", f"{config.IMAGE_DIR.name}/IMG-{i:06d}.png", label, random.choice(eqs)))
        conn.executemany("INSERT INTO images VALUES(?,?,?,?)", recs)
        conn.commit()
        log(f"images={n_img} ({time.time() - t0:.1f}s)")

    # ---- risk / plans / alerts
    res = engine.recompute(conn)
    audit.log(conn, "system", "seed", "system", "", {"equipment": n_eq, **res})
    log(f"risk+plans {res} ({time.time() - t0:.1f}s)")
    conn.close()
    ndt.train_model()
    log(f"model trained, done in {time.time() - t0:.1f}s")
    return {"skipped": False, **res}


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
