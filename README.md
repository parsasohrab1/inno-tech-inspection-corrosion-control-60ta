# سامانه هوشمند یکپارچه بازرسی، پیش‌بینی خوردگی و مدیریت یکپارچگی دارایی‌ها

پیاده‌سازی اجرایی سند [SRS](docs/SRS.md) — چهار ماژول در یک محصول وب فارسی (RTL):

| ماژول | قابلیت‌ها |
|---|---|
| **M1** تحلیل داده بازرسی | ورود CSV/Excel/JSON با گزارش نرخ پذیرش (≥۹۵٪)، پیش‌پردازش سیگنال (حذف DC، Savitzky–Golay، نویز MAD)، شناسایی و طبقه‌بندی عیب (RandomForest)، اولویت‌بندی، **تأیید/رد کارشناس (Human-in-the-Loop)**، تحلیل تصویر |
| **M2** پیش‌بینی خوردگی | نرخ LT/ST (حاکم = بیشینه)، پیش‌بینی ضخامت ۵+ ساله با بازه اطمینان، عمر باقیمانده با بازه، شاخص سلامت ۰–۱، احتمال بحرانی‌شدن ۱/۳/۵ ساله، هشدار (داشبورد + ایمیل SMTP اختیاری)، بک‌تست MAE |
| **M3** ریسک و RBI | امتیاز ریسک ۰–۱۰۰ (احتمال × پیامد، الهام‌گرفته از API 580/581)، رتبه‌بندی، نقشه حرارتی ۵×۵، برنامه بازرسی (فاصله = min(½ عمر باقیمانده، سقف سطح ریسک)؛ مبنا API 510/570/653)، **What-If** |
| **M4** پرونده دیجیتال | پرونده یکپارچه تجهیز، جستجوی یکپارچه، مقایسه دو بازرسی، دستیار پرسش‌وپاسخ مبتنی بر داده (آفلاین)، گزارش HTML/PDF/Excel، داشبورد، **Audit Trail غیرقابل تغییر** (زنجیره هش SHA-256 + تریگر DB) |

امنیت: JWT، RBAC (۸ نقش)، قفل موقت پس از ۵ ورود ناموفق، حذف نرم (بدون حذف فیزیکی)، هدرهای امنیتی.

## اجرای سریع

```bash
pip install -r requirements.txt
cd backend
python -m app.seed          # (اختیاری) تولید داده مصنوعی ≈ ۲٫۵ دقیقه
uvicorn app.main:app --port 8000
```

مرورگر: <http://localhost:8000> — در اولین اجرا اگر پایگاه داده خالی باشد (`AUTO_SEED=1`) داده مصنوعی خودکار در پس‌زمینه ساخته می‌شود (`/health` وضعیت `seeding` را نشان می‌دهد).
مستندات API (Swagger): <http://localhost:8000/docs>

**کاربران نمونه** (گذرواژه پیش‌فرض `Demo@12345`، با `DEMO_PASSWORD` قابل تغییر):
`admin` · `manager` · `asset` · `inspector` · `ndt` · `corrosion` · `rbi` · `hse`

### Docker

```bash
SECRET_KEY=$(openssl rand -hex 32) docker compose up --build
```

### داده مصنوعی
مطابق SRS: ۱٬۰۰۰ تجهیز، ≈۱۰ هزار بازرسی، ≈۱۶۵ هزار اندازه‌گیری ضخامت، ۵۰٬۰۰۰ رکورد NDT، ۱۰٬۰۰۰ سیگنال A-scan، ۲٬۰۰۰ تصویر. مقیاس با متغیرهای `SEED_*` در [.env.example](.env.example) قابل تنظیم است. برای داده واقعی، ساختار ستون‌ها را حفظ کرده و از «ورود داده» استفاده کنید.

## معماری

```
backend/app
  main.py            برنامه FastAPI و سرو فرانت
  db.py security.py  SQLite (WAL) و JWT/RBAC
  seed.py            تولید داده مصنوعی + آموزش مدل
  services/
    ndt.py           M1  سیگنال/تصویر/مدل عیب
    corrosion.py     M2  نرخ، پیش‌بینی، عمر باقیمانده، سلامت
    risk.py          M3  ریسک، RBI، What-If، نقشه حرارتی
    engine.py        محاسبه مجدد، هشدار، ایمیل
    assistant.py     M4  دستیار پرسش‌وپاسخ
    reports.py       M4  HTML / XLSX / PDF
    audit.py         Audit Trail زنجیره‌ای
  routers/           API (auth، assets، analytics، assistant_reports)
frontend/            SPA بدون وابستگی خارجی (قابل اجرا آفلاین)
backend/tests/       ۱۷ تست یکپارچگی (pytest)
```

SRS پایگاه‌های PostgreSQL/TimescaleDB/MinIO/Redis/Elasticsearch را برای مقیاس بزرگ پیشنهاد می‌کند؛ این نسخه برای استقرار تک‌گره و آفلاین با SQLite و فایل‌سیستم پیاده شده و لایه دسترسی داده (`db.py`، `engine.py`) برای جایگزینی ماژولار است.

## نقاط API
`POST /api/auth/login` · `GET /api/equipment[/{id}]` · `POST /api/inspections` · `POST /api/ndt/analyze` · `GET /api/predictions/corrosion/{id}` · `GET /api/risk/ranking` · `POST /api/risk/what-if` · `GET /api/plans` · `POST /api/assistant/query` · `GET /api/reports/{id}?format=html|pdf|xlsx` — فهرست کامل در `/docs`.

## کیفیت و اعتبارسنجی
```bash
python -m pytest        # از ریشه پروژه
```
معیارهای SRS روی داده مصنوعی (به‌صورت خودکار تست می‌شوند): Precision/Recall شناسایی و طبقه‌بندی ≥ ۰٫۸۵/۰٫۸۰ (کارت مدل در `/api/ndt/model-card`)، MAE پیش‌بینی ضخامت ≤ ۰٫۵ mm (`/api/predictions/metrics`)، برنامه بازرسی برای ۱۰۰٪ تجهیزات فعال/آماده، پاسخ دستیار < ۵ ثانیه، تحلیل سیگنال < ۵ ثانیه.

## اعتبارسنجی با داده واقعی (مسیر TRL 5)
```bash
cd backend
python -m app.normalize raw.csv mapping.json thickness.csv          # نگاشت ستون/واحد (CSV, Excel, JSON, SQL)
python -m app.validate --equipment eq.csv --thickness thickness.csv --ndt ndt.csv --signals DIR
python -m app.validate --demo                                        # خودآزمایی ابزار روی داده مصنوعی
```
خروجی `data/validation/validation.md|json` (کیفیت داده، MAE و پوشش بازه، مقایسه با خط پایه، Precision/Recall با برچسب کارشناس). بسته پایلوت: [docs/PILOT](docs/PILOT) (درخواست داده، قرارداد ستون‌ها، برگه ارزیابی کارشناسان).

> **هشدار:** مدل‌ها روی داده مصنوعی آموزش دیده‌اند؛ پیش از استفاده عملیاتی باید با داده واقعی بازآموزی و اعتبارسنجی شوند (`ndt.train_model()`). تمام خروجی‌ها پیشنهادی هستند و تصمیم نهایی بازرسی بر عهده کارشناس ذی‌صلاح است. پیش از استقرار `SECRET_KEY` و گذرواژه‌های نمونه را تغییر دهید.
