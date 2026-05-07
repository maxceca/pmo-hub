#!/usr/bin/env python3
"""
CEN Systems — RDA Dashboard Generator (PMO Hub edition)
Lee datos de Snowflake (MUAMBA_EXTRACT.MUAMBA_API) y genera
pmo-hub/rda/index.html  — página standalone del Dashboard RDA.

Uso:
  python rda/generate_rda.py          (desde la raiz del repo)

Variables de entorno requeridas:
  SNOWFLAKE_ACCOUNT   ej. a4736573681671-censystemsdb
  SNOWFLAKE_USER      ej. rda_dashboard
  SNOWFLAKE_PASSWORD  ej. RdaDashboard2024
  SNOWFLAKE_ROLE      ej. PM             (default: PM)
  SNOWFLAKE_WAREHOUSE ej. COMPUTE_WH     (default: COMPUTE_WH)
"""

import os
import sys
import json
import base64
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ── Rutas ────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent.parent     # raiz del repo pmo-hub
RDA_DIR    = ROOT / "rda"
OUTPUT     = RDA_DIR / "index.html"
LOGO_FILE  = ROOT / "assets" / "logo.png"

# ── Snowflake config ─────────────────────────────────────────────────
SF_ACCOUNT   = os.environ.get("SNOWFLAKE_ACCOUNT",   "a4736573681671-censystemsdb").strip()
SF_USER      = os.environ.get("SNOWFLAKE_USER",       "").strip()
SF_PASSWORD  = os.environ.get("SNOWFLAKE_PASSWORD",   "").strip()
SF_ROLE      = os.environ.get("SNOWFLAKE_ROLE",       "PM").strip()
SF_WAREHOUSE = os.environ.get("SNOWFLAKE_WAREHOUSE",  "COMPUTE_WH").strip()
SF_DATABASE  = "MUAMBA_EXTRACT"
SF_SCHEMA    = "MUAMBA_API"
TABLAS       = {"USD": "MUAMBA_RDA_USD", "MXN": "MUAMBA_RDA_MXN"}
MIN_YEAR     = "2023"

# ── Helpers ───────────────────────────────────────────────────────────
def _f(v):
    if v is None: return 0.0
    try: return float(str(v).replace(",", ""))
    except: return 0.0

def _s(v): return "" if v is None else str(v).strip()

def _year_from_pry(pry):
    try:
        aa = pry.split("-")[1][:2]
        return "20" + aa
    except Exception:
        return ""

# ── Logo ──────────────────────────────────────────────────────────────
def _logo_b64():
    if LOGO_FILE.exists():
        return base64.b64encode(LOGO_FILE.read_bytes()).decode()
    return ""

# ── Snowflake ─────────────────────────────────────────────────────────
def _get_conn():
    import snowflake.connector
    return snowflake.connector.connect(
        account   = SF_ACCOUNT,
        user      = SF_USER,
        password  = SF_PASSWORD,
        warehouse = SF_WAREHOUSE,
        database  = SF_DATABASE,
        schema    = SF_SCHEMA,
        role      = SF_ROLE,
    )

SQL_RDA = """
SELECT PROYECTO, NOMBRE, ESTATUS, SUCURSAL, NOMBRE_CLIENTE,
       UNIDAD_NEGOCIO, TIPO_VENTA, PORTAFOLIO, PM, AM,
       INGENIERO_PREVENTA, FECHA_CREACION, FECHA_INICIO, FECHA_FIN,
       FECHA_ULTIMA_FACTURA, SIGUIENTE_FACTURACION, MONTO_A_FACTURAR,
       VENTA_PREVISTA_TOTAL, FACTURADO_CON_NC,
       COSTO_PREVISTO_EQUIPO, COSTO_PREVISTO_SERVICIOS, COSTO_PREVISTO_MOI,
       COSTO_PREVISTO_MOD, COSTO_PREVISTO_GASTOS, COSTO_PREVISTO_OTROS, COSTO_PREVISTO_TOTAL,
       COSTO_REAL_EQUIPO_FACTURADO, COSTO_REAL_SERVICIOS, COSTO_REAL_MOI,
       COSTO_REAL_MOD, COSTO_REAL_GASTOS, COSTOS_REAL_OTROS, COSTO_REAL_TOTAL,
       MARGEN_PREVISTO
FROM {db}.{schema}.{table}
WHERE LOAD_DATE = (SELECT MAX(LOAD_DATE) FROM {db}.{schema}.{table})
"""

def _row_to_dict(row, cols):
    r = dict(zip(cols, row))
    pry  = _s(r.get("PROYECTO"))
    anio = _year_from_pry(pry)
    return {
        "proyecto":       pry,
        "nombre":         _s(r.get("NOMBRE")),
        "estatus":        _s(r.get("ESTATUS")),
        "sucursal":       _s(r.get("SUCURSAL")),
        "cliente":        _s(r.get("NOMBRE_CLIENTE")),
        "unidad_negocio": _s(r.get("UNIDAD_NEGOCIO")),
        "tipo_venta":     _s(r.get("TIPO_VENTA")),
        "portafolio":     _s(r.get("PORTAFOLIO")),
        "pm":             _s(r.get("PM")),
        "am":             _s(r.get("AM")),
        "preventa":       _s(r.get("INGENIERO_PREVENTA")),
        "fecha_creacion": _s(r.get("FECHA_CREACION")),
        "fecha_inicio":   _s(r.get("FECHA_INICIO")),
        "fecha_fin":      _s(r.get("FECHA_FIN")),
        "fecha_ult_fac":  _s(r.get("FECHA_ULTIMA_FACTURA")),
        "sig_facturacion":_s(r.get("SIGUIENTE_FACTURACION")),
        "monto_facturar": _f(r.get("MONTO_A_FACTURAR")),
        "anio":           anio,
        "venta_prevista": _f(r.get("VENTA_PREVISTA_TOTAL")),
        "facturado_nc":   _f(r.get("FACTURADO_CON_NC")),
        "cp_equipo":      _f(r.get("COSTO_PREVISTO_EQUIPO")),
        "cp_servicios":   _f(r.get("COSTO_PREVISTO_SERVICIOS")),
        "cp_moi":         _f(r.get("COSTO_PREVISTO_MOI")),
        "cp_mod":         _f(r.get("COSTO_PREVISTO_MOD")),
        "cp_gastos":      _f(r.get("COSTO_PREVISTO_GASTOS")),
        "cp_otros":       _f(r.get("COSTO_PREVISTO_OTROS")),
        "cp_total":       _f(r.get("COSTO_PREVISTO_TOTAL")),
        "cr_equipo":      _f(r.get("COSTO_REAL_EQUIPO_FACTURADO")),
        "cr_servicios":   _f(r.get("COSTO_REAL_SERVICIOS")),
        "cr_moi":         _f(r.get("COSTO_REAL_MOI")),
        "cr_mod":         _f(r.get("COSTO_REAL_MOD")),
        "cr_gastos":      _f(r.get("COSTO_REAL_GASTOS")),
        "cr_otros":       _f(r.get("COSTOS_REAL_OTROS")),
        "cr_total":       _f(r.get("COSTO_REAL_TOTAL")),
        "margen_prev":    _f(r.get("MARGEN_PREVISTO")),
    }

def _query_sf(tabla):
    sql = SQL_RDA.format(db=SF_DATABASE, schema=SF_SCHEMA, table=tabla)
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return [_row_to_dict(row, cols) for row in cur.fetchall()]
    finally:
        conn.close()

# ── Datos ─────────────────────────────────────────────────────────────
def build_rda_data():
    all_p = []
    for moneda in ["USD", "MXN"]:
        tabla = TABLAS[moneda]
        print(f"  Consultando {SF_DATABASE}.{SF_SCHEMA}.{tabla} ...", flush=True)
        rows = _query_sf(tabla)
        count = 0
        for p in rows:
            if p["anio"] >= MIN_YEAR:
                copia = dict(p)
                copia["rda_moneda"] = moneda
                all_p.append(copia)
                count += 1
        print(f"  OK: {count} proyectos ({moneda})", flush=True)

    anios     = sorted({p["anio"]       for p in all_p if p["anio"]},      reverse=True)
    tipos     = sorted({p["tipo_venta"] for p in all_p if p["tipo_venta"]})
    estatuses = sorted({p["estatus"]    for p in all_p if p["estatus"]})

    now_mx  = datetime.now(timezone(timedelta(hours=-6)))
    updated = now_mx.strftime("%d %b %Y %H:%M h (CDMX)").lstrip("0")

    return {
        "total":     len(all_p),
        "proyectos": all_p,
        "catalogos": {"anios": anios, "tipos": tipos, "estatuses": estatuses},
        "updated":   updated,
    }

# ── HTML Template ─────────────────────────────────────────────────────
def build_html(data: dict, logo_b64: str) -> str:
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    logo_tag = (f'<img src="data:image/png;base64,{logo_b64}" alt="CEN Systems">'
                if logo_b64 else "")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dashboard RDA · PMO Hub · CEN Systems</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
:root{{
  --g:#97D700;--bk:#101820;--gd:#717C7D;--gl:#919D9D;
  --red:#D62828;--ora:#F77F00;--bg:#F5F5F5;--wh:#fff;
  --font:'Avenir','Open Sans',system-ui,sans-serif;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--font);background:var(--bg);color:var(--bk);font-size:14px}}

/* NAV */
nav.hub-nav{{display:flex;align-items:center;justify-content:space-between;
  padding:0 24px;height:52px;background:var(--bk);border-bottom:3px solid var(--g);
  position:sticky;top:0;z-index:9999;}}
.nav-logo{{display:flex;align-items:center;gap:10px;text-decoration:none;}}
.nav-logo img{{height:30px;width:auto;}}
.nav-title-group{{display:flex;flex-direction:column;line-height:1.2;}}
.nav-title{{font-size:13px;font-weight:700;color:#fff;letter-spacing:.02em;}}
.nav-sub{{font-size:10px;color:var(--g);font-weight:600;letter-spacing:.04em;text-transform:uppercase;}}
.nav-links{{display:flex;gap:4px;}}
.nav-links a{{font-size:12px;color:rgba(255,255,255,.75);text-decoration:none;
  padding:5px 12px;border-radius:6px;font-weight:500;transition:all .15s;}}
.nav-links a:hover{{background:rgba(255,255,255,.1);color:#fff;}}
.nav-links a.active{{background:rgba(151,215,0,.2);color:#fff;font-weight:600;}}

/* HEADER */
.dhead-band{{background:var(--bk);padding:14px 24px;display:flex;align-items:center;
  justify-content:space-between;border-bottom:2px solid rgba(151,215,0,.2);}}
.dhead-left .eyebrow{{font-size:10px;font-weight:600;color:var(--g);letter-spacing:.12em;
  text-transform:uppercase;margin-bottom:4px;}}
.dhead-left .title{{font-size:20px;font-weight:700;color:#fff;line-height:1;}}
.dhead-left .title span{{color:var(--g);}}
.dhead-right{{font-size:11px;color:var(--gl);text-align:right;line-height:1.7;}}
.dhead-right strong{{color:rgba(202,220,252,.7);}}

/* TOOLBAR */
.toolbar{{background:var(--wh);padding:9px 24px;display:flex;align-items:center;
  gap:10px;border-bottom:1px solid #e0e0e0;flex-wrap:wrap}}
.lbl{{font-size:10px;color:var(--gd);font-weight:700;text-transform:uppercase;letter-spacing:.4px;white-space:nowrap}}
select{{border:1px solid #d0d0d0;border-radius:4px;padding:5px 10px;
  font-family:var(--font);font-size:13px;color:var(--bk);background:var(--wh);outline:none}}
select:focus{{border-color:var(--g)}}
.sep{{width:1px;height:22px;background:#e0e0e0}}

/* LAYOUT */
.layout{{display:grid;grid-template-columns:1fr 680px;height:calc(100vh - 106px);overflow:hidden}}
.left{{overflow-y:auto;padding:16px 20px}}
.right{{border-left:3px solid var(--g);background:var(--wh);display:flex;flex-direction:column;
  box-shadow:-6px 0 28px rgba(0,0,0,.12);overflow:hidden}}

/* KPIs */
.krow{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:14px}}
.kpi{{background:var(--wh);border-radius:6px;padding:12px 15px;border-left:3px solid var(--g);
  box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.kpi.r{{border-left-color:var(--red)}}.kpi.gr{{border-left-color:var(--gd)}}
.kl{{font-size:9px;font-weight:700;color:var(--gd);text-transform:uppercase;letter-spacing:.4px;margin-bottom:6px}}
.kmon{{display:flex;flex-direction:column;gap:3px}}
.kmon-row{{display:flex;align-items:baseline;justify-content:space-between;gap:6px}}
.kmon-label{{font-size:10px;font-weight:700;color:var(--gl);min-width:30px}}
.kmon-val{{font-size:15px;font-weight:700;line-height:1;text-align:right}}
.kmon-val.neg{{color:var(--red)}}
.ks{{font-size:10px;color:var(--gl);margin-top:5px;border-top:1px solid #f0f0f0;padding-top:4px}}

/* Charts */
.crow{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px}}
.card{{background:var(--wh);border-radius:6px;padding:14px 18px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.ct{{font-size:10px;font-weight:700;padding-bottom:5px;border-bottom:2px solid var(--g);display:inline-block;margin-bottom:10px}}
.cw{{position:relative;height:190px}}

/* Table */
.sbar{{display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap}}
.sfield{{display:flex;flex-direction:column;gap:3px;flex:1;min-width:160px}}
.sfield label{{font-size:10px;font-weight:700;color:var(--gd);text-transform:uppercase;letter-spacing:.4px}}
.si{{padding:6px 12px;border:1px solid #d0d0d0;border-radius:6px;font-size:13px;font-family:var(--font);outline:none;width:100%}}
.si:focus{{border-color:var(--g)}}
.cnt{{font-size:11px;color:var(--gd);white-space:nowrap;align-self:flex-end;padding-bottom:6px}}
.tw{{overflow-x:auto;border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
table.pt{{width:100%;border-collapse:collapse;font-size:12px;min-width:700px}}
table.pt th{{background:var(--bk);color:#fff;padding:8px 10px;text-align:left;
  font-size:10px;font-weight:700;white-space:nowrap;position:sticky;top:0;z-index:2;
  letter-spacing:.04em;text-transform:uppercase}}
table.pt td{{padding:6px 10px;border-bottom:1px solid #f0f0f0;white-space:nowrap}}
table.pt tr:nth-child(even){{background:#fafafa}}
table.pt tr:hover{{background:#f0fae0;cursor:pointer}}
table.pt tr.sel{{background:#e8f5c8!important}}
.pill{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:10px;font-weight:700}}
.pg{{background:#e8f5c8;color:#3d6b00}}.py{{background:#fff3cd;color:#856404}}
.pr{{background:#fde8e8;color:#8b1a1a}}.pgr{{background:#ebebeb;color:#555}}

/* Right panel */
.dempty{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
  color:var(--gl);padding:28px;text-align:center;gap:10px}}
.dempty .ico{{font-size:50px;opacity:.3}}
.dempty p{{font-size:12px;line-height:1.6;max-width:240px}}
.dhead{{background:var(--bk);color:#fff;padding:14px 18px;border-bottom:3px solid var(--g);flex-shrink:0}}
.dpry{{font-size:11px;color:var(--g);font-weight:700;letter-spacing:.5px;margin-bottom:4px}}
.dnom{{font-size:14px;font-weight:700;line-height:1.3}}
.dcli{{font-size:11px;color:var(--gl);margin-top:2px}}
.dchips{{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}}
.status-chip{{display:inline-flex;align-items:center;padding:3px 10px;border-radius:12px;font-size:10px;font-weight:700}}
.sc-g{{background:rgba(151,215,0,.2);color:var(--g);border:1px solid rgba(151,215,0,.4)}}
.sc-r{{background:rgba(214,40,40,.2);color:#ff8080;border:1px solid rgba(214,40,40,.35)}}
.sc-y{{background:rgba(247,127,0,.2);color:#f7b731;border:1px solid rgba(247,127,0,.35)}}
.sc-gr{{background:rgba(145,157,157,.12);color:var(--gl);border:1px solid rgba(145,157,157,.25)}}
.hero{{background:linear-gradient(135deg,#182028 0%,#242f38 100%);
  padding:16px 18px;border-bottom:3px solid var(--g);flex-shrink:0}}
.hero-row{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}}
.hero-num{{text-align:center}}
.hero-label{{font-size:9px;color:var(--gl);text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px}}
.hero-val{{font-size:22px;font-weight:700;color:#fff;line-height:1;font-variant-numeric:tabular-nums}}
.hero-val.ok{{color:var(--g)}}.hero-val.bad{{color:#ff6b6b}}
.hero-bar{{height:6px;background:rgba(255,255,255,.12);border-radius:3px;overflow:hidden;margin-bottom:7px}}
.hero-fill{{height:100%;border-radius:3px;background:var(--g);transition:width .6s}}
.hero-fill.bad{{background:var(--red)}}
.hero-meta{{display:flex;justify-content:space-between;font-size:11px;color:var(--gl)}}
.dbod{{flex:1;overflow-y:auto;padding:14px}}
.dsec{{margin-bottom:16px}}
.dttl{{font-size:9px;font-weight:700;color:var(--gd);text-transform:uppercase;letter-spacing:.6px;
  margin-bottom:8px;padding-bottom:4px;border-bottom:2px solid var(--g)}}
.dgrid{{display:grid;grid-template-columns:1fr 1fr;gap:5px}}
.di{{font-size:12px;padding:5px 6px;background:#f9f9f9;border-radius:4px}}
.di .ll{{color:var(--gd);font-size:9px;margin-bottom:2px}}
.di .vv{{font-weight:600;color:var(--bk)}}
.rubro-row{{padding:9px 0;border-bottom:1px solid #eee}}
.rubro-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.rubro-name{{font-size:12px;font-weight:700;color:var(--bk)}}
.rubro-badge{{font-size:9px;font-weight:700;padding:2px 7px;border-radius:4px}}
.rubro-nums{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-bottom:5px}}
.rn{{text-align:center;padding:4px 3px;background:#f5f5f5;border-radius:4px}}
.rn .rl{{font-size:9px;color:var(--gd);text-transform:uppercase;letter-spacing:.3px;margin-bottom:2px}}
.rn .rv{{font-size:12px;font-weight:700;font-variant-numeric:tabular-nums}}
.rubro-bar{{height:4px;background:#e0e0e0;border-radius:2px;overflow:hidden}}
.rf{{height:100%;border-radius:2px;transition:width .5s}}
.rf-g{{background:var(--g)}}.rf-r{{background:var(--red)}}
.rubro-total{{margin-top:12px;background:#f0f0f0;border-radius:7px;padding:12px 14px}}
.rt-row{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-top:8px}}
.rt-cell{{text-align:center}}
.rt-label{{font-size:9px;color:var(--gd);text-transform:uppercase;letter-spacing:.4px;margin-bottom:3px}}
.rt-val{{font-size:18px;font-weight:700;font-variant-numeric:tabular-nums}}
.badge{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:9px;font-weight:700}}
.bok{{background:#e8f5c8;color:#3d6b00}}.bw{{background:#fff3cd;color:#856404}}.bb{{background:#fde8e8;color:#8b1a1a}}
.xbtn{{float:right;background:none;border:none;color:var(--gl);font-size:18px;cursor:pointer;line-height:1;margin-top:-2px}}
.xbtn:hover{{color:var(--bk)}}
.hid{{display:none!important}}

footer{{background:var(--wh);border-top:1px solid #e0e0e0;padding:8px 24px;
  text-align:center;color:var(--gl);font-size:10px}}
</style>
</head>
<body>

<nav class="hub-nav">
  <a href="../" class="nav-logo">
    {logo_tag}
    <div class="nav-title-group">
      <div class="nav-title">PMO Hub</div>
      <div class="nav-sub">CEN Systems</div>
    </div>
  </a>
  <div class="nav-links">
    <a href="../">Hub</a>
    <a href="../portafolio/">Portafolio</a>
    <a href="../ocupacion/">Ocupacion</a>
    <a href="../kpis/">KPIs</a>
    <a href="./" class="active">RDA</a>
  </div>
</nav>

<div class="dhead-band">
  <div class="dhead-left">
    <div class="eyebrow">Datos desde Snowflake &middot; MUAMBA_EXTRACT</div>
    <div class="title">Dashboard <span>RDA</span></div>
  </div>
  <div class="dhead-right">
    <div>Ultima actualizacion</div>
    <div><strong id="updatedLbl">{data['updated']}</strong></div>
  </div>
</div>

<div class="toolbar">
  <span class="lbl">Ano</span>
  <select id="sAnio" onchange="applyF()"><option value="">Todos</option></select>
  <span class="lbl">Estatus</span>
  <select id="sEst" onchange="applyF()"><option value="">Todos</option></select>
  <span class="lbl">Tipo Venta</span>
  <select id="sTipo" onchange="applyF()"><option value="">Todos</option></select>
  <div class="sep"></div>
  <span class="lbl">Moneda</span>
  <select id="sMon" onchange="applyF()">
    <option value="">Todas</option>
    <option value="USD">USD</option>
    <option value="MXN">MXN</option>
  </select>
</div>

<div class="layout">
  <div class="left">
    <div class="krow" id="krow"></div>
    <div class="crow">
      <div class="card">
        <div class="ct">Venta Prevista vs Facturado c/NC &middot; Top 12 USD</div>
        <div class="cw"><canvas id="cvVenta"></canvas></div>
      </div>
      <div class="card">
        <div class="ct">Costo Previsto vs Real &middot; por concepto USD</div>
        <div class="cw"><canvas id="cvCostos"></canvas></div>
      </div>
    </div>
    <div class="card">
      <div class="sbar">
        <div class="sfield">
          <label>Numero de PRY</label>
          <input class="si" id="bPry" type="text" placeholder="ej. 00282..." oninput="renderTbl()">
        </div>
        <div class="sfield">
          <label>Cliente</label>
          <input class="si" id="bCli" type="text" placeholder="ej. COLMEX..." oninput="renderTbl()">
        </div>
        <span class="cnt" id="cnt"></span>
      </div>
      <div class="tw">
        <table class="pt">
          <thead><tr>
            <th>Proyecto</th><th>Nombre</th><th>Cliente</th>
            <th>Tipo Venta</th><th>Estatus</th><th>Mon.</th><th>PM</th><th>Ano</th>
          </tr></thead>
          <tbody id="tbody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="right" id="rp">
    <div class="dempty" id="demp">
      <div class="ico">📋</div>
      <p>Selecciona un proyecto de la tabla para ver el detalle financiero y las desviaciones por rubro</p>
    </div>
    <div id="dcont" class="hid" style="display:flex;flex-direction:column;height:100%;overflow:hidden">
      <div class="dhead">
        <button class="xbtn" onclick="closeDet()">&#x2715;</button>
        <div class="dpry" id="dpry"></div>
        <div class="dnom" id="dnom"></div>
        <div class="dcli" id="dcli"></div>
        <div class="dchips" id="dchips"></div>
      </div>
      <div class="hero" id="dhero"></div>
      <div class="dbod">
        <div class="dsec">
          <div class="dttl">Informacion general</div>
          <div class="dgrid" id="dinfo"></div>
        </div>
        <div class="dsec">
          <div class="dttl">Costos Previstos vs Reales Facturados &middot; por concepto</div>
          <div id="dconc"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<footer>
  <strong>CEN Systems S.A. de C.V.</strong> &nbsp;&middot;&nbsp; Cisco Gold Partner &nbsp;&middot;&nbsp;
  Dashboard RDA &nbsp;&middot;&nbsp; <a href="../" style="color:var(--g);text-decoration:none">PMO Hub</a>
</footer>

<script>
const RDA_DATA = {json_str};
const G='#97D700',BK='#101820',GD='#717C7D',GL='#919D9D',RED='#D62828';
const CONC=[{{k:'equipo',l:'Equipo'}},{{k:'servicios',l:'Servicios'}},
            {{k:'moi',l:'MOI'}},{{k:'mod',l:'MOD'}},{{k:'gastos',l:'Gastos'}},{{k:'otros',l:'Otros'}}];
let all=RDA_DATA.proyectos, sel=null, chV=null, chC=null;

const f=(n,d=2)=>n==null||isNaN(n)?'—':Number(n).toLocaleString('es-MX',{{minimumFractionDigits:d,maximumFractionDigits:d}});
const fp=n=>!isFinite(n)?'—':(n*100).toFixed(1)+'%';
const sumM=(arr,k,m)=>arr.filter(p=>p.rda_moneda===m).reduce((s,p)=>s+(p[k]||0),0);

function fillSels(){{
  const cat=RDA_DATA.catalogos;
  [['sAnio',cat.anios,'Todos'],['sEst',cat.estatuses,'Todos'],['sTipo',cat.tipos,'Todos']]
  .forEach(([id,items,ph])=>{{
    const s=document.getElementById(id);
    s.innerHTML=`<option value="">${{ph}}</option>`+items.map(x=>`<option>${{x}}</option>`).join('');
  }});
}}

function filtered(){{
  const a=document.getElementById('sAnio').value;
  const e=document.getElementById('sEst').value;
  const t=document.getElementById('sTipo').value;
  const m=document.getElementById('sMon').value;
  return all.filter(p=>(!a||p.anio===a)&&(!e||p.estatus===e)&&(!t||p.tipo_venta===t)&&(!m||p.rda_moneda===m));
}}

function applyF(){{renderAll();}}
function renderAll(){{const d=filtered();renderKPIs(d);renderChV(d);renderChC(d);renderTbl();}}

function kpiCard(label,cls,usd,mxn,sub){{
  const nu=usd<0,nm=mxn<0;
  return `<div class="kpi ${{cls}}">
    <div class="kl">${{label}}</div>
    <div class="kmon">
      <div class="kmon-row"><span class="kmon-label">USD</span>
        <span class="kmon-val${{nu?' neg':''}}">${{f(usd)}}</span></div>
      <div class="kmon-row"><span class="kmon-label">MXN</span>
        <span class="kmon-val${{nm?' neg':''}}">${{f(mxn)}}</span></div>
    </div>
    ${{sub?`<div class="ks">${{sub}}</div>`:''}}
  </div>`;
}}

function renderKPIs(d){{
  const vpU=sumM(d,'venta_prevista','USD'),vpM=sumM(d,'venta_prevista','MXN');
  const fnU=sumM(d,'facturado_nc','USD'),fnM=sumM(d,'facturado_nc','MXN');
  const cpU=sumM(d,'cp_total','USD'),cpM=sumM(d,'cp_total','MXN');
  const crU=sumM(d,'cr_total','USD'),crM=sumM(d,'cr_total','MXN');
  const pU=vpU>0?fnU/vpU:0,pM=vpM>0?fnM/vpM:0;
  const vcU=crU-cpU,vcM=crM-cpM;
  const nP=d.length,nU=d.filter(p=>p.rda_moneda==='USD').length,nM=d.filter(p=>p.rda_moneda==='MXN').length;
  document.getElementById('krow').innerHTML=
    kpiCard('Venta Prevista','',vpU,vpM,`${{nP}} proyectos \xb7 ${{nU}} USD / ${{nM}} MXN`)+
    kpiCard('Facturado con NC','',fnU,fnM,`USD ${{fp(pU)}} \xb7 MXN ${{fp(pM)}}`)+
    kpiCard('Costo Previsto','gr',cpU,cpM,'')+
    kpiCard('Costo Real Facturado','gr',crU,crM,'')+
    kpiCard('Variacion Costo',vcU>0||vcM>0?'r':'',vcU,vcM,'Prev. vs Real');
}}

function renderChV(d){{
  const top=[...d].filter(p=>p.rda_moneda==='USD'&&(p.venta_prevista>0||p.facturado_nc>0))
    .sort((a,b)=>b.venta_prevista-a.venta_prevista).slice(0,12);
  if(chV)chV.destroy();
  chV=new Chart(document.getElementById('cvVenta'),{{type:'bar',data:{{
    labels:top.map(p=>p.proyecto),
    datasets:[
      {{label:'Venta Prev.',data:top.map(p=>p.venta_prevista),backgroundColor:GD,borderRadius:3}},
      {{label:'Fac. c/NC',data:top.map(p=>p.facturado_nc),backgroundColor:G,borderRadius:3}}
    ]}},options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{position:'top',labels:{{font:{{size:10}}}}}},title:{{display:false}}}},
    scales:{{
      x:{{ticks:{{font:{{size:8}},maxRotation:45}},grid:{{color:'rgba(0,0,0,.04)'}}}},
      y:{{ticks:{{font:{{size:9}},callback:v=>v>=1e6?(v/1e6).toFixed(1)+'M':v>=1e3?(v/1e3).toFixed(0)+'K':v}},grid:{{color:'rgba(0,0,0,.04)'}}}}
    }}}}}});
}}

function renderChC(d){{
  const dU=d.filter(p=>p.rda_moneda==='USD');
  if(chC)chC.destroy();
  chC=new Chart(document.getElementById('cvCostos'),{{type:'bar',data:{{
    labels:CONC.map(c=>c.l),
    datasets:[
      {{label:'Costo Prev.',data:CONC.map(c=>dU.reduce((s,p)=>s+(p['cp_'+c.k]||0),0)),backgroundColor:GD,borderRadius:3}},
      {{label:'Real Fac.',data:CONC.map(c=>dU.reduce((s,p)=>s+(p['cr_'+c.k]||0),0)),backgroundColor:G,borderRadius:3}}
    ]}},options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{position:'top',labels:{{font:{{size:10}}}}}}}},
    scales:{{
      x:{{ticks:{{font:{{size:10}}}},grid:{{color:'rgba(0,0,0,.04)'}}}},
      y:{{ticks:{{font:{{size:9}},callback:v=>v>=1e6?(v/1e6).toFixed(1)+'M':v>=1e3?(v/1e3).toFixed(0)+'K':v}},grid:{{color:'rgba(0,0,0,.04)'}}}}
    }}}}}});
}}

function renderTbl(){{
  const qP=document.getElementById('bPry').value.toLowerCase();
  const qC=document.getElementById('bCli').value.toLowerCase();
  const d=filtered().filter(p=>
    (!qP||p.proyecto.toLowerCase().includes(qP))&&
    (!qC||p.cliente.toLowerCase().includes(qC)));
  document.getElementById('cnt').textContent=d.length+' proyectos';
  const rows=d.map(p=>{{
    const ec=p.estatus&&p.estatus.toLowerCase().includes('activ')?'pg':
             p.estatus&&p.estatus.toLowerCase().includes('cerr')?'pgr':'py';
    const mc=p.rda_moneda==='USD'?'pg':'py';
    const s=sel===p.proyecto?'sel':'';
    const nm=p.nombre&&p.nombre.length>28?p.nombre.slice(0,28)+'...':p.nombre||'';
    const cl=p.cliente&&p.cliente.length>22?p.cliente.slice(0,22)+'...':p.cliente||'';
    const pm=p.pm?(p.pm.split(' ').slice(0,2).join(' ')):'—';
    return `<tr class="${{s}}" onclick="selPry('${{(p.proyecto||'').replace(/'/g,"\\'")}}')" >
      <td><strong>${{p.proyecto||''}}</strong></td>
      <td title="${{p.nombre||''}}">${{nm}}</td>
      <td title="${{p.cliente||''}}">${{cl}}</td>
      <td>${{p.tipo_venta||''}}</td>
      <td><span class="pill ${{ec}}">${{p.estatus||''}}</span></td>
      <td><span class="pill ${{mc}}">${{p.rda_moneda||''}}</span></td>
      <td>${{pm}}</td>
      <td>${{p.anio||''}}</td>
    </tr>`;
  }});
  document.getElementById('tbody').innerHTML=rows.join('')||
    `<tr><td colspan="8" style="text-align:center;padding:20px;color:${{GL}}">Sin resultados</td></tr>`;
}}

function selPry(pry){{
  sel=pry;
  const p=all.find(x=>x.proyecto===pry);
  if(!p)return;
  renderTbl();
  const mon=p.rda_moneda||'';
  const vp=p.venta_prevista||0,fn=p.facturado_nc||0;
  const gap=fn-vp;
  const rawPct=vp>0?fn/vp:0;
  const barPct=Math.min(rawPct,1)*100;
  const pctCl=rawPct>=1?'ok':rawPct>=.5?'':'bad';
  const heroCl=rawPct>=1?'':'bad';

  document.getElementById('dpry').innerHTML=
    `${{p.proyecto||''}} &nbsp;<span class="pill ${{mon==='USD'?'pg':'py'}}">${{mon}}</span>`;
  document.getElementById('dnom').textContent=p.nombre||'';
  document.getElementById('dcli').textContent=p.cliente||'';

  const est=p.estatus||'';
  const estCls=est.toLowerCase().includes('activ')?'sc-g':est.toLowerCase().includes('cerr')?'sc-gr':'sc-y';
  document.getElementById('dchips').innerHTML=
    `<span class="status-chip ${{estCls}}">${{est}}</span>`+
    `<span class="status-chip sc-gr">Ano ${{p.anio||'—'}}</span>`+
    (p.pm?`<span class="status-chip sc-gr">PM: ${{p.pm.split(' ').slice(0,2).join(' ')}}</span>`:'');

  document.getElementById('dhero').innerHTML=`
    <div class="hero-row">
      <div class="hero-num"><div class="hero-label">Venta Prevista</div>
        <div class="hero-val">${{f(vp)}}</div></div>
      <div class="hero-num"><div class="hero-label">Facturado c/NC</div>
        <div class="hero-val ${{pctCl}}">${{f(fn)}}</div></div>
    </div>
    <div class="hero-bar"><div class="hero-fill ${{heroCl}}" style="width:${{barPct.toFixed(1)}}%"></div></div>
    <div class="hero-meta">
      <span>Cumplimiento: <strong style="color:${{rawPct>=.9?G:rawPct>=.5?'#f7b731':RED}};font-size:13px">${{fp(rawPct)}}</strong></span>
      <span>Gap: <strong style="color:${{gap<0?RED:G}}">${{gap>=0?'+':''}}</strong><strong style="color:${{gap<0?RED:G}}">${{f(gap)}}</strong></span>
    </div>`;

  document.getElementById('dinfo').innerHTML=[
    {{l:'Tipo Venta',v:p.tipo_venta||'—'}},{{l:'Unidad Neg.',v:p.unidad_negocio||'—'}},
    {{l:'AM',v:p.am||'—'}},{{l:'Portafolio',v:p.portafolio||'—'}},
    {{l:'Fecha Inicio',v:p.fecha_inicio||'—'}},{{l:'Fecha Fin',v:p.fecha_fin||'—'}},
    {{l:'Ult. Factura',v:p.fecha_ult_fac||'—'}},{{l:'Monto a Fac.',v:f(p.monto_facturar)+' '+mon}},
  ].map(x=>`<div class="di"><div class="ll">${{x.l}}</div><div class="vv">${{x.v}}</div></div>`).join('');

  let rubroHtml='',tCP=0,tCR=0;
  CONC.forEach(c=>{{
    const cp=p['cp_'+c.k]||0,cr=p['cr_'+c.k]||0,va=cr-cp;
    tCP+=cp;tCR+=cr;
    const barW=cp>0?Math.min(cr/cp,1.5)*100:cr>0?100:0;
    const barCls=va>cp*.05?'rf-r':'rf-g';
    const bc=va>cp*.10?'bb':va>cp*.02?'bw':'bok';
    const bt=va>cp*.10?'Excede':va>cp*.02?'Alerta':'OK';
    rubroHtml+=`
      <div class="rubro-row">
        <div class="rubro-header">
          <span class="rubro-name">${{c.l}}</span>
          <span class="rubro-badge ${{bc}}">${{bt}}</span>
        </div>
        <div class="rubro-nums">
          <div class="rn"><div class="rl">Previsto</div><div class="rv">${{f(cp)}}</div></div>
          <div class="rn"><div class="rl">Real Fac.</div>
            <div class="rv" style="color:${{va>0?RED:'inherit'}}">${{f(cr)}}</div></div>
          <div class="rn"><div class="rl">Variacion</div>
            <div class="rv" style="color:${{va>0?RED:'#3d6b00'}}">${{va>0?'+':''}}</div>
            <div class="rv" style="color:${{va>0?RED:'#3d6b00'}}">${{f(va)}}</div></div>
        </div>
        <div class="rubro-bar"><div class="rf ${{barCls}}" style="width:${{barW.toFixed(1)}}%"></div></div>
      </div>`;
  }});

  const tv=tCR-tCP;
  const tvCls=tv>tCP*.10?'bb':tv>0?'bw':'bok';
  const tvTxt=tv>tCP*.10?'Excede':tv>0?'Alerta':'OK';
  rubroHtml+=`
    <div class="rubro-total" style="border-left:4px solid ${{tv>0?RED:G}}">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:12px;font-weight:700;color:var(--bk)">TOTAL \xb7 ${{mon}}</span>
        <span class="rubro-badge ${{tvCls}}">${{tvTxt}}</span>
      </div>
      <div class="rt-row">
        <div class="rt-cell"><div class="rt-label">Costo Previsto</div>
          <div class="rt-val">${{f(tCP)}}</div></div>
        <div class="rt-cell"><div class="rt-label">Real Facturado</div>
          <div class="rt-val" style="color:${{tv>0?RED:'inherit'}}">${{f(tCR)}}</div></div>
        <div class="rt-cell"><div class="rt-label">Variacion</div>
          <div class="rt-val" style="color:${{tv>0?RED:'#3d6b00'}}">${{tv>0?'+':''}}</div>
          <div class="rt-val" style="color:${{tv>0?RED:'#3d6b00'}}">${{f(tv)}}</div></div>
      </div>
    </div>`;

  document.getElementById('dconc').innerHTML=rubroHtml;
  document.getElementById('demp').classList.add('hid');
  const dc=document.getElementById('dcont');
  dc.classList.remove('hid');
  dc.style.display='flex';
}}

function closeDet(){{
  sel=null;
  document.getElementById('demp').classList.remove('hid');
  const dc=document.getElementById('dcont');
  dc.classList.add('hid');
  dc.style.display='none';
  renderTbl();
}}

fillSels();
renderAll();
</script>
</body>
</html>"""

# ── Main ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 52)
    print("  RDA Dashboard Generator · CEN Systems PMO Hub")
    print(f"  Snowflake: {SF_DATABASE}.{SF_SCHEMA}")
    print(f"  Usuario:   {SF_USER}")
    print(f"  Salida:    {OUTPUT}")
    print("=" * 52)

    if not SF_USER or not SF_PASSWORD:
        print("ERROR: Se requieren SNOWFLAKE_USER y SNOWFLAKE_PASSWORD", file=sys.stderr)
        sys.exit(1)

    print("Consultando Snowflake...")
    data = build_rda_data()
    print(f"Total proyectos: {data['total']}")

    logo_b64 = _logo_b64()
    print(f"Logo: {'OK' if logo_b64 else 'no encontrado'}")

    print("Generando rda/index.html...")
    RDA_DIR.mkdir(parents=True, exist_ok=True)
    html = build_html(data, logo_b64)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Listo. {len(html):,} chars. Actualizado: {data['updated']}")
