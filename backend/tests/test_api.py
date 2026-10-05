import io
import json

import numpy as np
import pytest
from PIL import Image


def H(tokens, role="admin"):
    return tokens[role]


def test_health_and_auth(client, tokens):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/equipment").status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "bad"}).status_code == 401
    me = client.get("/api/auth/me", headers=H(tokens)).json()
    assert me["role"] == "admin"


def test_rbac(client, tokens):
    assert client.get("/api/audit", headers=H(tokens, "inspector")).status_code == 403
    assert client.get("/api/audit", headers=H(tokens, "manager")).status_code == 200
    assert client.post("/api/risk/recompute", headers=H(tokens, "inspector")).status_code == 403


def test_equipment_listing_and_digital_file(client, tokens):
    r = client.get("/api/equipment?page_size=10&sort=risk", headers=H(tokens)).json()
    assert r["total"] == 60 and len(r["items"]) == 10
    scores = [i["risk_score"] for i in r["items"] if i["risk_score"] is not None]
    assert scores == sorted(scores, reverse=True)
    eid = r["items"][0]["equipment_id"]
    d = client.get(f"/api/equipment/{eid}", headers=H(tokens)).json()
    assert d["equipment"]["equipment_id"] == eid and d["risk"] and "inspections" in d
    assert client.get("/api/equipment/EQ-999999", headers=H(tokens)).status_code == 404
    s = client.get(f"/api/equipment/{eid}/thickness", headers=H(tokens)).json()["series"]
    assert len(s) >= 1


def test_corrosion_prediction(client, tokens):
    eid = client.get("/api/equipment?page_size=1", headers=H(tokens)).json()["items"][0]["equipment_id"]
    p = client.get(f"/api/predictions/corrosion/{eid}?horizon_years=5", headers=H(tokens)).json()
    assert p["forecast"][-1]["years_ahead"] == 5.0
    assert 0 <= p["health_index"] <= 1 and p["rl_low"] <= p["remaining_life_years"] <= p["rl_high"] + 1e-6
    th = [f["thickness_mm"] for f in p["forecast"]]
    assert th == sorted(th, reverse=True)
    assert p["p_critical_1y"] <= p["p_critical_3y"] <= p["p_critical_5y"]
    m = client.get("/api/predictions/metrics", headers=H(tokens)).json()
    assert m["n"] > 0 and m["mae_mm"] <= 0.5


def test_risk_ranking_heatmap_plans(client, tokens):
    rk = client.get("/api/risk/ranking?limit=20", headers=H(tokens)).json()["items"]
    assert rk[0]["rank"] == 1 and all(0 <= r["risk_score"] <= 100 for r in rk)
    hm = client.get("/api/risk/heatmap", headers=H(tokens)).json()
    assert len(hm["grid"]) == 5 and sum(c["count"] for row in hm["grid"] for c in row) > 0
    pl = client.get("/api/plans", headers=H(tokens)).json()
    # برنامه برای 100% تجهیزات فعال/آماده
    assert pl["plans_total"] == pl["active_equipment"]


def test_what_if(client, tokens):
    eid = client.get("/api/risk/ranking?limit=1", headers=H(tokens)).json()["items"][0]["equipment_id"]
    body = {"equipment_id": eid, "scenarios": [{"name": "نرخ ×۲", "rate_multiplier": 2.0}, {"name": "کند", "rate_multiplier": 0.5}]}
    r = client.post("/api/risk/what-if", json=body, headers=H(tokens)).json()["results"]
    assert r[0]["name"] == "پایه"
    assert r[1]["remaining_life_years"] <= r[0]["remaining_life_years"] <= r[2]["remaining_life_years"]
    assert r[1]["risk_score"] >= r[0]["risk_score"]


def test_ndt_analyze_signal_and_review(client, tokens):
    from app.services import ndt
    rng = np.random.default_rng(3)
    sig = ndt.make_signal("Crack", rng)
    buf = io.BytesIO(); np.save(buf, sig)
    eid = client.get("/api/equipment?page_size=1", headers=H(tokens)).json()["items"][0]["equipment_id"]
    r = client.post("/api/ndt/analyze", files={"file": ("s.npy", buf.getvalue())},
                    data={"equipment_id": eid, "save": "true"}, headers=H(tokens, "ndt"))
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["defect_detected"] and a["requires_expert_review"] and a["elapsed_s"] < 5
    assert "ndt_id" in a
    rv = client.post(f"/api/ndt/{a['ndt_id']}/review", json={"decision": "approve", "comment": "ok"}, headers=H(tokens, "ndt"))
    assert rv.status_code == 200
    assert client.get(f"/api/ndt/{a['ndt_id']}", headers=H(tokens)).json()["review_status"] == "approved"
    # بازرس/NDT می‌توانند، مدیر HSE نمی‌تواند تحلیل کند
    assert client.post("/api/ndt/analyze", files={"file": ("s.npy", buf.getvalue())}, headers=H(tokens, "hse")).status_code == 403


def test_ndt_bad_input(client, tokens):
    r = client.post("/api/ndt/analyze", files={"file": ("s.csv", b"a,b\nx,y\n")}, headers=H(tokens, "ndt"))
    assert r.status_code == 422
    short = io.BytesIO(); np.save(short, np.zeros(10))
    assert client.post("/api/ndt/analyze", files={"file": ("s.npy", short.getvalue())}, headers=H(tokens, "ndt")).status_code == 422


def test_model_quality_targets():
    from app.services import ndt
    card = ndt.model_card()
    assert card["detection"]["precision"] >= 0.85 and card["detection"]["recall"] >= 0.80
    assert card["macro_precision"] >= 0.85 and card["macro_recall"] >= 0.80


def test_image_analysis(client, tokens):
    img = Image.fromarray(np.clip(np.random.default_rng(1).normal(128, 20, (256, 256)), 0, 255).astype(np.uint8))
    from PIL import ImageDraw
    ImageDraw.Draw(img).ellipse([60, 60, 110, 110], outline=255, width=3)
    b = io.BytesIO(); img.save(b, "PNG")
    r = client.post("/api/ndt/analyze-image", files={"file": ("i.png", b.getvalue())}, headers=H(tokens, "ndt")).json()
    assert r["label"] == "defect" and r["bbox"]
    clean = Image.fromarray(np.clip(np.random.default_rng(2).normal(128, 20, (256, 256)), 0, 255).astype(np.uint8))
    b2 = io.BytesIO(); clean.save(b2, "PNG")
    assert client.post("/api/ndt/analyze-image", files={"file": ("i.png", b2.getvalue())}, headers=H(tokens, "ndt")).json()["label"] == "no_defect"


def test_create_inspection_triggers_recompute(client, tokens):
    eid = client.get("/api/equipment?page_size=1", headers=H(tokens)).json()["items"][0]["equipment_id"]
    d = client.get(f"/api/equipment/{eid}", headers=H(tokens)).json()
    before = d["risk"]["min_thickness_mm"]
    body = {"equipment_id": eid, "inspection_date": "2026-01-15", "method": "UT",
            "thickness": [{"point_id": f"P-{i:03d}", "thickness_mm": round(before - 0.8 + i * 0.01, 2)} for i in range(1, 8)]}
    r = client.post("/api/inspections", json=body, headers=H(tokens, "inspector"))
    assert r.status_code == 201, r.text
    assert r.json()["risk"]["min_thickness_mm"] < before
    assert client.post("/api/inspections", json={**body, "inspection_date": "2999-01-01"}, headers=H(tokens, "inspector")).status_code == 422


def test_import_acceptance(client, tokens):
    eq = client.get("/api/equipment?page_size=1", headers=H(tokens)).json()["items"][0]["equipment_id"]
    csv = "equipment_id,inspection_date,method\n" + "\n".join(f"{eq},2025-0{m}-10,UT" for m in range(1, 10)) + "\nEQ-NOPE,2025-01-01,UT\n"
    r = client.post("/api/import/inspections", files={"file": ("i.csv", csv.encode())}, headers=H(tokens, "inspector")).json()
    assert r["accepted"] == 9 and r["rejected"] == 1 and r["errors"][0]["row"] == 11
    bad = client.post("/api/import/inspections", files={"file": ("i.csv", b"x,y\n1,2\n")}, headers=H(tokens, "inspector"))
    assert bad.status_code == 422


def test_assistant(client, tokens):
    r = client.post("/api/assistant/query", json={"question": "کدام تجهیزات در دوره آتی بیشترین ریسک افت یکپارچگی را دارند؟"}, headers=H(tokens)).json()
    assert r["intent"] == "risk_top" and r["table"]["rows"] and r["elapsed_s"] < 5
    top = client.get("/api/risk/ranking?limit=1", headers=H(tokens)).json()["items"][0]
    assert r["table"]["rows"][0][0] == top["tag"]  # پاسخ مبتنی بر داده
    t = client.post("/api/assistant/query", json={"question": f"وضعیت {top['tag']}"}, headers=H(tokens)).json()
    assert t["intent"] == "equipment" and top["tag"] in t["answer"]
    u = client.post("/api/assistant/query", json={"question": "قیمت دلار چنده؟"}, headers=H(tokens)).json()
    assert u["intent"] == "unknown" and not u["grounded"]


def test_reports(client, tokens):
    eid = client.get("/api/equipment?page_size=1", headers=H(tokens)).json()["items"][0]["equipment_id"]
    for rid in ("management", eid):
        h = client.get(f"/api/reports/{rid}?format=html", headers=H(tokens))
        assert h.status_code == 200 and "dir='rtl'" in h.text
        x = client.get(f"/api/reports/{rid}?format=xlsx", headers=H(tokens))
        assert x.status_code == 200 and x.content[:2] == b"PK"
    p = client.get(f"/api/reports/{eid}?format=pdf", headers=H(tokens))
    assert p.status_code in (200, 501)
    if p.status_code == 200:
        assert p.content[:4] == b"%PDF"
    assert client.get("/api/reports/EQ-999999", headers=H(tokens)).status_code == 404


def test_audit_trail_immutable(client, tokens):
    v = client.get("/api/audit/verify", headers=H(tokens, "manager")).json()
    assert v["valid"] and v["checked"] > 0
    from app.db import connect
    c = connect()
    with pytest.raises(Exception, match="immutable"):
        c.execute("UPDATE audit_log SET username='x' WHERE id=1")
    with pytest.raises(Exception, match="immutable"):
        c.execute("DELETE FROM audit_log")
    c.close()


def test_dashboard_search_alerts(client, tokens):
    d = client.get("/api/dashboard", headers=H(tokens)).json()
    assert d["kpi"]["total"] == 60 and d["top_risk"]
    s = client.get("/api/search?q=Unit", headers=H(tokens)).json()
    assert s["equipment"]
    assert isinstance(client.get("/api/alerts", headers=H(tokens)).json(), list)


def test_soft_delete(client, tokens):
    r = client.post("/api/equipment", json={"tag": "TST-001", "equipment_type": "Vessel", "material": "Carbon Steel A516", "fluid": "Water",
                                            "install_date": "2015-01-01", "design_pressure_bar": 10, "design_temp_c": 100,
                                            "nominal_thickness_mm": 10, "min_required_thickness_mm": 6, "criticality": 3}, headers=H(tokens, "manager"))
    assert r.status_code == 201
    eid = r.json()["equipment_id"]
    assert client.delete(f"/api/equipment/{eid}", headers=H(tokens, "manager")).status_code == 200
    assert client.get(f"/api/equipment/{eid}", headers=H(tokens)).status_code == 404
    bad = client.post("/api/equipment", json={"tag": "TST-002", "equipment_type": "Vessel", "material": "x", "fluid": "Water", "install_date": "2015-01-01",
                                              "design_pressure_bar": 10, "design_temp_c": 100, "nominal_thickness_mm": 5, "min_required_thickness_mm": 6, "criticality": 3},
                      headers=H(tokens, "manager"))
    assert bad.status_code == 422
