#!/usr/bin/env python3
"""
CEN Systems — Dashboard Generator (PMO Hub edition)
Lee KPIS para dashboard ejecutivo.xlsx y genera portafolio/index.html
con branding unificado del PMO Hub.

Uso: python portafolio/generate_dashboard.py
     (ejecutar desde la raiz del repo pmo-hub)
"""

import pandas as pd
import json
import base64
import sys
import os
from datetime import datetime, date
from pathlib import Path

# ── Rutas (relativas a la raiz del repo) ─────────────────────────────────────
ROOT       = Path(__file__).parent.parent          # raiz del repo
EXCEL_FILE = str(ROOT / "portafolio" / "KPIS para dashboard ejecutivo.xlsx")
OUTPUT_FILE= str(ROOT / "portafolio" / "index.html")
LOGO_FILE  = str(ROOT / "assets" / "logo.png")
YEARS      = ["2023", "2024", "2025", "2026"]

# ── Hub nav CSS (sin @import — fuente se carga via <link>) ───────────────────
HUB_NAV_CSS = """\
/* === Censys PMO Hub - Nav compartido === */
.pmo-hub-nav{display:flex;align-items:center;justify-content:space-between;
  padding:0 24px;height:52px;background:#1a1a2e;border-bottom:3px solid #97D700;
  position:sticky;top:0;z-index:9999;font-family:'Open Sans',sans-serif;
  box-sizing:border-box;}
.pmo-nav-logo{display:flex;align-items:center;gap:10px;text-decoration:none;}
.pmo-nav-logo img{height:30px;width:auto;}
.pmo-nav-title-group{display:flex;flex-direction:column;line-height:1.2;}
.pmo-nav-title{font-size:13px;font-weight:700;color:#fff;letter-spacing:.02em;}
.pmo-nav-sub{font-size:10px;color:#97D700;font-weight:600;letter-spacing:.04em;
  text-transform:uppercase;}
.pmo-nav-links{display:flex;gap:4px;}
.pmo-nav-links a{font-size:12px;color:rgba(255,255,255,.75);text-decoration:none;
  padding:5px 12px;border-radius:6px;font-weight:500;transition:all .15s;}
.pmo-nav-links a:hover{background:rgba(255,255,255,.1);color:#fff;}
@media(max-width:640px){.pmo-nav-links{display:none;}}
/* ══════════════════════════════════════════════════════ */
"""

# ── Fecha de corte ────────────────────────────────────────────────────────────
def get_excel_date():
    from datetime import timedelta
    UTC_OFFSET = timedelta(hours=-6)
    try:
        import zipfile, xml.etree.ElementTree as ET
        with zipfile.ZipFile(EXCEL_FILE) as z:
            if "docProps/core.xml" in z.namelist():
                tree = ET.parse(z.open("docProps/core.xml"))
                ns   = {"dcterms": "http://purl.org/dc/terms/"}
                mod  = tree.find("dcterms:modified", ns)
                if mod is not None and mod.text:
                    dt_utc  = datetime.strptime(mod.text[:19], "%Y-%m-%dT%H:%M:%S")
                    dt_cdmx = dt_utc + UTC_OFFSET
                    print(f"   Fecha Excel (CDMX): {dt_cdmx.strftime('%d/%m/%Y %H:%M')}")
                    return dt_cdmx.date(), dt_cdmx.strftime("%d/%m/%Y %H:%M") + " CDMX"
    except Exception as e:
        print(f"   Warning fecha XML: {e}")
    try:
        ts      = os.path.getmtime(EXCEL_FILE)
        dt_utc  = datetime.utcfromtimestamp(ts)
        dt_cdmx = dt_utc + UTC_OFFSET
        return dt_cdmx.date(), dt_cdmx.strftime("%d/%m/%Y %H:%M") + " CDMX"
    except:
        pass
    dt_cdmx = datetime.utcnow() + UTC_OFFSET
    return dt_cdmx.date(), dt_cdmx.strftime("%d/%m/%Y %H:%M") + " CDMX"

CORTE, CORTE_LABEL = get_excel_date()

# ── Helpers ───────────────────────────────────────────────────────────────────
def sem_calc(est, fecha, is_sinoc=False, is_rec=False):
    if is_rec:   return "Recurrente"
    if is_sinoc: return "Riesgo Alto"
    if any(k in est for k in ["CONTRATO LEGAL","PEND OC","PENDIENTE CONTRATO"]):
        return "Riesgo Alto"
    if fecha == "—": return "—"
    try:
        fd   = datetime.strptime(fecha, "%Y-%m-%d").date()
        days = (fd - CORTE).days
        if days < 0:   return "Vencido"
        if days <= 30: return "Crítico ≤30d"
        if days <= 60: return "Alerta 31-60d"
        if days <= 90: return "Vigilar 61-90d"
        return "OK >90d"
    except:
        return "—"

def esc(s):
    return str(s).strip().replace("\\","").replace('"','\\"').replace("'","")[:70]

EST_PFX = ("2.","3.","4.","5.","6.","7.","8.","9.",
           "TERMINADO","EN HOLD","CANCEL","REVISANDO","PLANEANDO",
           "KICKOFF","SOLICITADA","PENDIENTE FACTURAR")

# ── Section boundary detection ────────────────────────────────────────────────
SEC_KEYWORDS = [
    ("PRY Creados",                "creados"),
    ("PRY Cerrados por Conta",     "cerrados_cp"),
    ("PRY Cerrados por Proyectos", "cerrados_pry"),
    ("PRY Fac Recurrente",         "recurrente"),
    ("PRY sin OC",                 "sin_oc"),
    ("PRY Abiertos",               "abiertos"),
]

def get_bounds(df):
    bounds = []
    for i, row in df.iterrows():
        c1 = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        for kw, key in SEC_KEYWORDS:
            if kw in c1:
                if key == "abiertos" and "Pend" in c1:
                    key = "abiertos_pend"
                bounds.append((i, key))
                break
    bounds.append((len(df) + 999, "END"))
    return bounds

# ── Data extraction ───────────────────────────────────────────────────────────
def extract(df):
    bounds = get_bounds(df)
    summary = {}; pry = {}

    for idx, (sec_row, sec_key) in enumerate(bounds[:-1]):
        next_row  = bounds[idx + 1][0]
        sec_slice = df.iloc[sec_row:next_row]

        sec_has_fecha = False
        sum_proj = {}; sum_serv = {}; n = 0; rows = []

        for _, row in sec_slice.iterrows():
            rl = list(row.values)
            c1 = str(rl[1]).strip() if len(rl)>1 and pd.notna(rl[1]) else ""
            c3 = str(rl[3]).strip() if len(rl)>3 and pd.notna(rl[3]) else ""

            def g(i2, d=0):
                v = rl[i2] if i2 < len(rl) and pd.notna(rl[i2]) else None
                if v is None: return d
                try: return float(v)
                except: return d

            if c1 == "PRY" and len(rl)>2 and str(rl[2]).strip() == "CLIENTE":
                c10 = str(rl[10]).strip() if len(rl)>10 and pd.notna(rl[10]) else ""
                sec_has_fecha = "echa" in c10.lower()
                continue

            if c3 in ("Proyecto", "Servicio"):
                try:
                    nv = float(c1)
                    if nv > 0 and c3 == "Proyecto": n = int(nv)
                except: pass
                d = {"vp":g(4),"cp":g(5),"fac":g(9),"cr":g(10)}
                if c3 == "Proyecto": sum_proj = d
                else:                sum_serv = d
                continue

            if not c1.startswith("PRY-"): continue

            cli  = esc(str(rl[2])) if len(rl)>2 and pd.notna(rl[2]) else "—"
            nom  = esc(str(rl[3])) if len(rl)>3 and pd.notna(rl[3]) else "—"
            vp   = g(4); fac = g(6); pend = g(8)
            est  = "—"; fecha = "—"; fecha_real = "—"

            if sec_has_fecha or sec_key in ("abiertos","abiertos_pend"):
                v9  = rl[9]  if len(rl)>9  and pd.notna(rl[9])  else None
                v10 = rl[10] if len(rl)>10 and pd.notna(rl[10]) else None
                v11 = rl[11] if len(rl)>11 and pd.notna(rl[11]) else None
                if v9:
                    sv = str(v9).strip()
                    if any(sv.startswith(p) for p in EST_PFX): est = sv
                if isinstance(v10, datetime): fecha      = v10.strftime("%Y-%m-%d")
                if isinstance(v11, datetime): fecha_real = v11.strftime("%Y-%m-%d")

            is_rec   = sec_key == "recurrente"
            is_sinoc = sec_key == "sin_oc"
            rows.append({
                "p": c1, "c": cli, "n": nom,
                "est": esc(est), "fecha": fecha, "fecha_real": fecha_real,
                "vp": round(vp,2), "fac": round(fac,2), "pend": round(pend,2),
                "sem": sem_calc(est, fecha, is_sinoc=is_sinoc, is_rec=is_rec)
            })

        summary[sec_key] = {"n": n, "proj": sum_proj, "serv": sum_serv}
        pry[sec_key]     = rows

    return summary, pry

# ── KPI helpers ───────────────────────────────────────────────────────────────
def kpi(yr_sum):
    d  = yr_sum.get("creados", {})
    p  = d.get("proj", {}); s = d.get("serv", {})
    vp = p.get("vp",0) + s.get("vp",0)
    fac= p.get("fac",0)+ s.get("fac",0)
    cr = p.get("cr",0) + s.get("cr",0)
    mg = fac - cr
    pct= mg/fac*100 if fac else 0
    return {"n":d.get("n",0),"vp":vp,"fac":fac,"cr":cr,"mg":mg,"pct":pct}

# ── JS DATA builder ───────────────────────────────────────────────────────────
SEC_CFG = [
    ("creados",       "PRY Creados — Total año",                        [],                                False),
    ("cerrados_cp",   "PRY Cerrados — Contabilidad y Proyectos",         [],                                False),
    ("cerrados_pry",  "PRY Cerrados — Solo por Proyectos",               [],                                False),
    ("recurrente",    "PRY Facturación Recurrente",                      ["est","sem"],                     False),
    ("sin_oc",        "PRY sin OC o Contrato",                           ["sem"],                           True),
    ("abiertos",      "PRY Abiertos (sin pendiente)",                    ["est","fecha","fecha_real","sem"], False),
    ("abiertos_pend", "PRY Abiertos con Pendiente por Facturar",         ["est","fecha","sem"],              False),
]

def pry_js(rows):
    if not rows: return "[]"
    items = []
    for r in rows:
        items.append(
            '{p:"'+r["p"]+'",c:"'+r["c"]+'",n:"'+r["n"]+'",est:"'+r["est"]+'",fecha:"'+r["fecha"]+'",'
            'fecha_real:"'+r.get("fecha_real","—")+'",vp:'+str(r["vp"])+',fac:'+str(r["fac"])+','
            'pend:'+str(r["pend"])+',"sem":"'+r["sem"]+'"}'
        )
    return "[\n        " + ",\n        ".join(items) + "\n      ]"

def build_data_js(all_summary, all_pry):
    years = []
    for yr in YEARS:
        S = all_summary.get(yr, {}); P = all_pry.get(yr, {})
        segs = []
        for sec, title, ec, is_sinoc in SEC_CFG:
            d  = S.get(sec, {"n":0,"proj":{},"serv":{}})
            p  = d.get("proj",{}); s = d.get("serv",{})
            def pv(k): return round(p.get(k,0),4)
            def sv(k): return round(s.get(k,0),4)
            seg = ('{ title:"'+title+'", n:'+str(d.get("n",0))+', isSinOC:'+("true" if is_sinoc else "false")+','
                   '\n      proj:{vp:'+str(pv("vp"))+'*M,cp:'+str(pv("cp"))+'*M,fac:'+str(pv("fac"))+'*M,cr:'+str(pv("cr"))+'*M},'
                   '\n      serv:{vp:'+str(sv("vp"))+'*M,cp:'+str(sv("cp"))+'*M,fac:'+str(sv("fac"))+'*M,cr:'+str(sv("cr"))+'*M},'
                   '\n      pry:'+pry_js(P.get(sec,[]))+','
                   '\n      ec:'+json.dumps(ec)+'}')
            segs.append(seg)
        years.append('"'+yr+'": [\n    '+ ',\n    '.join(segs) +'\n  ]')
    return "var DATA = {\n  " + ",\n  ".join(years) + "\n};"

# ── Logo loader ───────────────────────────────────────────────────────────────
def load_logo():
    if os.path.exists(LOGO_FILE):
        with open(LOGO_FILE, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

# ── KPI panels ───────────────────────────────────────────────────────────────
def kpi_html_2026(k):
    fac_pct = k["fac"]/k["vp"]*100 if k["vp"] else 0
    pend    = k["vp"] - k["fac"]
    mg_str  = ("-$"+f"{abs(k['mg']):.1f}M") if k["mg"]<0 else ("$"+f"{k['mg']:.1f}M")
    return (
        '<div class="kpi"><div class="kpi-lbl">PRY Creados</div>'
        f'<div class="kpi-val">{k["n"]}</div><div class="kpi-sub c-muted">Año en curso</div></div>'
        f'<div class="kpi"><div class="kpi-lbl">Pipeline total</div><div class="kpi-val">${k["vp"]:.1f}M</div>'
        '<div class="prog"><div class="prog-fill" style="width:100%"></div></div></div>'
        f'<div class="kpi"><div class="kpi-lbl">Facturado al corte</div><div class="kpi-val">${k["fac"]:.1f}M</div>'
        f'<div class="kpi-sub c-warn">{fac_pct:.1f}% del pipeline</div>'
        f'<div class="prog"><div class="prog-fill" style="width:{min(fac_pct,100):.1f}%;background:#d4962a"></div></div></div>'
        f'<div class="kpi"><div class="kpi-lbl">Pendiente facturar</div><div class="kpi-val">${pend:.1f}M</div>'
        '<div class="kpi-sub c-info">Por ejecutar y facturar</div></div>'
        f'<div class="kpi"><div class="kpi-lbl">Margen al corte</div><div class="kpi-val">{mg_str}</div>'
        '<div class="kpi-sub c-bad">Costos devengando</div></div>'
    )

def kpi_html_hist(k, yr):
    fac_pct = k["fac"]/k["vp"]*100 if k["vp"] else 0
    mg_pct  = k["mg"]/k["fac"]*100 if k["fac"] else 0
    return (
        f'<div class="kpi"><div class="kpi-lbl">PRY Creados</div><div class="kpi-val">{k["n"]}</div>'
        '<div class="kpi-sub c-muted">Proyectos y Servicios</div></div>'
        f'<div class="kpi"><div class="kpi-lbl">Venta prevista</div><div class="kpi-val">${k["vp"]:.1f}M</div></div>'
        f'<div class="kpi"><div class="kpi-lbl">Facturado real</div><div class="kpi-val">${k["fac"]:.1f}M</div>'
        f'<div class="kpi-sub c-good">{fac_pct:.1f}% del previsto</div></div>'
        f'<div class="kpi"><div class="kpi-lbl">Margen real</div><div class="kpi-val">${k["mg"]:.1f}M</div>'
        f'<div class="kpi-sub c-good">{mg_pct:.1f}% promedio</div></div>'
    )

# ── HTML template (hub-ready) ─────────────────────────────────────────────────
def build_html(logo_b64, data_js, all_kpis):
    logo_src = f"data:image/png;base64,{logo_b64}" if logo_b64 else "../assets/logo.png"

    panels = ""
    for yr in YEARS:
        k       = all_kpis[yr]
        active  = " active" if yr == "2026" else ""
        kpi_div = kpi_html_2026(k) if yr == "2026" else kpi_html_hist(k, yr)
        alert   = ""
        if yr == "2024":
            alert = '<div class="alert">Recurrentes 2024: margen real negativo. Ferrocarril Mexicano ($26.2M pendiente) es la exposición crítica.</div>'
        if yr == "2026":
            alert = '<div class="alert">AT&amp;T ($55.3M) sin estatus asignado. Costo devengado supera lo facturado — acelerar facturación en Q2 es crítico.</div>'
        panels += f'<div class="yr-panel{active}" id="p{yr}"><div class="kpi-strip">{kpi_div}</div>{alert}<div id="seg{yr}"></div></div>\n'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Portafolio de Proyectos \u00b7 PMO Hub</title>
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
{HUB_NAV_CSS}
:root{{--navy:#1E2761;--navy-mid:#2D3A8C;--teal:#97D700;--ice:#CADCFC;--green:#97D700;--bg:#F4F6FB;--surface:#ffffff;--border:rgba(151,215,0,0.25);--border-sub:#E2E8F0;--text:#1E293B;--text2:#64748B;--text3:#94A3B8;--danger:#dc2626;--warning:#d97706;--info:#2563eb;--r-sm:6px;--r-md:10px;--r-lg:16px;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Open Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;font-size:14px;line-height:1.6;}}
.hero{{background:linear-gradient(135deg,#1E2761 0%,#2D3A8C 60%,#1a3a6b 100%);padding:3rem 2rem 2.5rem;position:relative;overflow:hidden;}}
.hero::before{{content:'';position:absolute;right:-5%;top:-20%;width:500px;height:500px;border-radius:50%;background:radial-gradient(circle,rgba(151,215,0,.15) 0%,transparent 70%);}}
.hero-inner{{max-width:1280px;margin:0 auto;position:relative;z-index:1;display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:16px;}}
.hero-eyebrow{{font-size:11px;font-weight:600;color:#97D700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.75rem;display:flex;align-items:center;gap:8px;}}
.hero-eyebrow::before{{content:'';display:block;width:28px;height:2px;background:#97D700;}}
.hero h1{{font-size:clamp(1.6rem,3vw,2.4rem);font-weight:700;color:#fff;line-height:1.1;margin-bottom:.5rem;}}
.hero h1 span{{color:#97D700;}}
.hero-sub{{font-size:13px;color:#CADCFC;opacity:.85;font-weight:300;}}
.hero-date{{font-size:12px;color:#CADCFC;opacity:.7;text-align:right;white-space:nowrap;}}
.hero-date strong{{color:#97D700;font-weight:600;display:block;font-size:11px;letter-spacing:.06em;text-transform:uppercase;margin-bottom:2px;}}
main{{max-width:1280px;margin:0 auto;padding:28px 32px 64px;}}
.page-header{{margin-bottom:28px;display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:12px;}}
.page-title{{font-size:22px;font-weight:700;letter-spacing:-.3px;color:var(--text);}}
.page-sub{{font-size:13px;color:var(--text2);margin-top:4px;}}
.yr-tabs{{display:flex;gap:4px;background:#f1f5f9;padding:4px;border-radius:var(--r-md);border:1px solid var(--border-sub);}}
.yr-btn{{font-family:'Open Sans',sans-serif;font-size:13px;font-weight:500;padding:7px 22px;border:none;border-radius:var(--r-sm);background:transparent;color:var(--text3);cursor:pointer;transition:all .2s;}}
.yr-btn:hover{{color:var(--text);}}
.yr-btn.active{{background:var(--green);color:#fff;font-weight:700;}}
.kpi-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px;}}
.kpi{{background:var(--surface);border:1px solid var(--border-sub);border-radius:var(--r-md);padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.06);}}
.kpi-lbl{{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;}}
.kpi-val{{font-size:21px;font-weight:700;letter-spacing:-.5px;}}
.kpi-sub{{font-size:11px;margin-top:4px;font-weight:500;}}
.c-good{{color:#16a34a;}}.c-warn{{color:var(--warning);}}.c-bad{{color:var(--danger);}}.c-info{{color:var(--info);}}.c-muted{{color:var(--text3);}}
.prog{{height:3px;background:#e2e8f0;border-radius:2px;margin-top:6px;overflow:hidden;}}
.prog-fill{{height:100%;border-radius:2px;background:var(--green);}}
.alert{{background:#fef2f2;border:1px solid #fecaca;border-radius:var(--r-md);padding:10px 16px;font-size:12.5px;color:#b91c1c;margin-bottom:14px;display:flex;align-items:flex-start;gap:8px;}}
.alert::before{{content:"!";flex-shrink:0;font-weight:700;margin-top:1px;}}
.seg{{background:var(--surface);border:1px solid var(--border-sub);border-radius:var(--r-lg);overflow:hidden;margin-bottom:10px;transition:border-color .2s;box-shadow:0 1px 3px rgba(0,0,0,.05);}}
.seg:hover{{border-color:var(--green);}}.seg.risk-high{{border-left:3px solid var(--danger);}}
.seg-hdr{{display:flex;align-items:center;justify-content:space-between;padding:11px 18px;background:#f8fafc;border-bottom:1px solid var(--border-sub);}}
.seg-title{{font-size:11.5px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:.07em;}}
.badge{{display:inline-flex;align-items:center;font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;}}
.b-gray{{background:#e2e8f0;color:var(--text2);}}.b-red{{background:#fee2e2;color:#b91c1c;}}
.b-risk{{background:#fee2e2;color:#b91c1c;border:1px solid #fecaca;font-weight:700;}}
.expand-btn{{font-family:'Open Sans',sans-serif;font-size:11px;padding:4px 12px;border:1px solid var(--border-sub);border-radius:var(--r-sm);background:transparent;color:var(--text3);cursor:pointer;transition:all .15s;}}
.expand-btn:hover{{border-color:var(--green);color:var(--green);}}
.seg-table{{width:100%;border-collapse:collapse;}}
.seg-table th{{font-size:10.5px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.05em;padding:8px 18px;text-align:left;border-bottom:1px solid var(--border-sub);background:#f8fafc;}}
.seg-table th.r{{text-align:right;}}
.seg-table td{{padding:9px 18px;font-size:13px;border-bottom:1px solid #f1f5f9;}}
.seg-table td.r{{text-align:right;font-variant-numeric:tabular-nums;font-size:12.5px;}}
.seg-table tr:last-child td{{border-bottom:none;}}.seg-table tr:hover td{{background:#f8fafc;}}
.type-tag{{font-size:11px;color:var(--text2);font-weight:500;}}
.pill{{display:inline-flex;align-items:center;font-size:10px;font-weight:600;padding:2px 7px;border-radius:20px;white-space:nowrap;}}
.p-ok{{background:#dcfce7;color:#16a34a;}}.p-warn{{background:#fef3c7;color:#d97706;}}
.p-bad{{background:#fee2e2;color:#dc2626;}}.p-info{{background:#dbeafe;color:#2563eb;}}
.p-muted{{background:#f1f5f9;color:var(--text3);}}
.p-risk{{background:#fee2e2;color:#b91c1c;border:1px solid #fecaca;font-weight:700;}}
.risk-banner{{background:#fef2f2;border-top:1px solid #fecaca;padding:10px 18px;font-size:12px;color:#b91c1c;display:flex;align-items:flex-start;gap:8px;}}
.drill-wrap{{display:none;border-top:1px solid var(--border-sub);padding:14px 18px;background:#f8fafc;overflow-x:auto;}}
.drill-table{{width:100%;border-collapse:collapse;min-width:700px;}}
.drill-table th{{font-size:10px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.06em;padding:6px 8px;text-align:left;border-bottom:1px solid var(--border-sub);white-space:nowrap;background:#f8fafc;}}
.drill-table th.r{{text-align:right;}}
.drill-table td{{padding:7px 8px;font-size:11.5px;border-bottom:1px solid #f1f5f9;vertical-align:top;color:var(--text2);}}
.drill-table td.mono{{font-size:10.5px;color:var(--text3);white-space:nowrap;}}
.drill-table td.cli{{font-weight:500;color:var(--text);max-width:120px;}}.drill-table td.nom{{max-width:200px;}}
.drill-table td.r{{text-align:right;font-size:11px;font-variant-numeric:tabular-nums;}}
.drill-table td.pend{{text-align:right;font-weight:600;color:var(--text);}}
.drill-table tr:last-child td{{border-bottom:none;}}.drill-table tr:hover td{{background:#f1f5f9;}}
.yr-panel{{display:none;}}.yr-panel.active{{display:block;}}
footer{{border-top:1px solid var(--border-sub);padding:18px 32px;display:flex;align-items:center;justify-content:space-between;font-size:11px;color:var(--text3);background:#fff;}}
::-webkit-scrollbar{{width:5px;height:5px;}}::-webkit-scrollbar-track{{background:transparent;}}
::-webkit-scrollbar-thumb{{background:rgba(0,0,0,0.12);border-radius:3px;}}
::-webkit-scrollbar-thumb:hover{{background:rgba(151,215,0,0.6);}}
</style>
</head>
<body>
<nav class="pmo-hub-nav">
  <a href="../" class="pmo-nav-logo">
    <img src="{logo_src}" alt="Censys PMO">
    <div class="pmo-nav-title-group">
      <span class="pmo-nav-title">PMO Hub</span>
      <span class="pmo-nav-sub">CEN Systems</span>
    </div>
  </a>
  <div class="pmo-nav-links">
    <a href="../">Inicio</a>
    <a href="../portafolio/">Portafolio</a>
    <a href="../ocupacion/">Ocupacion</a>
    <a href="../kpis/">KPIs</a>
    <a href="../tools/">Herramientas</a>
  </div>
</nav>
<div class="hero">
  <div class="hero-inner">
    <div>
      <div class="hero-eyebrow">PMO Hub · Dashboard Ejecutivo</div>
      <h1>Portafolio de <span>Proyectos</span></h1>
      <p class="hero-sub">CEN Systems · Análisis financiero año por año · Valores en MXN (millones)</p>
    </div>
    <div class="hero-date">
      <strong>Última actualización</strong>
      {CORTE_LABEL}
    </div>
  </div>
</div>
<main>
  <div class="page-header">
    <div></div>
    <div class="yr-tabs">
      <button class="yr-btn" onclick="switchYr('2023',this)">2023</button>
      <button class="yr-btn" onclick="switchYr('2024',this)">2024</button>
      <button class="yr-btn" onclick="switchYr('2025',this)">2025</button>
      <button class="yr-btn active" onclick="switchYr('2026',this)">2026</button>
    </div>
  </div>
  {panels}
</main>
<footer>
  <img src="{logo_src}" alt="CEN Systems" style="height:22px;opacity:.35;">
  <div>Dashboard Ejecutivo &middot; CEN Systems S.A. de C.V. &middot; Portafolio Proyectos y Servicios &middot; {CORTE_LABEL}</div>
</footer>
<script>
var M = 1e6;
{data_js}
function fmt(v,dec){{dec=(dec===undefined)?1:dec;if(!v||isNaN(v))return "$0.0M";if(v<0)return "-$"+Math.abs(v).toFixed(dec)+"M";return "$"+v.toFixed(dec)+"M";}}
function calcMg(vp,cp){{return vp>0?(vp-cp)/vp*100:NaN;}}
function calcMgReal(fac,cr){{return fac>0?(fac-cr)/fac*100:NaN;}}
function mgPill(pct){{if(isNaN(pct)||pct===0)return "<span class=\\"pill p-muted\\">N/D</span>";if(pct>=25)return "<span class=\\"pill p-ok\\">"+pct.toFixed(1)+"%</span>";if(pct>=15)return "<span class=\\"pill p-warn\\">"+pct.toFixed(1)+"%</span>";return "<span class=\\"pill p-bad\\">"+pct.toFixed(1)+"%</span>";}}
function semPill(s){{var map={{"OK >90d":"<span class=\\"pill p-ok\\">OK &gt;90d</span>","Alerta 31-60d":"<span class=\\"pill p-warn\\">Alerta 31-60d</span>","Crítico ≤30d":"<span class=\\"pill p-bad\\">Crítico ≤30d</span>","Vencido":"<span class=\\"pill p-bad\\">Vencido</span>","Vigilar 61-90d":"<span class=\\"pill p-info\\">Vigilar 61-90d</span>","Recurrente":"<span class=\\"pill p-muted\\">Facturación parcial</span>","Riesgo Alto":"<span class=\\"pill p-risk\\">Riesgo Alto</span>"}};return map[s]||"<span class=\\"pill p-muted\\">"+s+"</span>";}}
function toggleDrill(id,btn){{var el=document.getElementById(id);var open=el.style.display==="block";el.style.display=open?"none":"block";btn.textContent=open?"Ver proyectos \u25be":"Ocultar \u25b4";}}
function buildSegment(containerId,seg){{var container=document.getElementById(containerId);var title=seg.title,nPry=seg.n,proj=seg.proj,serv=seg.serv;var pryList=seg.pry||[],extraCols=seg.ec||[],isSinOC=seg.isSinOC||false;var uid="dr_"+containerId+"_"+title.replace(/\\W+/g,"_").substring(0,20);var hasDrill=pryList.length>0;var mgPP=calcMg(proj.vp,proj.cp),mgPR=calcMgReal(proj.fac,proj.cr);var mgSP=calcMg(serv.vp,serv.cp),mgSR=calcMgReal(serv.fac,serv.cr);var hasEst=extraCols.indexOf("est")!==-1;var hasFecha=extraCols.indexOf("fecha")!==-1;var hasFechaReal=extraCols.indexOf("fecha_real")!==-1;var hasSem=extraCols.indexOf("sem")!==-1;var drillHtml="";if(hasDrill){{var thExtra="";if(hasEst)thExtra+="<th>Estatus impl.</th>";if(hasFecha)thExtra+="<th>Fecha fin Plan.</th>";if(hasFechaReal)thExtra+="<th>Fecha fin Real</th>";if(hasSem)thExtra+="<th>Riesgo</th>";var rowsHtml="";for(var i=0;i<pryList.length;i++){{var r=pryList[i];var tdExtra="";if(hasEst)tdExtra+="<td>"+(r.est||"--")+"</td>";if(hasFecha)tdExtra+="<td style=\\"white-space:nowrap;font-size:11px;color:var(--text3)\\">"+(r.fecha||"--")+"</td>";if(hasFechaReal){{var fr=r.fecha_real||"--";var frStyle=fr!=="--"?"color:var(--green);font-weight:500":"color:var(--text3)";tdExtra+="<td style=\\"white-space:nowrap;font-size:11px;"+frStyle+"\\">"+fr+"</td>";}}if(hasSem)tdExtra+="<td>"+semPill(r.sem||"--")+"</td>";rowsHtml+="<tr><td class=\\"mono\\">"+r.p+"</td><td class=\\"cli\\">"+r.c+"</td><td class=\\"nom\\">"+r.n+"</td>"+tdExtra+"<td class=\\"r\\">"+fmt(r.vp/M,2)+"</td><td class=\\"r\\">"+fmt(r.fac/M,2)+"</td>"+"<td class=\\"pend\\">"+fmt(r.pend/M,2)+"</td></tr>";}}drillHtml="<div class=\\"drill-wrap\\" id=\\""+uid+"\\"><table class=\\"drill-table\\"><thead><tr>"+"<th>PRY</th><th>Cliente</th><th>Nombre</th>"+thExtra+"<th class=\\"r\\">Venta prev.</th><th class=\\"r\\">Facturado</th><th class=\\"r\\">Pendiente</th>"+"</tr></thead><tbody>"+rowsHtml+"</tbody></table></div>";}}var riskBanner="";if(isSinOC&&nPry>0){{riskBanner="<div class=\\"risk-banner\\"><span style=\\"font-size:14px;flex-shrink:0\\">!</span>"+"<span><strong>Riesgo Alto — Sin facturación posible:</strong> estos proyectos no pueden facturarse hasta obtener la OC o contrato firmado. Requieren acción comercial inmediata.</span></div>";}}var badgeCls=isSinOC?"b-red":"b-gray";var riskBadge=(isSinOC&&nPry>0)?" <span class=\\"badge b-risk\\">Sin OC — No facturable</span>":"";var expandBtn=hasDrill?"<button class=\\"expand-btn\\" onclick=\\"toggleDrill('"+uid+"',this)\\">Ver proyectos \u25be</button>":"";var block=document.createElement("div");block.className="seg"+(isSinOC?" risk-high":"");block.innerHTML="<div class=\\"seg-hdr\\"><div><span class=\\"seg-title\\">"+title+"</span> "+"<span class=\\"badge "+badgeCls+"\\">"+nPry+" proyectos</span>"+riskBadge+"</div>"+"<div>"+expandBtn+"</div></div>"+"<table class=\\"seg-table\\"><thead><tr>"+"<th>Tipo</th><th class=\\"r\\">Venta prevista</th><th class=\\"r\\">Costo previsto</th>"+"<th class=\\"r\\">Mg previsto</th><th class=\\"r\\">Facturado</th>"+"<th class=\\"r\\">Costo real</th><th class=\\"r\\">Mg real</th></tr></thead><tbody>"+"<tr><td><span class=\\"type-tag\\">Proyecto</span></td>"+"<td class=\\"r\\">"+fmt(proj.vp/M)+"</td><td class=\\"r\\">"+fmt(proj.cp/M)+"</td>"+"<td class=\\"r\\">"+mgPill(mgPP)+"</td>"+"<td class=\\"r\\">"+fmt(proj.fac/M)+"</td><td class=\\"r\\">"+fmt(proj.cr/M)+"</td>"+"<td class=\\"r\\">"+mgPill(mgPR)+"</td></tr>"+"<tr><td><span class=\\"type-tag\\">Servicio</span></td>"+"<td class=\\"r\\">"+fmt(serv.vp/M)+"</td><td class=\\"r\\">"+fmt(serv.cp/M)+"</td>"+"<td class=\\"r\\">"+mgPill(mgSP)+"</td>"+"<td class=\\"r\\">"+fmt(serv.fac/M)+"</td><td class=\\"r\\">"+fmt(serv.cr/M)+"</td>"+"<td class=\\"r\\">"+mgPill(mgSR)+"</td></tr>"+"</tbody></table>"+riskBanner+drillHtml;container.appendChild(block);}}
function renderYear(yr){{var segs=DATA[yr];var container=document.getElementById("seg"+yr);if(!container||container.childElementCount>0)return;for(var i=0;i<segs.length;i++)buildSegment("seg"+yr,segs[i]);}}
function switchYr(yr,btn){{var btns=document.querySelectorAll(".yr-btn");for(var i=0;i<btns.length;i++)btns[i].classList.remove("active");btn.classList.add("active");var panels=document.querySelectorAll(".yr-panel");for(var i=0;i<panels.length;i++)panels[i].classList.remove("active");document.getElementById("p"+yr).classList.add("active");renderYear(yr);}}
renderYear("2026");
</script>
</body>
</html>"""

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[1/4] Leyendo {EXCEL_FILE}...")
    import warnings; warnings.filterwarnings("ignore")
    sheets = pd.read_excel(EXCEL_FILE, sheet_name=None, header=None)

    all_summary = {}; all_pry = {}; all_kpis = {}
    for yr in YEARS:
        if yr not in sheets:
            print(f"   Hoja {yr} no encontrada, omitiendo")
            continue
        print(f"[2/4] Procesando {yr} ({sheets[yr].shape[0]} filas)...")
        all_summary[yr], all_pry[yr] = extract(sheets[yr])
        all_kpis[yr] = kpi(all_summary[yr])

    print("[3/4] Generando DATA JS...")
    data_js = build_data_js(all_summary, all_pry)

    print("[4/4] Escribiendo HTML...")
    logo_b64 = load_logo()
    html     = build_html(logo_b64, data_js, all_kpis)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    size = len(html) / 1024
    print(f"\nListo: {OUTPUT_FILE} ({size:.0f} KB)")
    print(f"   Corte: {CORTE_LABEL}")
    for yr in YEARS:
        k = all_kpis.get(yr, {})
        print(f"   {yr}: n={k.get('n',0)} vp=${k.get('vp',0):.1f}M fac=${k.get('fac',0):.1f}M")
