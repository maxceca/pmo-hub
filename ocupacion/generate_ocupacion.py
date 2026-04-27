#!/usr/bin/env python3
"""
generate_ocupacion.py
Genera ocupacion/index.html a partir de archivos ICS (Office 365).
Usa solo stdlib Python: datetime, pathlib, re, os, json, collections.
"""

import re
import os
import json
import collections
from datetime import datetime, timedelta, date, timezone
from pathlib import Path

# ── Rutas ───────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
ICS_DIR   = Path(os.environ.get("ICS_DIR", REPO_ROOT / "ocupacion" / "calendars"))
OUTPUT    = REPO_ROOT / "ocupacion" / "index.html"

# ── Constantes ───────────────────────────────────────────────────────────────
CDMX_OFFSET      = timedelta(hours=-6)   # UTC-6
WORK_MIN_PER_DAY = 8 * 60               # 40h/semana = 8h/día = 480 min

# Días no laborables México 2026 + Jueves y Viernes Santo
HOLIDAYS: set[date] = {
    date(2026, 1,  1),   # Año Nuevo
    date(2026, 2,  2),   # Día de la Constitución (primer lunes de febrero)
    date(2026, 3, 16),   # Natalicio de Benito Juárez (tercer lunes de marzo)
    date(2026, 4,  2),   # Jueves Santo
    date(2026, 4,  3),   # Viernes Santo
    date(2026, 5,  1),   # Día del Trabajo
    date(2026, 9, 16),   # Día de la Independencia
    date(2026, 11,16),   # Revolución Mexicana (tercer lunes de noviembre)
    date(2026, 12,25),   # Navidad
}

# Palabras clave a excluir (insensible a mayúsculas y acentos)
EXCLUDE_KEYWORDS = ["personal", "comida", "medico", "médico",
                    "cita medica", "cita médica"]

# colores para Chart.js (uno por PM)
CHART_COLORS = [
    "rgba(30,39,97,0.85)",
    "rgba(151,215,0,0.85)",
    "rgba(220,38,38,0.85)",
    "rgba(217,119,6,0.85)",
    "rgba(59,130,246,0.85)",
    "rgba(139,92,246,0.85)",
]

# ── Helpers ICS ──────────────────────────────────────────────────────────────

def parse_dt(value: str) -> datetime | None:
    """Convierte DTSTART/DTEND a datetime UTC naive."""
    value = value.strip()
    # FORMAT: 20260101T143000Z
    if value.endswith("Z"):
        try:
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ")
        except ValueError:
            return None
    # FORMAT: 20260101T143000 (asumimos UTC-6 local si no hay Z)
    try:
        dt = datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
        # restar el offset para convertir a UTC equivalente naive
        return dt - CDMX_OFFSET  # si estaba en CDMX, convertimos a UTC naive
    except ValueError:
        pass
    # DATE only: 20260101
    try:
        return datetime.strptime(value[:8], "%Y%m%d")
    except ValueError:
        return None


def unfold_ics(raw: str) -> str:
    """Desdoblar líneas ICS (CRLF + espacio/tab = continuación)."""
    return re.sub(r"\r?\n[ \t]", "", raw)


def parse_ics(path: Path) -> list[dict]:
    """Retorna lista de eventos {start, end, busy_type} en hora CDMX."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = unfold_ics(raw)

    events = []
    in_event = False
    ev: dict = {}

    for line in raw.splitlines():
        if line == "BEGIN:VEVENT":
            in_event = True
            ev = {}
            continue
        if line == "END:VEVENT":
            if in_event and ev.get("start") and ev.get("end"):
                # ignorar TRANSP:TRANSPARENT
                if ev.get("transp", "OPAQUE") != "TRANSPARENT":
                    events.append(ev)
            in_event = False
            ev = {}
            continue
        if not in_event:
            continue

        # DTSTART (con o sin parámetros como ;TZID=...)
        m = re.match(r"DTSTART(?:;[^:]+)?:(.+)", line)
        if m:
            dt = parse_dt(m.group(1))
            if dt:
                ev["start"] = dt + CDMX_OFFSET  # UTC naive → CDMX naive
            continue

        m = re.match(r"DTEND(?:;[^:]+)?:(.+)", line)
        if m:
            dt = parse_dt(m.group(1))
            if dt:
                ev["end"] = dt + CDMX_OFFSET
            continue

        m = re.match(r"TRANSP:(.+)", line)
        if m:
            ev["transp"] = m.group(1).strip()
            continue

        m = re.match(r"X-MICROSOFT-CDO-BUSYSTATUS:(.+)", line)
        if m:
            ev["busy_type"] = m.group(1).strip()  # BUSY | TENTATIVE | FREE | OOF
            continue

        # SHOW-AS puede también indicar libre
        m = re.match(r"X-MICROSOFT-CDO-ALLDAYEVENT:(.+)", line)
        if m and m.group(1).strip() == "TRUE":
            ev["allday"] = True

        m = re.match(r"SUMMARY(?:;[^:]+)?:(.+)", line)
        if m:
            ev["summary"] = m.group(1).strip()

    return events


# ── Cálculo de ocupación ─────────────────────────────────────────────────────

def is_workday(d: date) -> bool:
    return d.weekday() < 5  # lun=0 … vie=4


def is_holiday(d: date) -> bool:
    return d in HOLIDAYS


def is_countable_day(d: date) -> bool:
    """Días en que se cuentan horas reales: lunes-viernes (incluyendo festivos si hubo trabajo)."""
    return is_workday(d)


def is_billable_day(d: date) -> bool:
    """Día laborable planeado: lunes-viernes y NO festivo (para el denominador)."""
    return is_workday(d) and not is_holiday(d)


def is_excluded(summary: str) -> bool:
    """True si el título del evento contiene una palabra clave a excluir."""
    s = summary.lower()
    return any(k in s for k in EXCLUDE_KEYWORDS)


def split_event_by_day(start: datetime, end: datetime):
    """Divide un evento multi-día en segmentos diarios."""
    segments = []
    cur = start
    while cur.date() < end.date():
        day_end = cur.replace(hour=23, minute=59, second=59)
        segments.append((cur, day_end))
        cur = (cur + timedelta(days=1)).replace(hour=0, minute=0, second=0)
    segments.append((cur, end))
    return segments


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Fusiona intervalos solapados (en minutos)."""
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def compute_daily_busy(events: list[dict]) -> dict:
    """
    Retorna dict: date → {total_min, busy_min, tent_min}
    - Cuenta TODAS las horas del evento sin restricción de horario.
    - Solo días laborables (lun-vie, no festivos).
    - Excluye eventos con palabras clave (personal, comida, médico...).
    - Fusiona intervalos solapados antes de sumar.
    """
    # usa minutos desde epoch-del-día para fusionar solapados
    def to_abs(dt: datetime) -> int:
        return dt.hour * 60 + dt.minute

    day_busy: dict[date, list[tuple[int, int]]] = collections.defaultdict(list)
    day_tent: dict[date, list[tuple[int, int]]] = collections.defaultdict(list)

    for ev in events:
        btype = ev.get("busy_type", "BUSY")
        if btype == "FREE":
            continue
        summary = ev.get("summary", "")
        if is_excluded(summary):
            continue
        segments = split_event_by_day(ev["start"], ev["end"])
        for seg_start, seg_end in segments:
            d = seg_start.date()
            if not is_countable_day(d):   # excluir fines de semana; festivos SÍ cuentan en numerador
                continue
            # minutos del segmento en ese día (sin clip de horario)
            s = to_abs(seg_start)
            e = to_abs(seg_end) if seg_start.date() == seg_end.date() else 24 * 60
            if e <= s:
                e = 24 * 60  # evento cruza medianoche: contar hasta fin de día
            if e <= s:
                continue
            if btype == "TENTATIVE":
                day_tent[d].append((s, e))
            else:
                day_busy[d].append((s, e))

    all_days = set(day_busy.keys()) | set(day_tent.keys())
    result = {}
    for d in all_days:
        all_intervals = day_busy[d] + day_tent[d]
        total_min = sum(e - s for s, e in merge_intervals(all_intervals))
        busy_only = sum(e - s for s, e in merge_intervals(day_busy[d]))
        tent_only = sum(e - s for s, e in merge_intervals(day_tent[d]))
        result[d] = {
            "total_min": total_min,
            "busy_min":  busy_only,
            "tent_min":  tent_only,
        }
    return result


# ── Agrupación por mes/semana ─────────────────────────────────────────────────

def week_of_month(d: date) -> int:
    """Semana dentro del mes (1-based)."""
    return (d.day - 1) // 7 + 1


def group_by_month(daily: dict) -> dict:
    """month_str → {total_min, busy_min, tent_min, work_days, avail_min, daily}"""
    months: dict[str, dict] = {}
    for d, vals in daily.items():
        if d.year < 2026:
            continue
        key = d.strftime("%Y-%m")
        if key not in months:
            yr, mo = int(key[:4]), int(key[5:])
            months[key] = {"total_min": 0, "busy_min": 0, "tent_min": 0,
                           "work_days": 0,
                           "avail_min": available_min_in_month(yr, mo),
                           "daily": {}}
        months[key]["total_min"] += vals["total_min"]
        months[key]["busy_min"]  += vals["busy_min"]
        months[key]["tent_min"]  += vals["tent_min"]
        months[key]["work_days"] += 1
        months[key]["daily"][d.isoformat()] = vals
    return months


def billable_days_in_month(year: int, month: int) -> int:
    """Días laborables del mes: lun-vie excluyendo festivos."""
    from calendar import monthrange
    _, days = monthrange(year, month)
    return sum(1 for d in range(1, days + 1)
               if is_billable_day(date(year, month, d)))


def available_min_in_month(year: int, month: int) -> int:
    """Minutos disponibles = días laborables × 480 (40h/semana = 8h/día)."""
    return billable_days_in_month(year, month) * WORK_MIN_PER_DAY


def pct(minutes: int, year: int, month: int) -> float:
    avail = available_min_in_month(year, month)
    if avail == 0:
        return 0.0
    return round(minutes / avail * 100, 1)


# ── Generación HTML ───────────────────────────────────────────────────────────

MONTH_ES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Ago",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}
MONTH_ES_FULL = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}
DAY_ABBR = ["L", "M", "M", "J", "V"]


def badge_class(p: float) -> str:
    if p > 100:
        return "badge-over"
    if p < 70:
        return "badge-green"
    if p <= 90:
        return "badge-amber"
    return "badge-red"


def bar_class(p: float) -> str:
    if p > 100:
        return "bar-over"
    if p < 70:
        return "bar-green"
    if p <= 90:
        return "bar-amber"
    return "bar-red"


def initials(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()


def fmt_fecha(dt: datetime) -> str:
    return (f"{dt.day} de {MONTH_ES_FULL[dt.month]} de {dt.year} · "
            f"{dt.hour:02d}:{dt.minute:02d} CDMX")


def build_weekly_breakdown(monthly_daily: dict, year: int, month: int) -> str:
    """Construye tabla semanal con días L M M J V coloreados."""
    from calendar import monthrange
    _, days_in_month = monthrange(year, month)

    # agrupar workdays por semana
    weeks: dict[int, list[date]] = collections.defaultdict(list)
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        if is_workday(d):
            weeks[week_of_month(d)].append(d)

    rows = []
    for wnum in sorted(weeks.keys()):
        wdays = weeks[wnum]
        first = wdays[0]
        last  = wdays[-1]
        label = f"Sem {wnum} ({first.day}–{last.day} {MONTH_ES[month]})"
        cells = ""
        for d in wdays:
            dvals = monthly_daily.get(d.isoformat(), {})
            dm = dvals.get("total_min", 0)
            dp = round(dm / WORK_MIN_PER_DAY * 100)
            holiday_mark = " 🎌" if is_holiday(d) else ""
            if dp > 100:
                cls = "dc-over"
            elif dp < 70:
                cls = "dc-green"
            elif dp <= 90:
                cls = "dc-amber"
            else:
                cls = "dc-red"
            tip = f"{DAY_ABBR[d.weekday()]} {d.day}{holiday_mark}: {dp}%"
            cells += (f'<div class="day-cell {cls}" title="{tip}">'
                      f'<span class="dc-abbr">{DAY_ABBR[d.weekday()]}</span>'
                      f'<span class="dc-val">{dp}%</span></div>')
        rows.append(f'<div class="week-row"><span class="week-label">{label}</span>'
                    f'<div class="day-cells">{cells}</div></div>')
    return "\n".join(rows)


def generate_html(pm_data: dict) -> str:
    """
    pm_data: { pm_name: { month_str: {total_min, busy_min, tent_min, work_days, daily} } }
    """
    now_cdmx = datetime.now() + CDMX_OFFSET
    fecha_gen = fmt_fecha(now_cdmx)

    # meses disponibles (unión de todos los PMs)
    all_months: list[str] = sorted({m for pd in pm_data.values() for m in pd.keys()})
    if not all_months:
        all_months = [now_cdmx.strftime("%Y-%m")]

    active_month = all_months[-1]
    ay, am = int(active_month[:4]), int(active_month[5:7])

    # período cubierto
    first_m = all_months[0]
    last_m  = all_months[-1]
    fy, fm  = int(first_m[:4]), int(first_m[5:7])
    ly, lm  = int(last_m[:4]), int(last_m[5:7])
    periodo = (f"{MONTH_ES[fm]} {fy}" if fy == ly
               else f"{MONTH_ES[fm]} {fy}")
    periodo += f" – {MONTH_ES[lm]} {ly}"

    # KPIs del mes activo
    pcts_active = {}
    for name, mdata in pm_data.items():
        if active_month in mdata:
            pcts_active[name] = pct(mdata[active_month]["total_min"], ay, am)
        else:
            pcts_active[name] = 0.0

    avg_pct = (round(sum(pcts_active.values()) / len(pcts_active), 1)
               if pcts_active else 0.0)
    max_pm  = max(pcts_active, key=pcts_active.get) if pcts_active else "—"
    min_pm  = min(pcts_active, key=pcts_active.get) if pcts_active else "—"

    # tabs de meses
    tabs_html = ""
    for m in all_months:
        my, mm_n = int(m[:4]), int(m[5:7])
        label = f"{MONTH_ES[mm_n]} {my}"
        active_cls = " active" if m == active_month else ""
        tabs_html += (f'<button class="mtab{active_cls}" '
                      f'onclick="showMonth(\'{m}\',this)">{label}</button>\n')

    # cards de PMs
    cards_html = ""
    for idx, (name, mdata) in enumerate(sorted(pm_data.items())):
        color = CHART_COLORS[idx % len(CHART_COLORS)]
        init  = initials(name)

        # datos por mes para JS
        pm_months_js = {}
        for m, vals in mdata.items():
            my, mm_n = int(m[:4]), int(m[5:7])
            p = pct(vals["total_min"], my, mm_n)
            pm_months_js[m] = {
                "pct":      p,
                "busy_min": vals["busy_min"],
                "tent_min": vals["tent_min"],
                "daily":    vals["daily"],
            }

        # weekly breakdown para cada mes (pre-renderizado)
        weekly_divs = ""
        for m, vals in mdata.items():
            my, mm_n = int(m[:4]), int(m[5:7])
            wb = build_weekly_breakdown(vals["daily"], my, mm_n)
            display = "block" if m == active_month else "none"
            weekly_divs += (f'<div class="weekly-breakdown" '
                            f'id="wb-{name.replace(" ","-")}-{m}" '
                            f'style="display:{display}">{wb}</div>\n')

        # valores del mes activo para renderizado inicial
        active_vals = pm_months_js.get(active_month, {"pct": 0, "busy_min": 0, "tent_min": 0})
        ap   = active_vals["pct"]
        bcls = badge_class(ap)
        brcls = bar_class(ap)

        cards_html += f"""
<div class="pm-card" data-pm="{name}" data-months='{json.dumps(pm_months_js, default=str)}'>
  <div class="pm-card-header">
    <div class="pm-avatar" style="background:{color.replace('0.85','1')}">{init}</div>
    <div class="pm-info">
      <div class="pm-name">{name}</div>
      <div class="pm-role">Project Manager</div>
    </div>
    <div class="pm-badge {bcls}" id="badge-{name.replace(' ','-')}">{ap}%</div>
  </div>
  <div class="pm-bar-wrap">
    <div class="pm-bar {brcls}" id="bar-{name.replace(' ','-')}"
         style="width:{min(ap,100)}%"></div>
  </div>
  <div class="pm-detail" id="detail-{name.replace(' ','-')}">
    <span class="detail-item">Confirmado: {active_vals['busy_min']} min</span>
    <span class="detail-item">Tentativo: {active_vals['tent_min']} min</span>
  </div>
  <div class="weekly-section">
    {weekly_divs}
  </div>
</div>
"""

    # Chart.js data
    pm_names = sorted(pm_data.keys())
    chart_labels = [f"{MONTH_ES[int(m[5:7])]} {m[:4]}" for m in all_months]
    datasets = []
    for idx, name in enumerate(pm_names):
        mdata = pm_data[name]
        values = []
        for m in all_months:
            if m in mdata:
                my, mm_n = int(m[:4]), int(m[5:7])
                values.append(pct(mdata[m]["total_min"], my, mm_n))
            else:
                values.append(None)
        color = CHART_COLORS[idx % len(CHART_COLORS)]
        border = color.replace("0.85", "1")
        datasets.append({
            "label":           name,
            "data":            values,
            "backgroundColor": color,
            "borderColor":     border,
            "borderWidth":     2,
            "borderRadius":    4,
        })

    chart_data_json = json.dumps({
        "labels":   chart_labels,
        "datasets": datasets,
    })

    # avg_pct badge
    avg_bcls = badge_class(avg_pct)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ocupación del Equipo · PMO Hub</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
/* === Censys PMO Hub - Nav compartido === */
.pmo-hub-nav{{display:flex;align-items:center;justify-content:space-between;
  padding:0 24px;height:52px;background:#1a1a2e;border-bottom:3px solid #97D700;
  position:sticky;top:0;z-index:9999;font-family:'Open Sans',sans-serif;
  box-sizing:border-box;}}
.pmo-nav-logo{{display:flex;align-items:center;gap:10px;text-decoration:none;}}
.pmo-nav-logo img{{height:30px;width:auto;}}
.pmo-nav-title-group{{display:flex;flex-direction:column;line-height:1.2;}}
.pmo-nav-title{{font-size:13px;font-weight:700;color:#fff;letter-spacing:.02em;}}
.pmo-nav-sub{{font-size:10px;color:#97D700;font-weight:600;letter-spacing:.04em;
  text-transform:uppercase;}}
.pmo-nav-links{{display:flex;gap:4px;}}
.pmo-nav-links a{{font-size:12px;color:rgba(255,255,255,.75);text-decoration:none;
  padding:5px 12px;border-radius:6px;font-weight:500;transition:all .15s;}}
.pmo-nav-links a:hover{{background:rgba(255,255,255,.1);color:#fff;}}
.pmo-nav-links a.active{{background:rgba(151,215,0,.2);color:#97D700;}}
@media(max-width:640px){{.pmo-nav-links{{display:none;}}}}
/* ══════════════════════════════════════════════════════ */

:root {{
  --navy: #1E2761; --navy-mid: #2D3A8C; --navy-lt: #3D4EA0;
  --teal: #97D700; --teal-lt: #7ab000;
  --ice: #CADCFC;
  --white: #ffffff; --off: #F4F6FB;
  --text: #1E293B; --muted: #64748B; --border: #E2E8F0;
  --green: #16A34A; --green-lt: #DCFCE7;
  --amber: #D97706; --amber-lt: #FEF3C7;
  --red: #DC2626; --red-lt: #FEE2E2;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; }}
body {{ font-family: 'Open Sans', sans-serif; background: var(--off); color: var(--text); line-height: 1.6; }}

@keyframes fadeUp {{
  from {{ opacity:0; transform:translateY(18px); }}
  to   {{ opacity:1; transform:translateY(0); }}
}}

/* ── HERO ── */
.hero {{
  background: linear-gradient(135deg, var(--navy) 0%, var(--navy-mid) 60%, #1a3a6b 100%);
  padding: 4rem 2rem 3rem;
  position: relative; overflow: hidden;
}}
.hero::before {{
  content:''; position:absolute; right:-5%; top:-20%;
  width:500px; height:500px; border-radius:50%;
  background:radial-gradient(circle, rgba(151,215,0,.25) 0%, transparent 70%);
}}
.hero::after {{
  content:''; position:absolute; right:15%; bottom:-30%;
  width:300px; height:300px; border-radius:50%;
  background:radial-gradient(circle, rgba(45,58,140,.4) 0%, transparent 70%);
}}
.hero-inner {{
  max-width:1200px; margin:0 auto; position:relative; z-index:1;
  display:flex; align-items:flex-end; justify-content:space-between; flex-wrap:wrap; gap:1.5rem;
}}
.hero-eyebrow {{
  font-size:11px; font-weight:600; color:var(--teal-lt); letter-spacing:.12em;
  text-transform:uppercase; margin-bottom:1rem;
  display:flex; align-items:center; gap:8px;
}}
.hero-eyebrow::before {{
  content:''; display:block; width:28px; height:2px; background:var(--teal-lt);
}}
.hero h1 {{
  font-size:clamp(2rem,4vw,3.2rem); font-weight:700; color:var(--white);
  line-height:1.1; margin-bottom:.75rem;
}}
.hero h1 span {{ color:var(--teal-lt); }}
.hero-sub {{ font-size:15px; color:var(--ice); opacity:.8; margin-bottom:1rem; font-weight:300; }}
.hero-date {{ text-align:right; color:var(--ice); font-size:12px; opacity:.8; line-height:1.8; }}
.hero-date strong {{ display:block; font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:var(--teal-lt); }}

/* ── CONTAINER ── */
.container {{ max-width:1200px; margin:0 auto; padding:0 2rem; }}

/* ── KPI STRIP ── */
.kpi-strip {{
  display:grid; grid-template-columns:repeat(4,1fr); gap:1rem;
  margin:2rem auto; max-width:1200px; padding:0 2rem;
  animation: fadeUp .5s ease both;
}}
@media(max-width:900px){{ .kpi-strip {{ grid-template-columns:repeat(2,1fr); }} }}
@media(max-width:480px){{ .kpi-strip {{ grid-template-columns:1fr; }} }}

.kpi-card {{
  background:var(--white); border-radius:14px;
  border:1px solid var(--border); padding:1.25rem 1.5rem;
  box-shadow:0 2px 12px rgba(30,39,97,.06);
  transition:transform .2s, box-shadow .2s;
}}
.kpi-card:hover {{ transform:translateY(-3px); box-shadow:0 8px 24px rgba(30,39,97,.12); }}
.kpi-label {{ font-size:11px; font-weight:600; color:var(--muted); letter-spacing:.06em;
  text-transform:uppercase; margin-bottom:.5rem; }}
.kpi-value {{ font-size:2rem; font-weight:700; color:var(--navy); line-height:1; }}
.kpi-sub {{ font-size:12px; color:var(--muted); margin-top:.3rem; }}
.kpi-value.green {{ color:var(--green); }}
.kpi-value.amber {{ color:var(--amber); }}
.kpi-value.red {{ color:var(--red); }}

/* ── MONTH TABS ── */
.section-tabs {{
  max-width:1200px; margin:0 auto 1.5rem; padding:0 2rem;
  animation: fadeUp .5s ease .1s both;
}}
.section-title {{
  font-size:13px; font-weight:700; color:var(--muted); letter-spacing:.08em;
  text-transform:uppercase; margin-bottom:1rem;
}}
.month-tabs {{ display:flex; gap:.5rem; flex-wrap:wrap; }}
.mtab {{
  font-size:12px; font-weight:600; padding:6px 16px; border-radius:20px;
  border:1.5px solid var(--border); background:var(--white);
  color:var(--muted); cursor:pointer; transition:all .15s;
  font-family:'Open Sans',sans-serif;
}}
.mtab:hover {{ border-color:var(--navy-mid); color:var(--navy-mid); }}
.mtab.active {{ background:var(--navy); color:var(--white); border-color:var(--navy); }}

/* ── PM GRID ── */
.pm-grid {{
  display:grid; grid-template-columns:repeat(2,1fr); gap:1.5rem;
  max-width:1200px; margin:0 auto 2rem; padding:0 2rem;
  animation: fadeUp .5s ease .15s both;
}}
@media(max-width:760px){{ .pm-grid {{ grid-template-columns:1fr; }} }}

.pm-card {{
  background:var(--white); border-radius:16px;
  border:1px solid var(--border); padding:1.5rem;
  box-shadow:0 2px 12px rgba(30,39,97,.06);
  transition:transform .2s, box-shadow .2s;
}}
.pm-card:hover {{ transform:translateY(-2px); box-shadow:0 8px 24px rgba(30,39,97,.1); }}

.pm-card-header {{ display:flex; align-items:center; gap:1rem; margin-bottom:1rem; }}
.pm-avatar {{
  width:44px; height:44px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-size:16px; font-weight:700; color:#fff; flex-shrink:0;
  background:var(--navy);
}}
.pm-info {{ flex:1; }}
.pm-name {{ font-size:15px; font-weight:700; color:var(--navy); }}
.pm-role {{ font-size:11px; color:var(--muted); }}

/* badges */
.pm-badge {{ font-size:14px; font-weight:700; padding:4px 12px; border-radius:20px; }}
.badge-green {{ background:var(--green-lt); color:var(--green); }}
.badge-amber {{ background:var(--amber-lt); color:var(--amber); }}
.badge-red   {{ background:var(--red-lt);   color:var(--red); }}
.badge-over  {{ background:#f3e8ff; color:#7c3aed; }}

/* barra */
.pm-bar-wrap {{
  height:8px; background:var(--border); border-radius:4px;
  margin-bottom:.75rem; overflow:hidden;
}}
.pm-bar {{ height:100%; border-radius:4px; transition:width .5s ease; }}
.bar-green {{ background:var(--green); }}
.bar-amber {{ background:var(--amber); }}
.bar-red   {{ background:var(--red); }}
.bar-over  {{ background:#7c3aed; }}

/* detalle busy/tent */
.pm-detail {{ display:flex; gap:1rem; margin-bottom:1rem; flex-wrap:wrap; }}
.detail-item {{ font-size:11px; color:var(--muted); }}

/* weekly breakdown */
.weekly-section {{ margin-top:.5rem; }}
.week-row {{
  display:flex; align-items:center; gap:.75rem;
  margin-bottom:.5rem; flex-wrap:wrap;
}}
.week-label {{ font-size:11px; color:var(--muted); width:120px; flex-shrink:0; }}
.day-cells {{ display:flex; gap:.3rem; }}
.day-cell {{
  width:38px; border-radius:6px; padding:3px 4px;
  text-align:center; font-size:10px; font-weight:600;
}}
.dc-abbr {{ display:block; font-size:9px; opacity:.7; }}
.dc-val  {{ display:block; }}
.dc-green {{ background:var(--green-lt); color:var(--green); }}
.dc-amber {{ background:var(--amber-lt); color:var(--amber); }}
.dc-red   {{ background:var(--red-lt);   color:var(--red); }}
.dc-over  {{ background:#f3e8ff; color:#7c3aed; border:1.5px solid #c4b5fd; }}

/* ── CHART ── */
.chart-section {{
  max-width:1200px; margin:0 auto 3rem; padding:0 2rem;
  animation: fadeUp .5s ease .2s both;
}}
.chart-card {{
  background:var(--white); border-radius:16px;
  border:1px solid var(--border); padding:1.5rem;
  box-shadow:0 2px 12px rgba(30,39,97,.06);
}}
.chart-title {{ font-size:14px; font-weight:700; color:var(--navy); margin-bottom:1rem; }}
.chart-wrap {{ position:relative; height:300px; }}

/* ── FOOTER ── */
footer {{
  text-align:center; padding:2rem; font-size:12px; color:var(--muted);
  border-top:1px solid var(--border); margin-top:1rem;
}}
footer a {{ color:var(--navy-mid); text-decoration:none; }}
footer a:hover {{ text-decoration:underline; }}
</style>
</head>
<body>

<!-- NAV -->
<nav class="pmo-hub-nav">
  <a href="../" class="pmo-nav-logo">
    <img src="../assets/logo.png" alt="Censys PMO">
    <div class="pmo-nav-title-group">
      <span class="pmo-nav-title">PMO Hub</span>
      <span class="pmo-nav-sub">CEN Systems</span>
    </div>
  </a>
  <div class="pmo-nav-links">
    <a href="../">Inicio</a>
    <a href="../portafolio/">Portafolio</a>
    <a href="../ocupacion/" class="active">Ocupación</a>
    <a href="../kpis/">KPIs</a>
    <a href="../tools/">Herramientas</a>
  </div>
</nav>

<!-- HERO -->
<div class="hero">
  <div class="hero-inner">
    <div>
      <div class="hero-eyebrow">PMO Hub · Dashboard de Recursos</div>
      <h1>Ocupación del <span>Equipo</span></h1>
      <p class="hero-sub">Análisis basado en calendarios de Office 365 · Horario laboral 8:00–17:00 CDMX</p>
    </div>
    <div class="hero-date">
      <strong>Actualizado</strong>
      {fecha_gen}
    </div>
  </div>
</div>

<!-- KPI STRIP -->
<div class="kpi-strip">
  <div class="kpi-card">
    <div class="kpi-label">Ocupación promedio</div>
    <div class="kpi-value {avg_bcls.replace('badge-','')}">{avg_pct}%</div>
    <div class="kpi-sub">{MONTH_ES[am]} {ay} · equipo completo</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">PM más ocupado</div>
    <div class="kpi-value red">{pcts_active.get(max_pm, 0)}%</div>
    <div class="kpi-sub">{max_pm}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Mayor disponibilidad</div>
    <div class="kpi-value green">{pcts_active.get(min_pm, 0)}%</div>
    <div class="kpi-sub">{min_pm}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Período cubierto</div>
    <div class="kpi-value" style="font-size:1.2rem">{periodo}</div>
    <div class="kpi-sub">{len(all_months)} {"mes" if len(all_months)==1 else "meses"} con datos</div>
  </div>
</div>

<!-- MONTH TABS -->
<div class="section-tabs">
  <div class="section-title">Seleccionar período</div>
  <div class="month-tabs">
    {tabs_html}
  </div>
</div>

<!-- PM GRID -->
<div class="pm-grid" id="pm-grid">
{cards_html}
</div>

<!-- TENDENCIA CHART -->
<div class="chart-section">
  <div class="chart-card">
    <div class="chart-title">Tendencia de Ocupación por PM (%)</div>
    <div class="chart-wrap">
      <canvas id="trendChart"></canvas>
    </div>
  </div>
</div>

<!-- FOOTER -->
<footer>
  <strong>CEN Systems</strong> · PMO Hub ·
  <a href="mailto:alceca3000@gmail.com">Alan Cerón Cardonne</a> · PMP® · Six Sigma MBB
</footer>

<script>
// ── Datos embebidos ──────────────────────────────────────────────────────────
const CHART_DATA = {chart_data_json};
const ALL_MONTHS = {json.dumps(all_months)};

// ── Chart.js ─────────────────────────────────────────────────────────────────
(function() {{
  const ctx = document.getElementById('trendChart').getContext('2d');
  new Chart(ctx, {{
    type: 'bar',
    data: CHART_DATA,
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ position: 'top', labels: {{ font: {{ size:11 }} }} }},
        annotation: {{ /* chartjs-plugin-annotation not loaded */ }},
        tooltip: {{
          callbacks: {{
            label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.parsed.y !== null ? ctx.parsed.y.toFixed(1)+'%' : 'sin datos'}}`
          }}
        }}
      }},
      scales: {{
        y: {{
          min: 0, max: 100,
          ticks: {{ callback: v => v+'%', font: {{ size:11 }} }},
          grid: {{ color: 'rgba(0,0,0,.06)' }}
        }},
        x: {{ ticks: {{ font: {{ size:11 }} }} }}
      }}
    }},
    plugins: [{{
      id: 'refLine',
      afterDraw(chart) {{
        const {{ ctx, scales: {{y, x}} }} = chart;
        const y80 = y.getPixelForValue(80);
        ctx.save();
        ctx.setLineDash([6,4]);
        ctx.strokeStyle = 'rgba(220,38,38,0.5)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(x.left, y80);
        ctx.lineTo(x.right, y80);
        ctx.stroke();
        ctx.restore();
        ctx.fillStyle = 'rgba(220,38,38,0.7)';
        ctx.font = '10px Open Sans';
        ctx.fillText('80%', x.right + 4, y80 + 4);
      }}
    }}]
  }});
}})();

// ── Cambio de mes ─────────────────────────────────────────────────────────────
function showMonth(month, btn) {{
  // activar tab
  document.querySelectorAll('.mtab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');

  // actualizar cada card de PM
  document.querySelectorAll('.pm-card').forEach(card => {{
    const name    = card.dataset.pm;
    const mdata   = JSON.parse(card.dataset.months);
    const safeName = name.replace(/ /g, '-');
    const vals    = mdata[month] || {{pct:0, busy_min:0, tent_min:0}};
    const p       = vals.pct;
    const bcls    = p > 100 ? 'badge-over' : (p < 70 ? 'badge-green' : (p <= 90 ? 'badge-amber' : 'badge-red'));
    const brcls   = p > 100 ? 'bar-over'   : (p < 70 ? 'bar-green'   : (p <= 90 ? 'bar-amber'   : 'bar-red'));

    const badge = document.getElementById('badge-' + safeName);
    const bar   = document.getElementById('bar-'   + safeName);
    const detail= document.getElementById('detail-' + safeName);

    if (badge) {{
      badge.textContent = p.toFixed(1) + '%';
      badge.className   = 'pm-badge ' + bcls;
    }}
    if (bar) {{
      bar.style.width = Math.min(p, 100) + '%';
      bar.className   = 'pm-bar ' + brcls;
    }}
    if (detail) {{
      detail.innerHTML =
        '<span class="detail-item">Confirmado: ' + vals.busy_min + ' min</span>' +
        '<span class="detail-item">Tentativo: '  + vals.tent_min  + ' min</span>';
    }}

    // weekly breakdowns
    ALL_MONTHS.forEach(m => {{
      const wb = document.getElementById('wb-' + safeName + '-' + m);
      if (wb) wb.style.display = (m === month) ? 'block' : 'none';
    }});
  }});
}}
</script>
</body>
</html>
"""
    return html


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[ocupacion] Directorio ICS: {ICS_DIR}")

    ics_files = sorted(ICS_DIR.glob("*.ics"))
    if not ics_files:
        print("[ocupacion] ADVERTENCIA: No se encontraron archivos .ics. "
              "Generando página vacía.")

    pm_data: dict[str, dict] = {}

    for ics_path in ics_files:
        pm_name = ics_path.stem
        print(f"  · Procesando: {pm_name} ...", end=" ", flush=True)
        events  = parse_ics(ics_path)
        daily   = compute_daily_busy(events)
        monthly = group_by_month(daily)
        pm_data[pm_name] = monthly
        total_ev = len(events)
        total_days = len(daily)
        print(f"{total_ev} eventos, {total_days} días con ocupación")

    html = generate_html(pm_data)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Listo: {OUTPUT}")


if __name__ == "__main__":
    main()
