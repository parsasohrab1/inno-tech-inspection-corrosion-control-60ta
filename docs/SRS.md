# inno-tech-inspection-corrosion-control-60ta
# سند نیازمندی‌های نرم‌افزار (SRS)
## سامانه هوشمند یکپارچه بازرسی، پیش‌بینی خوردگی و مدیریت یکپارچگی دارایی‌ها

**نسخه:** 1.0  
**وضعیت:** پیش‌نویس جامع  
**مخاطب:** مدیران فنی، عملیاتی و برنامه‌ریزی؛ کارشناسان بازرسی، خوردگی، RBI و HSE؛ تیم توسعه و هوش مصنوعی  
**هدف:** تعریف کامل نیازمندی‌های عملکردی، غیرعملکردی، داده‌ای، معماری، رابط‌ها، تست و پذیرش سامانه‌ای که چهار ماژول تحلیل هوشمند بازرسی، پیش‌بینی خوردگی، ارزیابی ریسک و پرونده دیجیتال را یکپارچه می‌کند.

---

## 1. مقدمه

### 1.1 هدف سند
این سند نیازمندی‌های نرم‌افزاری سامانه هوشمند یکپارچه بازرسی، پیش‌بینی خوردگی و مدیریت یکپارچگی دارایی‌ها را مشخص می‌کند. سامانه باید بتواند داده‌های بازرسی، آزمون‌های غیرمخرب، ضخامت‌سنجی، شرایط عملیاتی، سوابق خوردگی و تعمیرات را تحلیل کرده و خروجی‌هایی مانند شناسایی عیوب، پیش‌بینی خوردگی، عمر باقیمانده، ریسک یکپارچگی و برنامه بازرسی هوشمند ارائه دهد.

### 1.2 دامنه
سامانه شامل چهار ماژول اصلی است:
1. تحلیل هوشمند داده‌های بازرسی و شناسایی عیوب
2. پیش‌بینی هوشمند خوردگی و وضعیت سلامت تجهیزات
3. ارزیابی هوشمند ریسک، عمر باقیمانده و برنامه‌ریزی بازرسی
4. پرونده دیجیتال تجهیزات و دستیار هوشمند بازرسی

### 1.3 تعاریف و اختصارات
| اصطلاح | تعریف |
|---|---|
| NDT | آزمون‌های غیرمخرب |
| PAUT | آزمون آرایه فازی فراصوتی |
| ToFD | آزمون زمان پرواز پراش |
| UT | ضخامت‌سنجی/آزمون فراصوتی |
| RBI | بازرسی مبتنی بر ریسک |
| Health Index | شاخص سلامت یکپارچگی تجهیز |
| Remaining Life | عمر باقیمانده تجهیز |
| Digital File | پرونده دیجیتال یکپارچه تجهیز |
| Human-in-the-Loop | تأیید نهایی توسط کارشناس |

### 1.4 فرضیات
- داده‌های واقعی ممکن است پراکنده، ناقص یا با فرمت‌های متفاوت باشند.
- سامانه به‌صورت Web-based و قابل استقرار در محیط ابری یا On-Premise طراحی می‌شود.
- تصمیم نهایی بازرسی و تأیید عیوب بر عهده کارشناس ذی‌صلاح است.
- مدل‌های هوش مصنوعی با داده مصنوعی و سپس داده واقعی اعتبارسنجی می‌شوند.

---

## 2. توصیف کلی محصول

### 2.1 چشم‌انداز
ایجاد یک بستر واحد برای هوشمندسازی چرخه عمر یکپارچگی دارایی‌های صنعتی، از ثبت داده خام بازرسی تا پیش‌بینی خوردگی، ارزیابی ریسک، برنامه‌ریزی بازرسی و تولید گزارش مدیریتی.

### 2.2 کاربران اصلی
- بازرس فنی
- کارشناس NDT
- مهندس خوردگی
- کارشناس RBI
- مدیر بازرسی و تعمیرات
- مدیر دارایی
- مدیر HSE
- مدیر سیستم

### 2.3 محیط عملیاتی
- رابط کاربری تحت وب، فارسی و راست‌به‌چپ
- پایگاه داده رابطه‌ای/سری‌زمانی
- سرویس‌های تحلیل سیگنال، تصویر و مدل‌های پیش‌بینی
- امکان اتصال به CMMS، ERP، DCS و سامانه‌های بازرسی موجود

### 2.4 محدودیت‌ها
- الزام به حفظ محرمانگی داده‌های فنی
- نیاز به Audit Trail کامل
- امکان کار در محیط بدون اینترنت
- پشتیبانی از فرمت‌های CSV، Excel، JSON، تصویر و سیگنال

---

## 3. معماری کلان

### 3.1 لایه‌ها
1. **لایه داده:** جمع‌آوری، پاک‌سازی، نرمال‌سازی و ذخیره‌سازی داده‌ها
2. **لایه هوش مصنوعی:** مدل‌های یادگیری عمیق، پردازش سیگنال، پردازش تصویر، مدل‌های پیش‌بینی خوردگی و ریسک
3. **لایه سرویس:** APIها، موتور قواعد، موتور RBI، دستیار هوشمند
4. **لایه ارائه:** داشبورد، پرونده دیجیتال، گزارش‌ساز، رابط پرسش‌وپاسخ

### 3.2 ماژول‌ها
- **M1:** تحلیل داده بازرسی و شناسایی عیوب
- **M2:** پیش‌بینی خوردگی و سلامت تجهیز
- **M3:** ارزیابی ریسک و برنامه‌ریزی بازرسی
- **M4:** پرونده دیجیتال و دستیار هوشمند

---

## 4. نیازمندی‌های داده

### 4.1 موجودیت‌های اصلی
| موجودیت | توضیح | تعداد رکورد مصنوعی پیشنهادی |
|---|---|---|
| Equipment | مشخصات تجهیز | 1,000 |
| Inspection | سوابق بازرسی | ~12,500 |
| ThicknessMeasurement | اندازه‌گیری ضخامت | ~200,000 |
| NDTRecord | رکوردهای NDT | 50,000 |
| Signal | سیگنال‌های PAUT/ToFD | 10,000 |
| Image | تصاویر بازرسی | 2,000 |
| RiskAssessment | ارزیابی ریسک | 1,000 |
| InspectionPlan | برنامه بازرسی | 1,000 |
| DigitalFile | پرونده دیجیتال | 1,000 |
| User | کاربران | 200 |
| AuditLog | لاگ اقدامات | نامحدود |

### 4.2 سیاست داده
- نسخه‌بندی داده‌ها
- عدم حذف فیزیکی رکوردها
- رمزنگاری در حالت سکون و انتقال
- کنترل دسترسی مبتنی بر نقش (RBAC)
- ثبت تمام تغییرات در Audit Log

---

## 5. نیازمندی‌های عملکردی

### 5.1 ماژول اول: تحلیل هوشمند داده‌های بازرسی و شناسایی عیوب
| شناسه | عنوان | شرح | معیار پذیرش |
|---|---|---|---|
| FR-M1-01 | ورود داده بازرسی | دریافت CSV، Excel، JSON، تصویر و سیگنال | حداقل 95% رکوردها بدون خطا وارد شوند |
| FR-M1-02 | پیش‌پردازش سیگنال | نرمال‌سازی، نویززدایی، فیلتر | خروجی قابل استفاده برای مدل |
| FR-M1-03 | شناسایی عیب | تشخیص ترک، خوردگی، ناپیوستگی | Precision ≥ 0.85 |
| FR-M1-04 | طبقه‌بندی عیب | تفکیک نوع عیب | Recall ≥ 0.80 |
| FR-M1-05 | اولویت‌بندی موارد مشکوک | رتبه‌بندی برای بررسی کارشناس | خروجی دارای امتیاز اطمینان |
| FR-M1-06 | تأیید کارشناس | Human-in-the-Loop | امکان تأیید/رد پیش‌بینی |
| FR-M1-07 | گزارش تحلیل | تولید گزارش بازرسی | قابل خروجی PDF/Excel |

### 5.2 ماژول دوم: پیش‌بینی خوردگی و وضعیت سلامت
| شناسه | عنوان | شرح | معیار پذیرش |
|---|---|---|---|
| FR-M2-01 | ورود سوابق ضخامت | دریافت داده‌های دوره‌ای | پشتیبانی از سری زمانی |
| FR-M2-02 | محاسبه نرخ خوردگی | نرخ فعلی و روند | خطای MAE ≤ 0.5 mm |
| FR-M2-03 | پیش‌بینی ضخامت آینده | برآورد ضخامت در دوره‌های آتی | افق پیش‌بینی حداقل 5 سال |
| FR-M2-04 | برآورد عمر باقیمانده | محاسبه Remaining Life | خروجی با بازه اطمینان |
| FR-M2-05 | شاخص سلامت | Health Index بین 0 تا 1 | قابل نمایش در داشبورد |
| FR-M2-06 | احتمال بحرانی شدن | احتمال رسیدن به حد بحرانی | هشدار خودکار |
| FR-M2-07 | هشدار و اعلان | اطلاع‌رسانی به کاربران | ایمیل/داشبورد |

### 5.3 ماژول سوم: ارزیابی ریسک و برنامه‌ریزی بازرسی
| شناسه | عنوان | شرح | معیار پذیرش |
|---|---|---|---|
| FR-M3-01 | ارزیابی ریسک | ترکیب احتمال و پیامد | Risk Score 0-100 |
| FR-M3-02 | رتبه‌بندی تجهیزات | اولویت‌بندی بر اساس ریسک | خروجی مرتب‌شده |
| FR-M3-03 | برنامه RBI | پیشنهاد زمان، روش و اولویت | مطابق API 580/581 |
| FR-M3-04 | تحلیل What-If | سناریوسازی شرایط عملیاتی | خروجی قابل مقایسه |
| FR-M3-05 | نقشه ریسک | نمایش Heat Map | به‌روزرسانی خودکار |

### 5.4 ماژول چهارم: پرونده دیجیتال و دستیار هوشمند
| شناسه | عنوان | شرح | معیار پذیرش |
|---|---|---|---|
| FR-M4-01 | پرونده دیجیتال | نگهداری تمام سوابق تجهیز | جستجوی سریع |
| FR-M4-02 | جستجوی یکپارچه | جستجو در همه داده‌ها | پاسخ < 2 ثانیه |
| FR-M4-03 | مقایسه بازرسی‌ها | مقایسه دوره‌ای | نمایش تغییرات |
| FR-M4-04 | دستیار هوشمند | پرسش‌وپاسخ فنی | پاسخ مبتنی بر داده |
| FR-M4-05 | تولید گزارش | گزارش اولیه، مدیریتی | خروجی PDF/Word |
| FR-M4-06 | داشبورد مدیریتی | نمایش وضعیت کلی | به‌روزرسانی لحظه‌ای |
| FR-M4-07 | Audit Trail | ثبت اقدامات | غیرقابل تغییر |

---

## 6. نیازمندی‌های غیرعملکردی

| حوزه | نیازمندی |
|---|---|
| عملکرد | API < 2s، تحلیل سیگنال < 5s، داشبورد < 3s |
| مقیاس‌پذیری | پشتیبانی از 10 میلیون رکورد و توسعه افقی |
| دسترس‌پذیری | 99.5% |
| امنیت | JWT، RBAC، رمزنگاری AES-256، Audit Log |
| قابلیت استفاده | رابط فارسی، RTL، واکنش‌گرا |
| نگهداشت‌پذیری | معماری ماژولار، CI/CD، تست خودکار |
| دقت مدل | Precision ≥ 0.85، Recall ≥ 0.80، MAE ≤ 0.5mm |
| انطباق | ASME، API 510/570/653، RBI |

---

## 7. رابط‌ها

### 7.1 رابط کاربری
- داشبورد مدیریتی
- صفحه تجهیزات
- صفحه بازرسی
- صفحه تحلیل NDT
- صفحه پیش‌بینی خوردگی
- صفحه ریسک و برنامه بازرسی
- دستیار هوشمند

### 7.2 APIهای اصلی
| متد | مسیر | توضیح |
|---|---|---|
| POST | /api/auth/login | ورود |
| GET | /api/equipment | لیست تجهیزات |
| GET | /api/equipment/{id} | جزئیات تجهیز |
| POST | /api/inspections | ثبت بازرسی |
| POST | /api/ndt/analyze | تحلیل NDT |
| GET | /api/predictions/corrosion/{id} | پیش‌بینی خوردگی |
| GET | /api/risk/ranking | رتبه‌بندی ریسک |
| GET | /api/plans | برنامه بازرسی |
| POST | /api/assistant/query | پرسش از دستیار |
| GET | /api/reports/{id} | دریافت گزارش |

### 7.3 پایگاه داده
- PostgreSQL برای داده‌های ساختاریافته
- TimescaleDB برای سری‌های زمانی ضخامت
- MinIO برای سیگنال و تصویر
- Redis برای Cache
- Elasticsearch برای جستجو

---

## 8. مدل داده (خلاصه)

### Equipment
`equipment_id, tag, type, material, fluid, location, install_date, design_pressure, design_temp, nominal_thickness, min_required_thickness, criticality, status`

### Inspection
`inspection_id, equipment_id, inspection_date, inspection_type, inspector, method, remarks`

### ThicknessMeasurement
`thickness_id, inspection_id, equipment_id, point_id, measurement_date, thickness_mm, nominal_thickness_mm, min_required_thickness_mm, corrosion_rate`

### NDTRecord
`ndt_id, equipment_id, inspection_id, method, date, defect_type, defect_size, defect_depth, defect_length, result, confidence, inspector, signal_file`

### RiskAssessment
`equipment_id, min_thickness, health_index, corrosion_rate, remaining_life, risk_score, risk_level`

### InspectionPlan
`equipment_id, recommended_date, priority, recommended_method, risk_level, remaining_life`

---

## 9. سناریوهای کاربردی

1. بازرس سیگنال PAUT را آپلود می‌کند؛ سامانه عیب را شناسایی و اولویت‌بندی می‌کند.
2. مهندس خوردگی روند ضخامت را مشاهده و عمر باقیمانده را پیش‌بینی می‌کند.
3. کارشناس RBI برنامه بازرسی مبتنی بر ریسک دریافت می‌کند.
4. مدیر با دستیار هوشمند می‌پرسد: «کدام تجهیزات در دوره آتی بیشترین ریسک افت یکپارچگی را دارند؟»
5. سامانه گزارش مدیریتی و نقشه ریسک تولید می‌کند.

---

## 10. معیارهای پذیرش
- ورود و ذخیره‌سازی صحیح حداقل 95% داده‌های نمونه
- تشخیص عیب با Precision ≥ 0.85
- پیش‌بینی خوردگی با MAE ≤ 0.5mm
- تولید برنامه بازرسی برای 100% تجهیزات فعال
- پاسخ دستیار هوشمند در کمتر از 5 ثانیه
- تأیید کارشناس برای تمام خروجی‌های حساس

---

## 11. تست و اعتبارسنجی
- تست واحد
- تست یکپارچگی
- تست عملکرد
- تست امنیت
- اعتبارسنجی مدل با داده مصنوعی و واقعی
- UAT با کاربران کلیدی

---

## 12. استقرار
- Docker و Kubernetes
- CI/CD
- مانیتورینگ با Prometheus/Grafana
- پشتیبان‌گیری دوره‌ای
- امکان استقرار On-Premise یا Cloud

---

## 13. ریسک‌ها
| ریسک | راهکار |
|---|---|
| کیفیت پایین داده | پاک‌سازی و اعتبارسنجی |
| مقاومت کاربران | آموزش و Human-in-the-Loop |
| امنیت داده | رمزنگاری و RBAC |
| دقت مدل | آموزش مستمر و داده بیشتر |
| پیچیدگی یکپارچگی | API استاندارد و لایه واسط |

---

## 14. نقشه راه پیشنهادی
- فاز 0: تحلیل و طراحی معماری
- فاز 1: پیاده‌سازی M1 و M4
- فاز 2: پیاده‌سازی M2
- فاز 3: پیاده‌سازی M3
- فاز 4: یکپارچگی، تست میدانی و استقرار

---

# پیوست: کد تولید داده مصنوعی

کد زیر داده‌های مصنوعی قابل اتکا برای توسعه، تست و اعتبارسنجی تولید می‌کند. تعداد رکوردها قابل تنظیم است و به‌صورت پیش‌فرض شامل 1,000 تجهیز، حدود 200,000 اندازه‌گیری ضخامت، 50,000 رکورد NDT، 10,000 سیگنال، 2,000 تصویر و 1,000 ارزیابی ریسک/برنامه بازرسی است.

```python
# synthetic_data_generator.py
import os
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

OUT = "synthetic_data"
os.makedirs(OUT, exist_ok=True)
os.makedirs(f"{OUT}/signals", exist_ok=True)
os.makedirs(f"{OUT}/images", exist_ok=True)

# -----------------------------
# Config
# -----------------------------
N_EQUIP = 1000
N_INSPECTION_PER_EQ_MIN = 5
N_INSPECTION_PER_EQ_MAX = 20
N_THICKNESS_POINTS_MIN = 10
N_THICKNESS_POINTS_MAX = 25
N_NDT = 50000
N_SIGNALS = 10000
N_IMAGES = 2000

equipment_types = ["Vessel", "Pipeline", "Storage Tank", "Heat Exchanger", "Column", "Pump", "Compressor"]
materials = ["Carbon Steel A516", "Stainless Steel 304", "Stainless Steel 316", "Alloy Steel", "Duplex"]
fluids = ["Crude Oil", "Natural Gas", "Water", "Steam", "Acid Gas", "Hydrocarbon", "Cooling Water"]
locations = ["Unit 100", "Unit 200", "Unit 300", "Unit 400", "Utility", "Tank Farm"]
ndt_methods = ["PAUT", "ToFD", "UT", "RT", "VT", "MT", "PT"]
defect_types = ["Crack", "Corrosion", "Porosity", "Slag", "Lack of Fusion", "Lamination", "None"]

# -----------------------------
# 1) Equipment
# -----------------------------
equipment_rows = []
for i in range(1, N_EQUIP + 1):
    eq_type = random.choice(equipment_types)
    material = random.choice(materials)
    fluid = random.choice(fluids)
    install_date = datetime.now() - timedelta(days=random.randint(365, 365 * 30))
    nominal_thickness = random.choice([6, 8, 10, 12, 14, 16, 20, 25, 30, 35])
    min_required = round(nominal_thickness * random.uniform(0.5, 0.8), 2)
    design_pressure = round(random.uniform(1, 120), 2)
    design_temp = random.randint(40, 450)
    criticality = random.randint(1, 5)
    tag = f"{eq_type[:2].upper()}-{random.randint(100, 999)}"

    equipment_rows.append({
        "equipment_id": f"EQ-{i:06d}",
        "tag": tag,
        "equipment_type": eq_type,
        "material": material,
        "fluid": fluid,
        "location": random.choice(locations),
        "install_date": install_date.strftime("%Y-%m-%d"),
        "design_pressure_bar": design_pressure,
        "design_temp_c": design_temp,
        "nominal_thickness_mm": nominal_thickness,
        "min_required_thickness_mm": min_required,
        "criticality": criticality,
        "status": random.choice(["Active", "Active", "Active", "Standby", "Out of Service"])
    })

equipment_df = pd.DataFrame(equipment_rows)
equipment_df.to_csv(f"{OUT}/equipment.csv", index=False)

# -----------------------------
# 2) Corrosion rate helper
# -----------------------------
def base_corrosion_rate(material, fluid, temp, pressure):
    if "Stainless" in material or "Duplex" in material:
        base = random.uniform(0.01, 0.08)
    else:
        base = random.uniform(0.08, 0.45)

    fluid_factor = {
        "Crude Oil": 1.2,
        "Natural Gas": 0.7,
        "Water": 1.6,
        "Steam": 0.9,
        "Acid Gas": 2.2,
        "Hydrocarbon": 1.0,
        "Cooling Water": 1.8
    }.get(fluid, 1.0)

    temp_factor = 1 + max(0, (temp - 50) / 300)
    pressure_factor = 1 + pressure / 150
    return base * fluid_factor * temp_factor * pressure_factor

# -----------------------------
# 3) Inspections & Thickness
# -----------------------------
inspection_rows = []
thickness_rows = []
inspection_id = 1
thickness_id = 1

for _, eq in equipment_df.iterrows():
    eq_id = eq["equipment_id"]
    install_date = datetime.strptime(eq["install_date"], "%Y-%m-%d")
    nominal = eq["nominal_thickness_mm"]
    min_req = eq["min_required_thickness_mm"]
    cr = base_corrosion_rate(eq["material"], eq["fluid"], eq["design_temp_c"], eq["design_pressure_bar"])

    n_insp = random.randint(N_INSPECTION_PER_EQ_MIN, N_INSPECTION_PER_EQ_MAX)
    current_date = install_date

    for _ in range(n_insp):
        current_date += timedelta(days=random.randint(180, 720))
        if current_date > datetime.now():
            break

        insp_id = f"INS-{inspection_id:07d}"
        inspection_id += 1

        inspection_rows.append({
            "inspection_id": insp_id,
            "equipment_id": eq_id,
            "inspection_date": current_date.strftime("%Y-%m-%d"),
            "inspection_type": random.choice(["Periodic", "Risk-Based", "Post-Repair", "Baseline"]),
            "inspector": f"INS-{random.randint(1, 200):04d}",
            "method": random.choice(["UT", "PAUT", "ToFD", "VT", "RT"]),
            "remarks": ""
        })

        years = (current_date - install_date).days / 365.25
        loss = cr * years * random.uniform(0.8, 1.2)
        n_points = random.randint(N_THICKNESS_POINTS_MIN, N_THICKNESS_POINTS_MAX)

        for p in range(1, n_points + 1):
            thickness = nominal - loss + np.random.normal(0, 0.3)
            thickness = max(thickness, min_req * 0.6)

            thickness_rows.append({
                "thickness_id": f"THK-{thickness_id:08d}",
                "inspection_id": insp_id,
                "equipment_id": eq_id,
                "point_id": f"P-{p:03d}",
                "measurement_date": current_date.strftime("%Y-%m-%d"),
                "thickness_mm": round(float(thickness), 2),
                "nominal_thickness_mm": nominal,
                "min_required_thickness_mm": min_req,
                "corrosion_rate_mm_per_year": round(cr, 4)
            })
            thickness_id += 1

inspection_df = pd.DataFrame(inspection_rows)
thickness_df = pd.DataFrame(thickness_rows)

inspection_df.to_csv(f"{OUT}/inspections.csv", index=False)
thickness_df.to_csv(f"{OUT}/thickness_measurements.csv", index=False)

# -----------------------------
# 4) NDT Records
# -----------------------------
eq_ids = equipment_df["equipment_id"].values
insp_by_eq = {k: v["inspection_id"].values for k, v in inspection_df.groupby("equipment_id")}

ndt_rows = []
for i in range(1, N_NDT + 1):
    eq_id = np.random.choice(eq_ids)
    insp_ids = insp_by_eq.get(eq_id)

    if insp_ids is None or len(insp_ids) == 0:
        continue

    insp_id = np.random.choice(insp_ids)
    method = random.choice(ndt_methods)

    if method in ["PAUT", "ToFD"]:
        defect = random.choices(
            defect_types,
            weights=[0.15, 0.25, 0.10, 0.08, 0.07, 0.05, 0.30]
        )[0]
    else:
        defect = random.choices(
            defect_types,
            weights=[0.05, 0.20, 0.10, 0.05, 0.05, 0.05, 0.50]
        )[0]

    if defect != "None":
        size = round(random.uniform(0.5, 20), 2)
        depth = round(random.uniform(0.5, 10), 2)
        length = round(random.uniform(1, 50), 2)
        result = random.choices(["Accept", "Monitor", "Reject"], weights=[0.5, 0.3, 0.2])[0]
    else:
        size = depth = length = 0.0
        result = "Accept"

    ndt_rows.append({
        "ndt_id": f"NDT-{i:07d}",
        "equipment_id": eq_id,
        "inspection_id": insp_id,
        "method": method,
        "date": str(pd.to_datetime(inspection_df.loc[inspection_df["inspection_id"] == insp_id, "inspection_date"].values[0]).date()),
        "defect_type": defect,
        "defect_size_mm": size,
        "defect_depth_mm": depth,
        "defect_length_mm": length,
        "result": result,
        "confidence": round(random.uniform(0.6, 0.99), 3),
        "inspector": f"NDT-{random.randint(1, 150):04d}",
        "signal_file": ""
    })

ndt_df = pd.DataFrame(ndt_rows)
ndt_df.to_csv(f"{OUT}/ndt_records.csv", index=False)

# -----------------------------
# 5) PAUT/ToFD Signals
# -----------------------------
signal_ndt = ndt_df[ndt_df["method"].isin(["PAUT", "ToFD"])].head(N_SIGNALS).copy()

for idx, row in signal_ndt.iterrows():
    n = 1024
    t = np.linspace(0, 1, n)
    signal = np.random.normal(0, 0.05, n)

    if row["defect_type"] != "None":
        pos = random.uniform(0.2, 0.8)
        width = random.uniform(0.01, 0.05)
        amp = random.uniform(0.5, 1.5)
        signal += amp * np.exp(-((t - pos) ** 2) / (2 * width ** 2))

        for _ in range(random.randint(1, 3)):
            pos2 = min(0.95, pos + random.uniform(0.05, 0.2))
            signal += random.uniform(0.2, 0.8) * np.exp(-((t - pos2) ** 2) / (2 * width ** 2))

    fname = f"signals/{row['ndt_id']}.npy"
    np.save(f"{OUT}/{fname}", signal.astype(np.float32))
    ndt_df.loc[idx, "signal_file"] = fname

ndt_df.to_csv(f"{OUT}/ndt_records.csv", index=False)

# -----------------------------
# 6) Synthetic Images
# -----------------------------
image_labels = []

for i in range(N_IMAGES):
    img = np.random.normal(128, 20, (256, 256)).clip(0, 255).astype(np.uint8)
    im = Image.fromarray(img)
    draw = ImageDraw.Draw(im)

    label = random.choices(["defect", "no_defect"], weights=[0.4, 0.6])[0]

    if label == "defect":
        x1, y1 = random.randint(20, 200), random.randint(20, 200)
        x2, y2 = x1 + random.randint(10, 50), y1 + random.randint(10, 50)
        draw.ellipse([x1, y1, x2, y2], outline=255, width=3)
        draw.line([x1, y1, x2, y2], fill=255, width=2)

    fname = f"images/IMG-{i:06d}.png"
    im.save(f"{OUT}/{fname}")
    image_labels.append({
        "image_id": f"IMG-{i:06d}",
        "file": fname,
        "label": label
    })

pd.DataFrame(image_labels).to_csv(f"{OUT}/image_labels.csv", index=False)

# -----------------------------
# 7) Risk Assessment & Inspection Plan
# -----------------------------
thickness_by_eq = {k: v for k, v in thickness_df.groupby("equipment_id")}
risk_rows = []
plan_rows = []

for _, eq in equipment_df.iterrows():
    eq_thk = thickness_by_eq.get(eq["equipment_id"])

    if eq_thk is None or len(eq_thk) == 0:
        continue

    latest = eq_thk.sort_values("measurement_date").iloc[-1]
    min_thk = eq_thk["thickness_mm"].min()
    cr = latest["corrosion_rate_mm_per_year"]
    min_req = eq["min_required_thickness_mm"]
    nominal = eq["nominal_thickness_mm"]

    health = max(0, min(1, (min_thk - min_req) / (nominal - min_req + 1e-6)))
    remaining_life = max(0, (min_thk - min_req) / (cr + 1e-6))
    risk_score = (eq["criticality"] / 5) * (1 - health) * (1 / (remaining_life + 1)) * 100
    risk_score = min(100, max(0, risk_score))

    risk_level = "High" if risk_score > 70 else "Medium" if risk_score > 40 else "Low"

    risk_rows.append({
        "equipment_id": eq["equipment_id"],
        "min_thickness_mm": round(min_thk, 2),
        "health_index": round(health, 3),
        "corrosion_rate_mm_per_year": round(cr, 4),
        "remaining_life_years": round(remaining_life, 2),
        "risk_score": round(risk_score, 2),
        "risk_level": risk_level
    })

    interval_days = int(max(30, min(365 * 4, remaining_life * 365 * 0.5)))
    plan_date = datetime.now() + timedelta(days=interval_days)
    priority = "P1" if risk_level == "High" else "P2" if risk_level == "Medium" else "P3"
    method = "PAUT" if risk_level == "High" else "UT" if risk_level == "Medium" else "VT"

    plan_rows.append({
        "equipment_id": eq["equipment_id"],
        "recommended_date": plan_date.strftime("%Y-%m-%d"),
        "priority": priority,
        "recommended_method": method,
        "risk_level": risk_level,
        "remaining_life_years": round(remaining_life, 2)
    })

pd.DataFrame(risk_rows).to_csv(f"{OUT}/risk_assessments.csv", index=False)
pd.DataFrame(plan_rows).to_csv(f"{OUT}/inspection_plans.csv", index=False)

print("Synthetic data generated successfully in:", OUT)
```

### خروجی‌های کد
- `equipment.csv`
- `inspections.csv`
- `thickness_measurements.csv`
- `ndt_records.csv`
- `signals/*.npy`
- `images/*.png`
- `image_labels.csv`
- `risk_assessments.csv`
- `inspection_plans.csv`

این داده‌ها برای توسعه اولیه، تست عملکرد، آموزش مدل‌های هوش مصنوعی، اعتبارسنجی APIها و شبیه‌سازی سناریوهای مدیریت یکپارچگی دارایی قابل استفاده هستند. برای داده واقعی، کافی است ساختار ستون‌ها حفظ شود و مدل‌ها با داده واقعی بازآموزی/تنظیم شوند.

---

## جمع‌بندی
این SRS چارچوب کامل محصول را در چهار ماژول، نیازمندی‌های داده، API، امنیت، تست، پذیرش و استقرار تعریف می‌کند. کد پیوست نیز با تولید تعداد قابل اتکا داده مصنوعی، امکان شروع سریع توسعه و ارزیابی محصول را فراهم می‌آورد. شرکت پتروپالاتوس می‌تواند بر این مبنا مستندات فنی تفصیلی، معماری اجرایی، شبیه‌سازی اولیه، گانت‌چارت و برنامه مالی را ارائه نماید.
