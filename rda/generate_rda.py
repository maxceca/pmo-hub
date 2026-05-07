#!/usr/bin/env python3
"""
CEN Systems — RDA Dashboard Generator (PMO Hub edition)
Lee datos de Snowflake (MUAMBA_EXTRACT.MUAMBA_API) y actualiza
el bloque de datos en pmo-hub/index.html

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
import re
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ── Rutas ────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent.parent     # raiz del repo pmo-hub
INDEX_HTML = ROOT / "index.html"

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

# ── Generar datos ─────────────────────────────────────────────────────
def build_rda_data():
    all_p = []
    for moneda in ["USD", "MXN"]:
        tabla = TABLAS[moneda]
        print(f"  Consultando {SF_DATABASE}.{SF_SCHEMA}.{tabla} …", flush=True)
        rows = _query_sf(tabla)
        for p in rows:
            if p["anio"] >= MIN_YEAR:
                copia = dict(p)
                copia["rda_moneda"] = moneda
                all_p.append(copia)
        print(f"  OK: {len([x for x in rows if x['anio']>=MIN_YEAR])} proyectos ({moneda})", flush=True)

    anios     = sorted({p["anio"]       for p in all_p if p["anio"]},      reverse=True)
    tipos     = sorted({p["tipo_venta"] for p in all_p if p["tipo_venta"]})
    estatuses = sorted({p["estatus"]    for p in all_p if p["estatus"]})

    # Hora de actualización (UTC-6 México)
    now_mx = datetime.now(timezone(timedelta(hours=-6)))
    updated = now_mx.strftime("%d %b %Y %H:%M h (CDMX)").lstrip("0")

    return {
        "total":     len(all_p),
        "proyectos": all_p,
        "catalogos": {"anios": anios, "tipos": tipos, "estatuses": estatuses},
        "updated":   updated,
    }

# ── Inyectar en index.html ────────────────────────────────────────────
def inject_data(data: dict):
    if not INDEX_HTML.exists():
        print(f"ERROR: No se encontró {INDEX_HTML}", file=sys.stderr)
        sys.exit(1)

    html = INDEX_HTML.read_text(encoding="utf-8")

    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    new_block = (
        "<!-- RDA_DATA_BEGIN -->\n"
        f'<script id="rda-data">var RDA_DATA={json_str};</script>\n'
        "<!-- RDA_DATA_END -->"
    )

    pattern = r"<!-- RDA_DATA_BEGIN -->.*?<!-- RDA_DATA_END -->"
    updated_html, n = re.subn(pattern, new_block, html, flags=re.DOTALL)

    if n == 0:
        print("ERROR: No se encontró el bloque <!-- RDA_DATA_BEGIN -->...<!-- RDA_DATA_END --> en index.html",
              file=sys.stderr)
        sys.exit(1)

    INDEX_HTML.write_text(updated_html, encoding="utf-8")
    print(f"  index.html actualizado ({len(data['proyectos'])} proyectos)", flush=True)

# ── Main ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 52)
    print("  RDA Dashboard Generator · CEN Systems PMO Hub")
    print(f"  Snowflake: {SF_DATABASE}.{SF_SCHEMA}")
    print(f"  Usuario:   {SF_USER}")
    print("=" * 52)

    if not SF_USER or not SF_PASSWORD:
        print("ERROR: Se requieren SNOWFLAKE_USER y SNOWFLAKE_PASSWORD", file=sys.stderr)
        sys.exit(1)

    print("Consultando Snowflake…")
    data = build_rda_data()
    print(f"Total proyectos: {data['total']}")

    print("Actualizando index.html…")
    inject_data(data)

    print(f"Listo. Actualizado: {data['updated']}")
