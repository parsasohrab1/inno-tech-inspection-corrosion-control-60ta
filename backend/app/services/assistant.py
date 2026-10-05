"""M4 — دستیار هوشمند پرسش‌وپاسخ فنی (آفلاین، مبتنی بر داده).

پاسخ‌ها فقط از داده‌های ثبت‌شده در سامانه ساخته می‌شوند (بدون حدس)؛ هر پاسخ منبع داده دارد.
برای اتصال به LLM می‌توان `answer()` را با یک مدل زبانی پشت همین توابع ابزار (tools) جایگزین کرد.
"""
from __future__ import annotations

import re
import sqlite3

from ..db import one, rows, scalar

TYPE_WORDS = {
    "Storage Tank": ["مخزن ذخیره", "مخازن ذخیره", "مخزن", "مخازن", "tank"],
    "Heat Exchanger": ["مبدل", "مبدلها", "exchanger"],
    "Column": ["برج", "برجها", "column"],
    "Pipeline": ["خط لوله", "خطوط لوله", "لوله", "pipeline"],
    "Pump": ["پمپ", "پمپها", "pump"],
    "Compressor": ["کمپرسور", "کمپرسورها", "compressor"],
    "Vessel": ["ظرف", "ظروف", "وسل", "vessel"],
}
TYPE_FA = {"Storage Tank": "مخزن", "Heat Exchanger": "مبدل حرارتی", "Column": "برج", "Pipeline": "خط لوله",
           "Pump": "پمپ", "Compressor": "کمپرسور", "Vessel": "مخزن تحت فشار"}
DEFECT_WORDS = {"Crack": ["ترک"], "Corrosion": ["خوردگی"], "Porosity": ["تخلخل"], "Slag": ["سرباره"],
                "Lack of Fusion": ["عدم ذوب"], "Lamination": ["لایه"]}
HELP = ["کدام تجهیزات بیشترین ریسک افت یکپارچگی را دارند؟", "۱۰ مخزن با کمترین عمر باقیمانده", "وضعیت تجهیز VE-101",
        "نرخ خوردگی و عمر باقیمانده TA-105 چقدر است؟", "بازرسی‌های عقب‌افتاده کدامند؟", "چند تجهیز فعال داریم؟",
        "تعداد عیوب ترک تأییدنشده", "هشدارهای بحرانی را نشان بده", "برنامه بازرسی ماه آینده"]
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def norm(s: str) -> str:
    s = s.translate(_FA_DIGITS).replace("ي", "ی").replace("ك", "ک").replace("‌", "").replace("‏", "")
    s = re.sub(r"[ً-ٟ]", "", s)
    return s.lower().strip()


def _has(q, *words):
    return any(w in q for w in words)


def _result(answer, columns=None, data=None, sources=None, intent="", ok=True):
    return {"answer": answer, "table": {"columns": columns or [], "rows": data or []}, "sources": sources or [],
            "intent": intent, "grounded": ok}


def _eq_type(q):
    for t, ws in TYPE_WORDS.items():
        if any(norm(w) in q for w in ws):
            return t
    return None


def _top_n(q, default=10):
    m = re.search(r"(\d{1,3})\s*(تا|مورد|تجهیز|مخزن|مبدل|برج|پمپ|کمپرسور|خط|ظرف)", q) or re.search(r"(?:top|برترین|اول)\s*(\d{1,3})", q)
    return min(int(m.group(1)), 50) if m else default


def _eq_row_cols(r):
    return [r["tag"], TYPE_FA.get(r["equipment_type"], r["equipment_type"]), r["risk_score"], r["risk_level"],
            r["remaining_life_years"], r["health_index"]]


def answer(conn: sqlite3.Connection, text: str) -> dict:
    q = norm(text)
    if not q:
        return _result("لطفاً پرسش خود را بنویسید.", intent="empty", ok=False)

    # --- جستجوی تگ/شناسه
    m = re.search(r"\b([a-z]{2}-\d{3,4}|eq-\d{6})\b", q)
    if m:
        tag = m.group(1).upper()
        e = one(conn, "SELECT * FROM equipment WHERE (tag=? OR equipment_id=?) AND is_deleted=0", (tag, tag))
        if not e:
            return _result(f"تجهیزی با شناسه «{tag}» در سامانه یافت نشد.", intent="equipment", ok=False)
        r = one(conn, "SELECT * FROM risk_assessments WHERE equipment_id=?", (e["equipment_id"],)) or {}
        p = one(conn, "SELECT * FROM inspection_plans WHERE equipment_id=?", (e["equipment_id"],)) or {}
        nd = rows(conn, "SELECT defect_type, COUNT(*) n FROM ndt_records WHERE equipment_id=? AND defect_type!='None' AND review_status!='rejected' GROUP BY 1", (e["equipment_id"],))
        parts = [f"**{e['tag']}** ({TYPE_FA.get(e['equipment_type'], e['equipment_type'])}، {e['location']}، سیال: {e['fluid']}، وضعیت: {e['status']})."]
        if r:
            parts.append(f"ریسک: **{r['risk_score']:.0f}** ({r['risk_level']}) — شاخص سلامت {r['health_index']:.2f} ({r['health_status']}) — "
                         f"نرخ خوردگی {r['corrosion_rate_mm_per_year']:.3f} mm/y — ضخامت فعلی {r['min_thickness_mm']:.2f} mm "
                         f"(حداقل مجاز {e['min_required_thickness_mm']} mm) — عمر باقیمانده **{r['remaining_life_years']:.1f} سال** "
                         f"(بازه {r['rl_low']:.1f}–{r['rl_high']:.1f}).")
        if p:
            parts.append(f"برنامه بازرسی: {p['recommended_date']} با روش {p['recommended_method']} ({p['priority']}، مبنا: {p['standard']})"
                         + (" — **معوق**" if p["overdue"] else "") + ".")
        if nd:
            parts.append("عیوب ثبت‌شده: " + "، ".join(f"{d['defect_type']}×{d['n']}" for d in nd) + ".")
        return _result("\n".join(parts), ["تگ", "نوع", "امتیاز ریسک", "سطح", "عمر باقیمانده (سال)", "شاخص سلامت"],
                       [_eq_row_cols({**r, "tag": e["tag"], "equipment_type": e["equipment_type"]})] if r else [],
                       ["equipment", "risk_assessments", "inspection_plans", "ndt_records"], "equipment")

    et = _eq_type(q)
    loc = re.search(r"واحد\s*(\d{3})", q)
    where, p = "e.is_deleted=0", []
    if et:
        where += " AND e.equipment_type=?"; p.append(et)
    if loc:
        where += " AND e.location=?"; p.append(f"Unit {loc.group(1)}")
    scope = (TYPE_FA[et] if et else "تجهیز") + (f" در واحد {loc.group(1)}" if loc else "")
    n = _top_n(q)
    cols = ["تگ", "نوع", "امتیاز ریسک", "سطح", "عمر باقیمانده (سال)", "شاخص سلامت"]
    base = ("SELECT e.tag, e.equipment_type, r.risk_score, r.risk_level, r.remaining_life_years, r.health_index FROM risk_assessments r "
            f"JOIN equipment e USING(equipment_id) WHERE {where} AND e.status!='Out of Service'")

    def tbl(sql, args, order):
        rs = rows(conn, f"{sql} ORDER BY {order} LIMIT {n}", args)
        return [_eq_row_cols(r) for r in rs], rs

    # --- عمر باقیمانده
    if _has(q, "عمر باقیمانده", "کمترین عمر", "remaining life"):
        data, rs = tbl(base, p, "r.remaining_life_years ASC")
        return _result(f"{len(rs)} {scope} با کمترین عمر باقیمانده (بر اساس نرخ حاکم LT/ST و ضخامت فعلی):", cols, data,
                       ["risk_assessments", "thickness_measurements"], "remaining_life")
    # --- معوق
    if _has(q, "معوق", "عقب", "دیرکرد", "گذشته", "overdue"):
        total = scalar(conn, "SELECT COUNT(*) FROM inspection_plans WHERE overdue=1")
        rs = rows(conn, f"SELECT e.tag, p.priority, p.recommended_method, p.recommended_date, p.standard FROM inspection_plans p JOIN equipment e USING(equipment_id) "
                        f"WHERE p.overdue=1 AND {where} ORDER BY p.priority, p.recommended_date LIMIT {n}", p)
        return _result(f"{total} بازرسی معوق وجود دارد؛ {len(rs)} مورد با بالاترین اولویت:", ["تگ", "اولویت", "روش", "تاریخ پیشنهادی", "استاندارد"],
                       [list(r.values()) for r in rs], ["inspection_plans"], "overdue")
    # --- برنامه آتی
    if _has(q, "برنامه بازرسی", "برنامه") and not _has(q, "ریسک"):
        days = 60 if _has(q, "دو ماه") else 365 if _has(q, "سال") else 30 if _has(q, "ماه آینده", "یک ماه", "ماه") else 90
        rs = rows(conn, f"SELECT e.tag, p.priority, p.recommended_method, p.recommended_date, p.standard FROM inspection_plans p JOIN equipment e USING(equipment_id) "
                        f"WHERE p.recommended_date<=date('now','+{days} days') AND {where} ORDER BY p.recommended_date, p.priority LIMIT {max(n, 15)}", p)
        return _result(f"برنامه بازرسی تا {days} روز آینده ({len(rs)} مورد نمایش):", ["تگ", "اولویت", "روش", "تاریخ", "استاندارد"],
                       [list(r.values()) for r in rs], ["inspection_plans"], "plans")
    # --- هشدار
    if _has(q, "هشدار", "alert"):
        sev = "critical" if _has(q, "بحرانی") else None
        rs = rows(conn, "SELECT e.tag, a.severity, a.message FROM alerts a JOIN equipment e USING(equipment_id) WHERE a.acknowledged=0 "
                        + ("AND a.severity='critical' " if sev else "") + f"ORDER BY a.created_at DESC LIMIT {n}")
        total = scalar(conn, "SELECT COUNT(*) FROM alerts WHERE acknowledged=0" + (" AND severity='critical'" if sev else ""))
        return _result(f"{total} هشدار باز{' بحرانی' if sev else ''} وجود دارد:", ["تگ", "شدت", "پیام"], [list(r.values()) for r in rs], ["alerts"], "alerts")
    # --- عیوب
    if _has(q, "عیب", "عیوب", "ترک", "تخلخل", "سرباره", "ndt", "بازرسی غیرمخرب") or any(norm(w[0]) in q for w in DEFECT_WORDS.values()):
        dt = next((k for k, ws in DEFECT_WORDS.items() if any(w in q for w in ws)), None)
        pending = _has(q, "تأیید نشده", "تاییدنشده", "تأییدنشده", "منتظر", "بررسی")
        w2 = "n.defect_type!='None' AND n.review_status!='rejected'"
        if dt:
            w2 += f" AND n.defect_type='{dt}'"
        if pending:
            w2 += " AND n.review_status='pending'"
        total = scalar(conn, f"SELECT COUNT(*) FROM ndt_records n WHERE {w2}")
        rs = rows(conn, f"SELECT n.ndt_id, e.tag, n.defect_type, n.result, n.priority_score, n.review_status FROM ndt_records n JOIN equipment e USING(equipment_id) "
                        f"WHERE {w2} ORDER BY n.priority_score DESC LIMIT {n}")
        return _result(f"{total} رکورد عیب{' ' + dt if dt else ''}{' در انتظار تأیید' if pending else ''} ثبت شده است؛ {len(rs)} مورد با بالاترین اولویت:",
                       ["شناسه", "تگ", "نوع عیب", "نتیجه", "اولویت", "وضعیت بررسی"], [list(r.values()) for r in rs], ["ndt_records"], "defects")
    # --- تعداد
    if re.search(r"(^|\s)چند(\s|$)", q) or "تعداد" in q:
        st = "Active" if _has(q, "فعال") else "Standby" if _has(q, "آماده") else "Out of Service" if _has(q, "از مدار", "خارج") else None
        w3 = where + (" AND e.status=?" if st else "")
        c = scalar(conn, f"SELECT COUNT(*) FROM equipment e WHERE {w3}", p + ([st] if st else []))
        by = rows(conn, f"SELECT e.equipment_type t, COUNT(*) n FROM equipment e WHERE {w3} GROUP BY 1 ORDER BY n DESC", p + ([st] if st else []))
        return _result(f"{c} {scope}{' (' + st + ')' if st else ''} در سامانه ثبت شده است.", ["نوع", "تعداد"],
                       [[TYPE_FA.get(r['t'], r['t']), r['n']] for r in by], ["equipment"], "count")
    # --- سلامت
    if _has(q, "شاخص سلامت", "سلامت", "بحرانی"):
        data, rs = tbl(base, p, "r.health_index ASC")
        return _result(f"{len(rs)} {scope} با کمترین شاخص سلامت:", cols, data, ["risk_assessments"], "health")
    # --- ریسک (پیش‌فرض)
    if _has(q, "ریسک", "خطر", "یکپارچگی", "افت", "اولویت", "risk"):
        data, rs = tbl(base, p, "r.risk_score DESC")
        return _result(f"{len(rs)} {scope} با بیشترین ریسک افت یکپارچگی (ریسک = احتمال خرابی × پیامد؛ API 580/581):", cols, data,
                       ["risk_assessments", "equipment", "ndt_records"], "risk_top")
    return _result("این پرسش را نتوانستم از روی داده‌های سامانه پاسخ دهم و حدس نمی‌زنم. نمونه پرسش‌های پشتیبانی‌شده:\n- " + "\n- ".join(HELP),
                   intent="unknown", ok=False)
