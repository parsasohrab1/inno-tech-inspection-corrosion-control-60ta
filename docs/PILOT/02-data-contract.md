# قرارداد ساختار داده

ستون‌های **الزامی** با ★ مشخص شده‌اند. واحدها: ضخامت mm، فشار bar، دما °C، تاریخ `YYYY-MM-DD`.
اگر داده شما واحد/نام ستون دیگری دارد، فایل `mapping.json` بنویسید (نمونه در docstring فایل `backend/app/normalize.py`؛ تبدیل in→mm، psi→bar، °F→°C پشتیبانی می‌شود).

| جدول (`kind`) | ستون‌ها |
|---|---|
| `equipment` | ★tag ★equipment_type ★material ★fluid location ★install_date design_pressure_bar design_temp_c ★nominal_thickness_mm ★min_required_thickness_mm criticality(1-5) status |
| `inspections` | ★equipment_id ★inspection_date inspection_type inspector method remarks |
| `thickness` | ★equipment_id ★inspection_id ★point_id ★measurement_date ★thickness_mm |
| `ndt` | ★equipment_id ★method ★date ★defect_type defect_size_mm defect_depth_mm defect_length_mm result confidence inspector signal_file **expert_label** |

- `defect_type`/`expert_label`: `Crack, Corrosion, Porosity, Slag, Lack of Fusion, Lamination, None`.
- `signal_file`: مسیر فایل `.npy` (آرایه یک‌بعدی A-scan) نسبت به پوشه `--signals`. فرمت‌های دیگر (CSV/JSON) را هم می‌توان با اسکریپت کوچک به `.npy` تبدیل کرد؛ فرمت‌های اختصاصی دستگاه (Olympus/Zetec) باید ابتدا صادر (export) شوند.
- هر `point_id` باید در بازرسی‌های مختلف **همان نقطه فیزیکی** (CML) باشد.
