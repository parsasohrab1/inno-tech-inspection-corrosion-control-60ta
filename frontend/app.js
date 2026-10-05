"use strict";
/* سامانه هوشمند بازرسی — SPA بدون وابستگی خارجی (قابل اجرا آفلاین) */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const nf = (v, d = 2) => v == null ? "—" : Number(v).toLocaleString("fa-IR", { maximumFractionDigits: d });
const pct = v => v == null ? "—" : nf(v * 100, 0) + "٪";
const jd = d => { try { return d ? new Intl.DateTimeFormat("fa-IR-u-ca-persian", { dateStyle: "medium" }).format(new Date(d)) : "—"; } catch { return d; } };
const badge = (v, label) => `<span class="badge b-${esc(v)}">${esc(label ?? v)}</span>`;
const LV = { High: "زیاد", Medium: "متوسط", Low: "کم" };
const lvBadge = l => badge(l, LV[l] || l);
const ROLE_ACT = { ndt: ["inspector", "ndt", "admin"], inspect: ["inspector", "ndt", "corrosion", "manager", "admin"], plan: ["rbi", "manager", "admin"], recompute: ["corrosion", "rbi", "manager", "admin"], audit: ["manager", "hse", "admin"], eq: ["manager", "asset", "admin"] };
const can = k => ROLE_ACT[k].includes(S.user?.role);
const S = { token: localStorage.getItem("token"), user: JSON.parse(localStorage.getItem("user") || "null") };

function toast(m, bad) { const t = $("#toast"); t.textContent = m; t.style.display = "block"; t.style.background = bad ? "var(--crit)" : ""; clearTimeout(t._t); t._t = setTimeout(() => t.style.display = "none", 3500); }

async function api(path, opt = {}) {
  const h = { ...(opt.headers || {}) };
  if (S.token) h.Authorization = "Bearer " + S.token;
  let body = opt.body;
  if (body && !(body instanceof FormData)) { h["Content-Type"] = "application/json"; body = JSON.stringify(body); }
  const r = await fetch(path, { ...opt, headers: h, body });
  if (r.status === 401 && !path.includes("/auth/login")) { logout(); throw new Error("نشست منقضی شد"); }
  if (opt.raw) return r;
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : Array.isArray(j.detail) ? j.detail.map(d => d.msg).join("؛ ") : "خطا " + r.status);
  return j;
}
function logout() { localStorage.clear(); S.token = null; S.user = null; render(); }
const guard = fn => async (...a) => { try { return await fn(...a); } catch (e) { toast(e.message, true); } };

/* ------------------------------------------------------------------ charts */
function lineChart({ series, band, hline, w = 640, h = 280, yLabel = "", xdate = true }) {
  const all = series.flatMap(s => s.pts), bandPts = band || [];
  const xs = all.map(p => p[0]).concat(bandPts.map(p => p[0])), ys = all.map(p => p[1]).concat(bandPts.flatMap(p => [p[1], p[2]])).concat(hline ? [hline.y] : []);
  if (!xs.length) return "<p class='muted'>داده‌ای وجود ندارد</p>";
  const m = { l: 44, r: 10, t: 10, b: 28 }, x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys) - 0.5, y1 = Math.max(...ys) + 0.5;
  const X = x => m.l + (x - x0) / (x1 - x0 || 1) * (w - m.l - m.r), Y = y => h - m.b - (y - y0) / (y1 - y0 || 1) * (h - m.t - m.b);
  let o = `<svg viewBox="0 0 ${w} ${h}" width="100%" role="img" style="direction:ltr">`;
  for (let i = 0; i <= 4; i++) { const v = y0 + (y1 - y0) * i / 4; o += `<line class="ax" x1="${m.l}" x2="${w - m.r}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${m.l - 4}" y="${Y(v) + 4}" text-anchor="end">${nf(v, 1)}</text>`; }
  for (let i = 0; i <= 4; i++) { const v = x0 + (x1 - x0) * i / 4; o += `<text x="${X(v)}" y="${h - 8}" text-anchor="middle">${xdate ? jd(v).split(" ").slice(-1)[0] : nf(v / 1000, 2)}</text>`; }
  if (band?.length) o += `<path d="M${band.map(p => `${X(p[0])},${Y(p[2])}`).join("L")}L${[...band].reverse().map(p => `${X(p[0])},${Y(p[1])}`).join("L")}Z" fill="#1479a3" opacity=".18"/>`;
  if (hline) o += `<line x1="${m.l}" x2="${w - m.r}" y1="${Y(hline.y)}" y2="${Y(hline.y)}" stroke="#b3122b" stroke-dasharray="6 4"/><text x="${w - m.r - 4}" y="${Y(hline.y) - 4}" text-anchor="end" style="fill:#b3122b">${hline.label}</text>`;
  for (const s of series) {
    o += `<polyline fill="none" stroke="${s.color}" stroke-width="2" ${s.dash ? 'stroke-dasharray="6 4"' : ""} points="${s.pts.map(p => `${X(p[0])},${Y(p[1])}`).join(" ")}"/>`;
    if (s.dots) o += s.pts.map(p => `<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="3" fill="${s.color}"><title>${xdate ? jd(p[0]) : nf(p[0] / 1000)}: ${nf(p[1])}</title></circle>`).join("");
  }
  if (yLabel) o += `<text x="12" y="12">${yLabel}</text>`;
  return o + "</svg>";
}
function donut(data, colors) {
  const tot = data.reduce((a, d) => a + d.n, 0) || 1; let a0 = -Math.PI / 2, o = `<svg viewBox="-60 -60 120 120" width="150">`;
  data.forEach((d, i) => { const a1 = a0 + d.n / tot * 2 * Math.PI, big = a1 - a0 > Math.PI ? 1 : 0;
    o += `<path d="M${50 * Math.cos(a0)},${50 * Math.sin(a0)}A50,50 0 ${big} 1 ${50 * Math.cos(a1 - .001)},${50 * Math.sin(a1 - .001)}" stroke="${colors[i % colors.length]}" stroke-width="16" fill="none"><title>${d.label}: ${d.n}</title></path>`; a0 = a1; });
  return o + `<text x="0" y="5" text-anchor="middle" style="font-size:16px;font-weight:700;fill:var(--ink)">${nf(tot, 0)}</text></svg>`;
}
const hbars = (items, key, val, color = "var(--pri2)") => { const mx = Math.max(...items.map(i => i[val]), 1); return items.map(i => `<div class="hbar"><span>${esc(i[key])}</span><div class="bar"><i style="width:${i[val] / mx * 100}%;background:${color}"></i></div><b>${nf(i[val], 0)}</b></div>`).join(""); };
const table = (cols, rows, opt = {}) => `<div class="tw"><table><thead><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr class="${opt.click ? "click" : ""}" ${opt.attr ? opt.attr(r) : ""}>${r.cells.map(c => `<td>${c}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${cols.length}" class="muted">موردی یافت نشد</td></tr>`}</tbody></table></div>`;

async function download(path, name) {
  const r = await api(path, { raw: true });
  if (!r.ok) { const j = await r.json().catch(() => ({})); return toast(j.detail || "خطا در دریافت گزارش", true); }
  const u = URL.createObjectURL(await r.blob());
  if (name.endsWith(".html")) window.open(u, "_blank"); else { const a = document.createElement("a"); a.href = u; a.download = name; a.click(); }
}
window.dl = guard(download);

/* ------------------------------------------------------------------- shell */
const NAV = [["dashboard", "داشبورد"], ["equipment", "تجهیزات و پرونده دیجیتال"], ["ndt", "تحلیل NDT (M1)"], ["corrosion", "پیش‌بینی خوردگی (M2)"], ["risk", "ریسک و What-If (M3)"], ["plans", "برنامه بازرسی"],
  ["inspections", "ثبت بازرسی و ورود داده"], ["assistant", "دستیار هوشمند"], ["reports", "گزارش‌ها"], ["admin", "ممیزی و مدل‌ها"]];

function render() {
  if (!S.token) {
    $("#root").innerHTML = `<form class="card login" id="lf"><h2>ورود به سامانه</h2><label>نام کاربری<input name="u" value="admin" autocomplete="username" required></label>
      <label>گذرواژه<input name="p" type="password" autocomplete="current-password" required></label><button style="width:100%">ورود</button>
      <p class="muted" style="font-size:12px">کاربران نمونه: admin، manager، inspector، ndt، corrosion، rbi، hse، asset (گذرواژه در README)</p></form>`;
    $("#lf").onsubmit = guard(async e => { e.preventDefault(); const f = new FormData(e.target);
      const r = await api("/api/auth/login", { method: "POST", body: { username: f.get("u"), password: f.get("p") } });
      S.token = r.access_token; S.user = r.user; localStorage.setItem("token", S.token); localStorage.setItem("user", JSON.stringify(S.user)); location.hash = "#/dashboard"; render(); });
    return;
  }
  $("#root").innerHTML = `<div id="app"><nav><h1>🛢️ یکپارچگی دارایی<br><small>بازرسی · خوردگی · ریسک</small></h1>${NAV.map(([k, t]) => `<a href="#/${k}" data-k="${k}">${t}</a>`).join("")}
    <div class="user">${esc(S.user.full_name)}<br><span class="muted" style="color:#9cc">${esc(S.user.role_fa)}</span><br><a id="lo" style="color:#fff">خروج</a></div></nav><main id="main"></main></div>`;
  $("#lo").onclick = logout;
  route();
}
async function route() {
  if (!S.token) return;
  const [, k = "dashboard", ...rest] = location.hash.replace("#", "").split("/");
  document.querySelectorAll("nav a[data-k]").forEach(a => a.classList.toggle("active", a.dataset.k === k || (k === "eq" && a.dataset.k === "equipment")));
  const m = $("#main"); m.innerHTML = "<p class='muted'>در حال بارگذاری…</p>";
  try { await (PAGES[k] || PAGES.dashboard)(m, ...rest); } catch (e) { m.innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}
window.addEventListener("hashchange", route);

/* ------------------------------------------------------------------- pages */
const PAGES = {};
PAGES.dashboard = async m => {
  const d = await api("/api/dashboard"), k = d.kpi;
  const lvC = { High: "#b3122b", Medium: "#e0a100", Low: "#2e9d57" };
  m.innerHTML = `<h2>داشبورد مدیریتی</h2>
  <div class="grid g4">${[["تجهیزات", k.total, ""], ["فعال", k.active, ""], ["میانگین شاخص سلامت", k.avg_health, ""], ["عمر باقیمانده < ۵ سال", k.life_lt5, "warn"], ["عمر باقیمانده < ۲ سال", k.life_lt2, "bad"],
    ["بازرسی معوق", k.overdue_plans, "bad"], ["عیوب منتظر تأیید", k.pending_review, "warn"], ["هشدار باز", k.open_alerts, "bad"]].map(([l, v, c]) => `<div class="card kpi ${c}"><div class="v">${nf(v, 2)}</div><div class="l">${l}</div></div>`).join("")}</div>
  <div class="grid g2" style="margin-top:1rem">
    <div class="card"><h3>توزیع سطح ریسک</h3><div class="row">${donut(d.risk_levels.map(x => ({ label: LV[x.level], n: x.n })), d.risk_levels.map(x => lvC[x.level]))}<div>${d.risk_levels.map(x => `<div>${lvBadge(x.level)} ${nf(x.n, 0)}</div>`).join("")}</div></div></div>
    <div class="card"><h3>وضعیت سلامت</h3>${hbars(d.health, "status", "n")}</div>
    <div class="card"><h3>برنامه بازرسی ۱۲ ماه آینده</h3>${lineChart({ series: [{ pts: d.plans_by_month.map(x => [new Date(x.month + "-15").getTime(), x.n]), color: "#1479a3", dots: true }, { pts: d.plans_by_month.map(x => [new Date(x.month + "-15").getTime(), x.p1]), color: "#b3122b", dots: true }], h: 220 })}<small class="muted">آبی: همه · قرمز: اولویت P1</small></div>
    <div class="card"><h3>عیوب شناسایی‌شده</h3>${hbars(d.defects, "defect_type", "n", "#e4572e")}</div>
    <div class="card"><h3>۱۰ تجهیز پرریسک</h3>${table(["تگ", "نوع", "ریسک", "سطح", "عمر (سال)"], d.top_risk.map(r => ({ id: r.equipment_id, cells: [esc(r.tag), esc(r.equipment_type), nf(r.risk_score, 0), lvBadge(r.risk_level), nf(r.remaining_life_years, 1)] })), { click: 1, attr: r => `onclick="location.hash='#/eq/${r.id}'"` })}</div>
    <div class="card"><h3>هشدارهای باز</h3>${d.alerts.map(a => `<div style="margin:.4rem 0">${badge(a.severity, a.severity === "critical" ? "بحرانی" : "بالا")} <a href="#/eq/${a.equipment_id}">${esc(a.message)}</a> ${can("recompute") ? `<a onclick="ack(${a.alert_id})" title="تأیید">✔</a>` : ""}</div>`).join("") || "<p class='muted'>هشداری نیست</p>"}</div>
  </div>`;
};
window.ack = guard(async id => { await api(`/api/alerts/${id}/ack`, { method: "POST" }); toast("هشدار تأیید شد"); route(); });

let eqState = { page: 1, q: "", type: "", status: "", risk_level: "", sort: "risk" };
PAGES.equipment = async m => {
  const f = await api("/api/equipment/facets");
  const load = async () => {
    const qs = new URLSearchParams({ page: eqState.page, page_size: 20, sort: eqState.sort, ...Object.fromEntries(["q", "type", "status", "risk_level"].filter(k => eqState[k]).map(k => [k, eqState[k]])) });
    const r = await api("/api/equipment?" + qs);
    $("#eqt").innerHTML = table(["تگ", "نوع", "جنس", "سیال", "واحد", "وضعیت", "ریسک", "سلامت", "عمر باقیمانده"], r.items.map(e => ({ id: e.equipment_id,
      cells: [`<b>${esc(e.tag)}</b>`, esc(e.equipment_type), esc(e.material), esc(e.fluid), esc(e.location), esc(e.status), e.risk_level ? `${nf(e.risk_score, 0)} ${lvBadge(e.risk_level)}` : "—", e.health_status ? badge(e.health_status) : "—", nf(e.remaining_life_years, 1)] })),
      { click: 1, attr: r => `onclick="location.hash='#/eq/${r.id}'"` });
    const pages = Math.ceil(r.total / 20);
    $("#eqp").innerHTML = `${nf(r.total, 0)} تجهیز · صفحه ${nf(r.page, 0)} از ${nf(pages, 0)} <button class="sec" ${r.page <= 1 ? "disabled" : ""} id="pv">قبلی</button> <button class="sec" ${r.page >= pages ? "disabled" : ""} id="nx">بعدی</button>`;
    $("#pv").onclick = () => { eqState.page--; load(); }; $("#nx").onclick = () => { eqState.page++; load(); };
  };
  const sel = (id, l, opts, cur) => `<label>${l}<select id="${id}"><option value="">همه</option>${opts.map(o => `<option ${o === cur ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>`;
  m.innerHTML = `<h2>تجهیزات</h2><div class="row"><label>جستجو<input id="q" value="${esc(eqState.q)}" placeholder="تگ، سیال، جنس…"></label>${sel("type", "نوع", f.equipment_type, eqState.type)}${sel("status", "وضعیت", f.status, eqState.status)}
    <label>سطح ریسک<select id="risk_level"><option value="">همه</option>${["High", "Medium", "Low"].map(l => `<option value="${l}" ${l === eqState.risk_level ? "selected" : ""}>${LV[l]}</option>`).join("")}</select></label>
    <label>مرتب‌سازی<select id="sort">${[["risk", "ریسک"], ["life", "عمر باقیمانده"], ["health", "سلامت"], ["tag", "تگ"]].map(([v, t]) => `<option value="${v}" ${v === eqState.sort ? "selected" : ""}>${t}</option>`).join("")}</select></label><span class="sp"></span>
    ${can("eq") ? `<button id="newEq">+ تجهیز جدید</button>` : ""}</div><div class="card"><div id="eqt"></div><div id="eqp" class="row" style="margin-top:.6rem"></div></div>`;
  ["type", "status", "risk_level", "sort"].forEach(k => $("#" + k).onchange = e => { eqState[k] = e.target.value; eqState.page = 1; load(); });
  let t; $("#q").oninput = e => { clearTimeout(t); t = setTimeout(() => { eqState.q = e.target.value; eqState.page = 1; load(); }, 300); };
  if ($("#newEq")) $("#newEq").onclick = () => newEquipmentDialog(f);
  await load();
};
function newEquipmentDialog(f) {
  const v = prompt("تگ، نوع، جنس، سیال، تاریخ نصب(YYYY-MM-DD)، فشار، دما، ضخامت اسمی، حداقل مجاز، بحرانیت(1-5) را با ویرگول وارد کنید\nمثال: VE-900,Vessel,Carbon Steel A516,Water,2018-05-01,12,120,14,8,3");
  if (!v) return; const a = v.split(",").map(x => x.trim());
  api("/api/equipment", { method: "POST", body: { tag: a[0], equipment_type: a[1], material: a[2], fluid: a[3], install_date: a[4], design_pressure_bar: +a[5], design_temp_c: +a[6], nominal_thickness_mm: +a[7], min_required_thickness_mm: +a[8], criticality: +a[9] } })
    .then(r => { toast("ثبت شد: " + r.equipment_id); location.hash = "#/eq/" + r.equipment_id; }).catch(e => toast(e.message, true));
}

PAGES.eq = async (m, id, tab = "overview") => {
  const [d, th, pr] = await Promise.all([api(`/api/equipment/${id}`), api(`/api/equipment/${id}/thickness`), api(`/api/predictions/corrosion/${id}`).catch(() => null)]);
  const e = d.equipment, r = d.risk, p = d.plan;
  const tabs = [["overview", "نمای کلی"], ["thickness", "ضخامت و پیش‌بینی"], ["inspections", "بازرسی‌ها"], ["ndt", "عیوب NDT"], ["plan", "برنامه و What-If"], ["images", "تصاویر"]];
  m.innerHTML = `<div class="row"><h2 style="margin:0">${esc(e.tag)} <small class="muted">${esc(e.equipment_id)}</small></h2><span class="sp"></span>
    <button class="sec" onclick="dl('/api/reports/${id}?format=html','r.html')">گزارش HTML</button><button class="sec" onclick="dl('/api/reports/${id}?format=pdf','report-${id}.pdf')">PDF</button><button class="sec" onclick="dl('/api/reports/${id}?format=xlsx','report-${id}.xlsx')">Excel</button></div>
  <div class="grid g4">${r ? [["امتیاز ریسک", `${nf(r.risk_score, 0)} ${lvBadge(r.risk_level)}`], ["شاخص سلامت", `${nf(r.health_index)} ${badge(r.health_status)}`], ["عمر باقیمانده", `${nf(r.remaining_life_years, 1)} سال<br><small class="muted">${nf(r.rl_low, 1)}–${nf(r.rl_high, 1)}</small>`], ["نرخ خوردگی", `${nf(r.corrosion_rate_mm_per_year, 3)} mm/y<br><small class="muted">${esc(r.trend)}</small>`]].map(([l, v]) => `<div class="card kpi"><div class="l">${l}</div><div class="v" style="font-size:20px">${v}</div></div>`).join("") : "<p class='muted'>ارزیابی موجود نیست</p>"}</div>
  ${d.alerts.map(a => `<p class="err">⚠ ${esc(a.message)}</p>`).join("")}
  <div class="tabs" style="margin-top:1rem">${tabs.map(([k, t]) => `<a class="${k === tab ? "on" : ""}" href="#/eq/${id}/${k}">${t}</a>`).join("")}</div><div id="tab"></div>`;
  const T = $("#tab");
  if (tab === "overview") T.innerHTML = `<div class="grid g2"><div class="card"><h3>مشخصات</h3><dl class="kv">${[["نوع", e.equipment_type], ["جنس", e.material], ["سیال", e.fluid], ["واحد", e.location], ["تاریخ نصب", jd(e.install_date)], ["فشار طراحی", e.design_pressure_bar + " bar"], ["دمای طراحی", e.design_temp_c + " °C"], ["ضخامت اسمی", e.nominal_thickness_mm + " mm"], ["حداقل مجاز", e.min_required_thickness_mm + " mm"], ["بحرانیت", e.criticality], ["وضعیت", e.status]].map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl></div>
    <div class="card"><h3>خلاصه پرونده</h3><dl class="kv"><dt>تعداد بازرسی</dt><dd>${nf(d.summary.inspection_count, 0)}</dd><dt>رکوردهای NDT</dt><dd>${nf(d.summary.ndt_count, 0)}</dd><dt>عیوب باز</dt><dd>${nf(d.summary.open_defects, 0)}</dd>
    ${r ? `<dt>P(بحرانی) ۱/۳/۵ سال</dt><dd>${pct(r.p_critical_1y)} / ${pct(r.p_critical_3y)} / ${pct(r.p_critical_5y)}</dd><dt>احتمال خرابی / پیامد</dt><dd>${nf(r.pof_score)} / ${nf(r.cof_score)}</dd>` : ""}</dl>
    ${p ? `<h3 style="margin-top:1rem">برنامه بازرسی</h3><p>${badge(p.priority)} ${jd(p.recommended_date)} · ${esc(p.recommended_method)} · ${esc(p.standard)} ${p.overdue ? badge("Reject", "معوق") : ""}</p><p class="muted">${esc(p.rationale)}</p>` : ""}</div></div>`;
  if (tab === "thickness") {
    const t = x => new Date(x).getTime();
    T.innerHTML = `<div class="card"><h3>روند ضخامت و پیش‌بینی ۵ ساله (بازه اطمینان ۹۰٪)</h3>${pr ? lineChart({ series: [{ pts: th.series.map(s => [t(s.date), s.min_mm]), color: "#0b4f6c", dots: true }, { pts: th.series.map(s => [t(s.date), s.mean_mm]), color: "#2e9d57", dash: 1 }, { pts: pr.forecast.map(f => [t(f.date), f.thickness_mm]), color: "#1479a3", dash: 1 }],
      band: pr.forecast.map(f => [t(f.date), f.lower, f.upper]), hline: { y: e.min_required_thickness_mm, label: "حداقل مجاز" }, yLabel: "mm" }) : ""}
      <small class="muted">آبی تیره: کمینه ضخامت · سبز: میانگین · خط‌چین آبی: پیش‌بینی</small>
      ${pr ? `<dl class="kv" style="margin-top:1rem"><dt>نرخ بلندمدت (LT)</dt><dd>${nf(pr.corrosion_rate_lt, 3)} mm/y</dd><dt>نرخ کوتاه‌مدت (ST)</dt><dd>${nf(pr.corrosion_rate_st, 3)} mm/y</dd><dt>نرخ حاکم</dt><dd>${nf(pr.corrosion_rate, 3)} mm/y</dd><dt>تاریخ رسیدن به حد مجاز</dt><dd>${jd(pr.critical_date)}</dd></dl>` : ""}</div>`;
  }
  if (tab === "inspections") {
    T.innerHTML = `<div class="card">${table(["شناسه", "تاریخ", "نوع", "روش", "بازرس", "کمینه ضخامت", "مقایسه"], d.inspections.map(i => ({ cells: [i.inspection_id, jd(i.inspection_date), esc(i.inspection_type), esc(i.method), esc(i.inspector), nf(i.min_thickness_mm), `<input type="checkbox" class="cmp" value="${i.inspection_id}">`] })))}
      <div class="row" style="margin-top:.6rem"><button id="cmpb">مقایسه دو بازرسی انتخابی</button></div><div id="cmpr"></div></div>`;
    $("#cmpb").onclick = guard(async () => { const v = [...document.querySelectorAll(".cmp:checked")].map(x => x.value); if (v.length !== 2) return toast("دقیقاً دو بازرسی انتخاب کنید", true);
      const c = await api(`/api/equipment/${id}/compare?a=${v[0]}&b=${v[1]}`);
      $("#cmpr").innerHTML = `<p>فاصله زمانی ${nf(c.years_between)} سال · کمینه ${nf(c.a.min_mm)} → ${nf(c.b.min_mm)} mm · میانگین تغییر ${nf(c.mean_delta_mm)} mm · بدترین نقطه: ${esc(c.worst_point?.point_id)} (${nf(c.worst_point?.delta_mm)} mm)</p>` +
        table(["نقطه", "A", "B", "تغییر", "نرخ (mm/y)"], c.points.map(p => ({ cells: [p.point_id, nf(p.a), nf(p.b), `<span class="${p.delta_mm < -0.5 ? "err" : ""}">${nf(p.delta_mm)}</span>`, nf(p.rate_mm_per_year, 3)] }))); });
  }
  if (tab === "ndt") T.innerHTML = `<div class="card">${table(["شناسه", "تاریخ", "روش", "عیب", "نتیجه", "اطمینان", "اولویت", "وضعیت", ""], d.ndt_records.map(n => ({ cells: [n.ndt_id, jd(n.date), n.method, n.defect_type, badge(n.result), nf(n.confidence), nf(n.priority_score, 0), badge(n.review_status), n.signal_file ? `<a href="#/ndt/${n.ndt_id}">تحلیل</a>` : ""] })))}</div>`;
  if (tab === "plan") {
    T.innerHTML = `<div class="card"><h3>تحلیل What-If</h3><div class="row"><label>ضریب نرخ خوردگی<input id="wm" type="number" step="0.1" value="1.5"></label><label>تغییر دما (°C)<input id="wt" type="number" value="30"></label><label>تغییر فشار (bar)<input id="wp" type="number" value="0"></label>
      <label>تأخیر بازرسی (ماه)<input id="wd" type="number" value="6"></label><button id="wb">محاسبه</button></div><div id="wr"></div></div>`;
    $("#wb").onclick = guard(async () => { const r = await api("/api/risk/what-if", { method: "POST", body: { equipment_id: id, scenarios: [{ name: "سناریوی کاربر", rate_multiplier: +$("#wm").value, temp_delta: +$("#wt").value, pressure_delta: +$("#wp").value, inspection_delay_months: +$("#wd").value }] } });
      $("#wr").innerHTML = table(["سناریو", "ریسک", "سطح", "عمر باقیمانده", "نرخ", "P(۵ساله)", "بازرسی بعدی", "Δ ریسک"], r.results.map(x => ({ cells: [esc(x.name), nf(x.risk_score, 1), lvBadge(x.risk_level), nf(x.remaining_life_years, 1), nf(x.corrosion_rate_mm_per_year, 3), pct(x.p_critical_5y), jd(x.plan.recommended_date), x.delta_risk == null ? "—" : nf(x.delta_risk, 1)] }))); });
  }
  if (tab === "images") { T.innerHTML = `<div class="card"><div class="row" id="imgs">${d.images.map(i => `<figure style="margin:0"><img data-id="${i.image_id}" width="120" height="120" alt=""><figcaption class="muted">${i.label}</figcaption></figure>`).join("") || "<p class='muted'>تصویری ثبت نشده</p>"}</div></div>`;
    document.querySelectorAll("#imgs img").forEach(async im => { const r = await api("/api/images/" + im.dataset.id, { raw: true }); if (r.ok) im.src = URL.createObjectURL(await r.blob()); }); }
};

/* NDT */
PAGES.ndt = async (m, ndtId) => {
  const [q, card] = await Promise.all([api("/api/ndt/queue?limit=25"), api("/api/ndt/model-card")]);
  m.innerHTML = `<h2>تحلیل هوشمند داده‌های بازرسی (M1)</h2><div class="grid g2">
  <div class="card"><h3>تحلیل سیگنال PAUT / ToFD</h3><div class="row"><label>فایل سیگنال (.npy/.csv/.json)<input type="file" id="sf"></label><label>شناسه تجهیز (برای ذخیره)<input id="seq" placeholder="EQ-000001"></label>
    <label>ضخامت جداره (mm)<input id="swt" type="number" value="30" style="width:90px"></label></div><div class="row"><button id="sb" ${can("ndt") ? "" : "disabled"}>تحلیل</button><label style="flex-direction:row;align-items:center;gap:.4rem"><input type="checkbox" id="ssave"> ذخیره به‌عنوان رکورد NDT</label></div><div id="sr"></div></div>
  <div class="card"><h3>تحلیل تصویر بازرسی</h3><div class="row"><input type="file" id="imf" accept="image/*"><button id="ib" ${can("ndt") ? "" : "disabled"}>تحلیل تصویر</button></div><div id="ir"></div>
    <h3 style="margin-top:1rem">کارت مدل</h3><p class="muted" style="font-size:12px">${esc(card.model)}<br>تشخیص عیب: Precision ${nf(card.detection.precision, 3)} · Recall ${nf(card.detection.recall, 3)}<br>طبقه‌بندی (میانگین): Precision ${nf(card.macro_precision, 3)} · Recall ${nf(card.macro_recall, 3)} (هدف ≥ ۰٫۸۵ / ۰٫۸۰)</p></div></div>
  <div class="card" style="margin-top:1rem"><h3>صف بررسی کارشناس — مرتب‌شده بر اساس اولویت (${nf(q.total_pending, 0)} مورد در انتظار)</h3>${table(["اولویت", "شناسه", "تجهیز", "عیب", "نتیجه", "اطمینان", "سیگنال", "اقدام"], q.items.map(n => ({ cells: [`${badge(n.priority_level)} ${nf(n.priority_score, 0)}`, n.ndt_id, `<a href="#/eq/${n.equipment_id}">${esc(n.tag)}</a>`, `${esc(n.defect_type_fa)}`, badge(n.result), nf(n.confidence), n.signal_file ? `<a href="#/ndt/${n.ndt_id}">نمایش</a>` : "—",
    can("ndt") ? `<a onclick="rv('${n.ndt_id}','approve')">✔ تأیید</a> · <a onclick="rv('${n.ndt_id}','reject')" class="err">✖ رد</a>` : ""] })))}</div>`;
  const show = a => `<p>${badge(a.priority_level)} <b>${esc(a.defect_type_fa)}</b> (${esc(a.defect_type)}) · اطمینان ${pct(a.confidence)} · SNR ${nf(a.snr, 1)} · اولویت ${nf(a.priority_score, 0)} · نتیجه پیشنهادی ${badge(a.suggested_result)}</p>
    <p class="muted">اندازه ${nf(a.defect_size_mm)} · عمق ${nf(a.defect_depth_mm)} · طول ${nf(a.defect_length_mm)} mm · زمان تحلیل ${nf(a.elapsed_s, 2)} ثانیه ${a.ndt_id ? `· ذخیره شد: ${a.ndt_id}` : ""}</p>` +
    lineChart({ series: [{ pts: a.trace.x.map((x, i) => [x * 1000, a.trace.raw[i]]), color: "#9aa7b5" }, { pts: a.trace.x.map((x, i) => [x * 1000, a.trace.filtered[i]]), color: "#b3122b" }], w: 560, h: 220, xdate: false }) +
    `<small class="muted">خاکستری: خام · قرمز: پس از نویززدایی — خروجی پیشنهادی است و نیازمند تأیید کارشناس.</small>`;
  $("#sb").onclick = guard(async () => { const f = $("#sf").files[0]; if (!f) return toast("فایل را انتخاب کنید", true); const fd = new FormData(); fd.append("file", f); fd.append("wall_thickness_mm", $("#swt").value);
    if ($("#ssave").checked) { fd.append("save", "true"); fd.append("equipment_id", $("#seq").value); } $("#sb").disabled = true;
    try { $("#sr").innerHTML = show(await api("/api/ndt/analyze", { method: "POST", body: fd })); } finally { $("#sb").disabled = false; } });
  $("#ib").onclick = guard(async () => { const f = $("#imf").files[0]; if (!f) return toast("تصویر را انتخاب کنید", true); const fd = new FormData(); fd.append("file", f);
    const r = await api("/api/ndt/analyze-image", { method: "POST", body: fd }); $("#ir").innerHTML = `<p>${badge(r.label === "defect" ? "Reject" : "Accept", r.label_fa)} اطمینان ${pct(r.confidence)} · مساحت روشن ${nf(r.bright_area_px, 0)} px ${r.bbox ? "· کادر " + r.bbox.join(",") : ""}</p>`; });
  if (ndtId) { const r = await api("/api/ndt/" + ndtId); if (r.analysis) { r.analysis.elapsed_s = 0; $("#sr").innerHTML = `<p><b>${esc(r.ndt_id)}</b> — ${esc(r.tag)}</p>` + show(r.analysis); } }
};
window.rv = guard(async (id, decision) => { const c = prompt(decision === "approve" ? "توضیح تأیید (اختیاری)" : "دلیل رد (اختیاری)") ?? ""; await api(`/api/ndt/${id}/review`, { method: "POST", body: { decision, comment: c } }); toast("ثبت شد"); route(); });

/* خوردگی */
PAGES.corrosion = async (m, id) => {
  const metrics = await api("/api/predictions/metrics");
  const top = await api("/api/risk/ranking?limit=30");
  m.innerHTML = `<h2>پیش‌بینی خوردگی و سلامت تجهیز (M2)</h2><div class="card"><div class="row"><label>تجهیز<select id="ce">${top.items.map(i => `<option value="${i.equipment_id}" ${i.equipment_id === id ? "selected" : ""}>${esc(i.tag)} — ${esc(i.equipment_id)}</option>`).join("")}</select></label>
    <label>افق (سال)<input id="ch" type="number" min="1" max="15" value="5" style="width:80px"></label><label>ضریب نرخ<input id="cm" type="number" step="0.1" value="1" style="width:80px"></label><button id="cb">پیش‌بینی</button></div><div id="cr"></div></div>
    <div class="card" style="margin-top:1rem"><h3>اعتبارسنجی مدل (بک‌تست روی آخرین اندازه‌گیری)</h3><p>نمونه: ${nf(metrics.n, 0)} تجهیز · MAE = <b class="${metrics.meets_target ? "ok" : "err"}">${nf(metrics.mae_mm, 3)} mm</b> (هدف ≤ ۰٫۵) · میانه ${nf(metrics.median_ae_mm, 3)} · صدک ۹۰ ${nf(metrics.p90_ae_mm, 3)}</p></div>`;
  const run = guard(async () => { const e = $("#ce").value; const p = await api(`/api/predictions/corrosion/${e}?horizon_years=${$("#ch").value}&rate_multiplier=${$("#cm").value}`); const t = x => new Date(x).getTime();
    $("#cr").innerHTML = lineChart({ series: [{ pts: p.history.map(h => [t(h.date), h.min_mm]), color: "#0b4f6c", dots: true }, { pts: p.forecast.map(f => [t(f.date), f.thickness_mm]), color: "#1479a3", dash: 1 }], band: p.forecast.map(f => [t(f.date), f.lower, f.upper]), hline: { y: p.min_required_thickness_mm, label: "حداقل مجاز" } }) +
      `<div class="grid g4"><div class="card kpi"><div class="l">عمر باقیمانده</div><div class="v">${nf(p.remaining_life_years, 1)}</div><small>${nf(p.rl_low, 1)}–${nf(p.rl_high, 1)} سال</small></div><div class="card kpi"><div class="l">شاخص سلامت</div><div class="v">${nf(p.health_index)}</div>${badge(p.health_status)}</div>
      <div class="card kpi"><div class="l">نرخ حاکم</div><div class="v">${nf(p.corrosion_rate, 3)}</div><small>LT ${nf(p.corrosion_rate_lt, 3)} · ST ${nf(p.corrosion_rate_st, 3)}</small></div><div class="card kpi ${p.p_critical_5y > .5 ? "bad" : ""}"><div class="l">P(بحرانی) ۱/۳/۵ ساله</div><div class="v" style="font-size:18px">${pct(p.p_critical_1y)} / ${pct(p.p_critical_3y)} / ${pct(p.p_critical_5y)}</div></div></div>`; });
  $("#cb").onclick = run; $("#ce").onchange = run; run();
};

/* ریسک */
PAGES.risk = async m => {
  const [hm, rk] = await Promise.all([api("/api/risk/heatmap"), api("/api/risk/ranking?limit=40")]);
  const col = (p, c) => { const s = p * c; return s >= 16 ? "#b3122b" : s >= 9 ? "#e4572e" : s >= 4 ? "#e0a100" : "#2e9d57"; };
  m.innerHTML = `<h2>ارزیابی ریسک (M3)</h2><div class="grid g2"><div class="card"><h3>نقشه حرارتی ریسک (احتمال × پیامد)</h3><div class="heat">${[5, 4, 3, 2, 1].map(p => `<div class="lab">${p}</div>` + [1, 2, 3, 4, 5].map(c => { const cell = hm.grid[p - 1][c - 1]; return `<div style="background:${col(p, c)};opacity:${cell.count ? 1 : .25}" data-p="${p}" data-c="${c}" title="${cell.equipment.map(e => e.tag).join("، ")}">${cell.count || ""}</div>`; }).join("")).join("")}
    <div class="lab"></div>${[1, 2, 3, 4, 5].map(c => `<div class="lab">${c}</div>`).join("")}</div><p class="muted">محور عمودی: احتمال خرابی · افقی: پیامد</p><div id="hc"></div></div>
    <div class="card"><h3>What-If</h3><div class="row"><label>تجهیز<select id="we">${rk.items.map(i => `<option value="${i.equipment_id}">${esc(i.tag)}</option>`).join("")}</select></label></div>
    <div class="row"><label>نرخ ×<input id="a1" type="number" step=".1" value="1.5" style="width:70px"></label><label>Δدما<input id="a2" type="number" value="30" style="width:70px"></label><label>Δفشار<input id="a3" type="number" value="0" style="width:70px"></label><label>تأخیر (ماه)<input id="a4" type="number" value="6" style="width:70px"></label>
    <label>سیال<select id="a5"><option value="">بدون تغییر</option>${["Acid Gas", "Natural Gas", "Hydrocarbon", "Crude Oil", "Steam", "Water", "Cooling Water"].map(f => `<option>${f}</option>`).join("")}</select></label><button id="wb">مقایسه</button></div><div id="wr"></div></div></div>
    <div class="card" style="margin-top:1rem"><div class="row"><h3 style="margin:0">رتبه‌بندی تجهیزات بر اساس ریسک</h3><span class="sp"></span>${can("recompute") ? `<button class="sec" id="rc">محاسبه مجدد همه</button>` : ""}</div>
    ${table(["#", "تگ", "نوع", "سیال", "ریسک", "سطح", "P-cat", "C-cat", "عمر (سال)", "سلامت"], rk.items.map(r => ({ id: r.equipment_id, cells: [r.rank, `<b>${esc(r.tag)}</b>`, esc(r.equipment_type), esc(r.fluid), nf(r.risk_score, 1), lvBadge(r.risk_level), r.pof_category, r.cof_category, nf(r.remaining_life_years, 1), nf(r.health_index)] })), { click: 1, attr: r => `onclick="location.hash='#/eq/${r.id}'"` })}</div>`;
  document.querySelectorAll(".heat div[data-p]").forEach(d => d.onclick = () => { const c = hm.grid[d.dataset.p - 1][d.dataset.c - 1]; $("#hc").innerHTML = c.equipment.map(e => `<a href="#/eq/${e.equipment_id}">${esc(e.tag)}</a> (${nf(e.risk_score, 0)})`).join(" · ") || ""; });
  $("#wb").onclick = guard(async () => { const r = await api("/api/risk/what-if", { method: "POST", body: { equipment_id: $("#we").value, scenarios: [{ name: "سناریو", rate_multiplier: +$("#a1").value, temp_delta: +$("#a2").value, pressure_delta: +$("#a3").value, inspection_delay_months: +$("#a4").value, fluid: $("#a5").value || null }] } });
    $("#wr").innerHTML = table(["", "ریسک", "سطح", "عمر", "P(۵ساله)", "بازرسی بعدی"], r.results.map(x => ({ cells: [esc(x.name), nf(x.risk_score, 1) + (x.delta_risk != null ? ` (${x.delta_risk > 0 ? "+" : ""}${nf(x.delta_risk, 1)})` : ""), lvBadge(x.risk_level), nf(x.remaining_life_years, 1), pct(x.p_critical_5y), jd(x.plan.recommended_date)] }))); });
  if ($("#rc")) $("#rc").onclick = guard(async () => { $("#rc").disabled = true; const r = await api("/api/risk/recompute", { method: "POST" }); toast(`${r.assessed} تجهیز ارزیابی شد`); route(); });
};

PAGES.plans = async m => {
  const st = PAGES._pl = PAGES._pl || { priority: "", overdue: "", plan_status: "" };
  const r = await api("/api/plans?page_size=100" + Object.entries(st).filter(([, v]) => v !== "").map(([k, v]) => `&${k}=${v}`).join(""));
  m.innerHTML = `<h2>برنامه بازرسی مبتنی بر ریسک (RBI)</h2><p class="muted">پوشش: ${nf(r.plans_total, 0)} برنامه برای ${nf(r.active_equipment, 0)} تجهیز فعال/آماده. فاصله بازرسی = min(½ عمر باقیمانده، سقف سطح ریسک).</p>
  <div class="row"><label>اولویت<select id="fp"><option value="">همه</option>${["P1", "P2", "P3"].map(p => `<option ${st.priority === p ? "selected" : ""}>${p}</option>`).join("")}</select></label>
  <label>معوق<select id="fo"><option value="">همه</option><option value="true" ${st.overdue === "true" ? "selected" : ""}>فقط معوق</option></select></label>
  <label>وضعیت<select id="fs"><option value="">همه</option>${[["proposed", "پیشنهادی"], ["scheduled", "زمان‌بندی‌شده"], ["done", "انجام‌شده"]].map(([v, t]) => `<option value="${v}" ${st.plan_status === v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
  ${r.by_priority.map(b => `<span>${badge(b.priority)} ${nf(b.n, 0)} (معوق ${nf(b.overdue, 0)})</span>`).join(" ")}</div>
  <div class="card">${table(["اولویت", "تگ", "نوع", "تاریخ پیشنهادی", "روش", "ریسک", "عمر", "مبنا", "وضعیت", ""], r.items.map(p => ({ cells: [badge(p.priority), `<a href="#/eq/${p.equipment_id}">${esc(p.tag)}</a>`, esc(p.equipment_type), jd(p.recommended_date) + (p.overdue ? ` ${badge("Reject", "معوق")}` : ""), esc(p.recommended_method), nf(p.risk_score, 0), nf(p.remaining_life_years, 1), esc(p.standard), esc(p.plan_status),
    can("plan") && p.plan_status === "proposed" ? `<a onclick="sch('${p.equipment_id}','scheduled')">زمان‌بندی</a>` : can("plan") && p.plan_status === "scheduled" ? `<a onclick="sch('${p.equipment_id}','done')">انجام شد</a>` : ""] })))}</div>`;
  [["fp", "priority"], ["fo", "overdue"], ["fs", "plan_status"]].forEach(([id, k]) => $("#" + id).onchange = e => { st[k] = e.target.value; route(); });
};
window.sch = guard(async (id, s) => { await api("/api/plans/" + id, { method: "PATCH", body: { plan_status: s } }); toast("به‌روز شد"); route(); });

PAGES.inspections = async m => {
  const r = await api("/api/inspections?page_size=15");
  m.innerHTML = `<h2>ثبت بازرسی و ورود داده</h2><div class="grid g2"><div class="card"><h3>ثبت بازرسی جدید با ضخامت‌سنجی</h3>
  <div class="row"><label>شناسه تجهیز<input id="ie" placeholder="EQ-000001"></label><label>تاریخ<input id="id" type="date"></label><label>روش<select id="im"><option>UT</option><option>PAUT</option><option>ToFD</option><option>VT</option><option>RT</option></select></label></div>
  <label>نقاط ضخامت (هر خط: شناسه نقطه، ضخامت mm)<textarea id="it" rows="6" placeholder="P-001, 11.2&#10;P-002, 11.4"></textarea></label><div class="row" style="margin-top:.6rem"><button id="ib" ${can("inspect") ? "" : "disabled"}>ثبت و محاسبه مجدد ریسک</button></div><div id="ir"></div></div>
  <div class="card"><h3>ورود فایل (CSV / Excel / JSON)</h3><p class="muted">ستون‌های الزامی: تجهیزات: tag, equipment_type, material, fluid, install_date, nominal_thickness_mm, min_required_thickness_mm — بازرسی‌ها: equipment_id, inspection_date — ضخامت: equipment_id, inspection_id, point_id, measurement_date, thickness_mm — NDT: equipment_id, method, date, defect_type</p>
  <div class="row"><select id="ik"><option value="equipment">تجهیزات</option><option value="inspections">بازرسی‌ها</option><option value="thickness">ضخامت‌سنجی</option><option value="ndt">NDT</option></select><input type="file" id="if"><button id="iu">بارگذاری</button></div><div id="iur"></div></div></div>
  <div class="card" style="margin-top:1rem"><h3>آخرین بازرسی‌ها</h3>${table(["شناسه", "تجهیز", "تاریخ", "نوع", "روش", "بازرس"], r.items.map(i => ({ cells: [i.inspection_id, `<a href="#/eq/${i.equipment_id}">${esc(i.tag)}</a>`, jd(i.inspection_date), esc(i.inspection_type), esc(i.method), esc(i.inspector)] })))}</div>`;
  $("#id").value = new Date().toISOString().slice(0, 10);
  $("#ib").onclick = guard(async () => { const th = $("#it").value.split("\n").map(l => l.split(/[,،\t]/).map(x => x.trim())).filter(a => a.length >= 2 && a[0]).map(a => ({ point_id: a[0], thickness_mm: +a[1] }));
    const r = await api("/api/inspections", { method: "POST", body: { equipment_id: $("#ie").value.trim(), inspection_date: $("#id").value, method: $("#im").value, thickness: th } });
    $("#ir").innerHTML = `<p class="ok">ثبت شد: ${r.inspection_id}</p>${r.warnings.map(w => `<p class="err">⚠ ${esc(w)}</p>`).join("")}<p>ریسک جدید: ${nf(r.risk.risk_score, 1)} ${lvBadge(r.risk.risk_level)} · عمر باقیمانده ${nf(r.risk.remaining_life_years, 1)} سال</p>`; });
  $("#iu").onclick = guard(async () => { const f = $("#if").files[0]; if (!f) return toast("فایل را انتخاب کنید", true); const fd = new FormData(); fd.append("file", f);
    const r = await api("/api/import/" + $("#ik").value, { method: "POST", body: fd });
    $("#iur").innerHTML = `<p>${nf(r.accepted, 0)} از ${nf(r.total, 0)} رکورد پذیرفته شد (${pct(r.accept_rate)}) ${r.meets_95pct ? '<span class="ok">✔ ≥ ۹۵٪</span>' : '<span class="err">✖ &lt; ۹۵٪</span>'}</p>` + r.errors.slice(0, 10).map(e => `<div class="err">سطر ${e.row}: ${esc(e.error)}</div>`).join(""); });
};

PAGES.assistant = async m => {
  const ex = await api("/api/assistant/examples");
  m.innerHTML = `<h2>دستیار هوشمند بازرسی</h2><div class="card"><div class="chat" id="ch"><div class="msg a">سلام! از داده‌های ثبت‌شده در سامانه می‌پرسید؛ پاسخ‌ها مبتنی بر داده و دارای منبع هستند.</div></div>
  <div class="row" style="margin-top:.6rem"><input id="aq" style="flex:1" placeholder="پرسش خود را بنویسید…"><button id="ab">ارسال</button></div><div class="row">${ex.map(e => `<a class="ex">${esc(e)}</a>`).join(" · ")}</div></div>`;
  const ask = guard(async t => { t = t || $("#aq").value.trim(); if (!t) return; $("#aq").value = ""; const c = $("#ch"); c.insertAdjacentHTML("beforeend", `<div class="msg u">${esc(t)}</div>`);
    const r = await api("/api/assistant/query", { method: "POST", body: { question: t } });
    c.insertAdjacentHTML("beforeend", `<div class="msg a">${esc(r.answer).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")}${r.table.rows.length ? table(r.table.columns, r.table.rows.map(x => ({ cells: x.map(v => typeof v === "number" ? nf(v, 2) : esc(v)) }))) : ""}<div class="muted" style="font-size:11px">منبع: ${r.sources.join("، ") || "—"} · ${nf(r.elapsed_s, 2)} ثانیه</div></div>`); c.scrollTop = c.scrollHeight; });
  $("#ab").onclick = () => ask(); $("#aq").onkeydown = e => e.key === "Enter" && ask(); document.querySelectorAll(".ex").forEach(a => a.onclick = () => ask(a.textContent));
};

PAGES.reports = async m => {
  m.innerHTML = `<h2>گزارش‌ها</h2><div class="grid g2"><div class="card"><h3>گزارش مدیریتی</h3><p class="muted">خلاصه وضعیت، ۲۰ تجهیز پرریسک، برنامه بازرسی و عیوب.</p><div class="row"><button onclick="dl('/api/reports/management?format=html','management.html')">HTML / چاپ</button><button class="sec" onclick="dl('/api/reports/management?format=pdf','management.pdf')">PDF</button><button class="sec" onclick="dl('/api/reports/management?format=xlsx','management.xlsx')">Excel</button></div></div>
  <div class="card"><h3>گزارش تجهیز / تحلیل NDT</h3><div class="row"><input id="rid" placeholder="EQ-000001 یا NDT-0000001"></div><div class="row"><button id="r1">HTML</button><button class="sec" id="r2">PDF</button><button class="sec" id="r3">Excel</button></div></div></div>`;
  [["r1", "html"], ["r2", "pdf"], ["r3", "xlsx"]].forEach(([b, f]) => $("#" + b).onclick = () => { const v = $("#rid").value.trim(); v ? dl(`/api/reports/${v}?format=${f}`, `report-${v}.${f}`) : toast("شناسه را وارد کنید", true); });
};

PAGES.admin = async m => {
  if (!can("audit")) { m.innerHTML = "<p class='err'>دسترسی ندارید</p>"; return; }
  const [a, v] = await Promise.all([api("/api/audit?limit=60"), api("/api/audit/verify")]);
  m.innerHTML = `<h2>ممیزی (Audit Trail)</h2><div class="card"><p>زنجیره هش: ${v.valid ? `<span class="ok">✔ سالم (${nf(v.checked, 0)} رکورد)</span>` : `<span class="err">✖ دستکاری شناسایی شد (رکورد ${v.broken_at_id})</span>`}</p>
  ${table(["#", "زمان", "کاربر", "اقدام", "موجودیت", "شناسه", "جزئیات"], a.map(x => ({ cells: [x.id, esc(x.ts.replace("T", " ").slice(0, 19)), esc(x.username), esc(x.action), esc(x.entity), esc(x.entity_id), `<span class="muted">${esc((x.detail || "").slice(0, 80))}</span>`] })))}</div>`;
};

render();
