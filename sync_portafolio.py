#!/usr/bin/env python3
"""
sync_portafolio.py — CEN Systems PMO Hub
Descarga el index.html fresco de portafolio-cen, aplica branding del hub
y sobreescribe portafolio/index.html en pmo-hub.

Uso local : python sync_portafolio.py
En Actions: se invoca desde .github/workflows/sync-portafolio.yml
"""

import base64
import re
import sys
import urllib.request
from pathlib import Path

BASE      = Path(__file__).parent
LOGO_FILE = BASE / "assets" / "logo.png"

SOURCE_URL = (
    "https://raw.githubusercontent.com/maxceca/portafolio-cen/main/index.html"
)
OUTPUT = BASE / "portafolio" / "index.html"

# ── Logo ─────────────────────────────────────────────────────────────────────
def get_logo_b64():
    if LOGO_FILE.exists():
        return base64.b64encode(LOGO_FILE.read_bytes()).decode()
    return ""

# ── Hub nav HTML ─────────────────────────────────────────────────────────────
def shared_nav(logo_b64=""):
    logo_src = f"data:image/png;base64,{logo_b64}" if logo_b64 else "../assets/logo.png"
    return f"""<nav class="pmo-hub-nav">
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
</nav>"""

# ── CSS del hub nav (sin @import — la fuente se carga via <link>) ─────────────
SHARED_NAV_CSS = """\
/* === Censys PMO Hub - Nav compartido === */\
.pmo-hub-nav{display:flex;align-items:center;justify-content:space-between;\
  padding:0 24px;height:52px;background:#1a1a2e;border-bottom:3px solid #97D700;\
  position:sticky;top:0;z-index:9999;font-family:'Open Sans',sans-serif;\
  box-sizing:border-box;}\
.pmo-nav-logo{display:flex;align-items:center;gap:10px;text-decoration:none;}\
.pmo-nav-logo img{height:30px;width:auto;}\
.pmo-nav-title-group{display:flex;flex-direction:column;line-height:1.2;}\
.pmo-nav-title{font-size:13px;font-weight:700;color:#fff;letter-spacing:.02em;}\
.pmo-nav-sub{font-size:10px;color:#97D700;font-weight:600;letter-spacing:.04em;\
  text-transform:uppercase;}\
.pmo-nav-links{display:flex;gap:4px;}\
.pmo-nav-links a{font-size:12px;color:rgba(255,255,255,.75);text-decoration:none;\
  padding:5px 12px;border-radius:6px;font-weight:500;transition:all .15s;}\
.pmo-nav-links a:hover{background:rgba(255,255,255,.1);color:#fff;}\
@media(max-width:640px){.pmo-nav-links{display:none;}}
/* ══════════════════════════════════════════════════════ */
"""

# ── Transformaciones ─────────────────────────────────────────────────────────
def process_font(html):
    """Reemplaza Google Fonts por Open Sans."""
    html = re.sub(r'<link[^>]+fonts\.googleapis\.com[^>]*>', '', html)
    open_sans = (
        '<link href="https://fonts.googleapis.com/css2?family=Open+Sans'
        ':wght@300;400;500;600;700&display=swap" rel="stylesheet">'
    )
    return html.replace('</head>', f'  {open_sans}\n</head>', 1)

def process_font_family(html):
    for old in ['"DM Sans"', "'DM Sans'", '"Sora"', "'Sora'", 'DM Sans', 'Sora']:
        html = html.replace(old, 'Open Sans')
    return html

def inject_nav_css(html):
    return html.replace('<style>', '<style>\n' + SHARED_NAV_CSS, 1)

def replace_original_nav(html, nav_html):
    """Reemplaza el primer <nav>...</nav> del portafolio con el nav del hub."""
    return re.sub(r'<nav>.*?</nav>', nav_html, html, count=1, flags=re.DOTALL)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Descargando {SOURCE_URL} ...")
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"ERROR al descargar: {e}", file=sys.stderr)
        sys.exit(1)

    print("Aplicando branding del hub...")

    # 1. Color: #7DC242 -> #97D700
    html = html.replace('#7DC242', '#97D700').replace('7DC242', '97D700')

    # 2. Fuente
    html = process_font(html)
    html = process_font_family(html)

    # 3. Inyectar CSS del hub nav
    html = inject_nav_css(html)

    # 4. Reemplazar nav original con hub nav
    logo_b64 = get_logo_b64()
    hub_nav  = shared_nav(logo_b64)
    html = replace_original_nav(html, hub_nav)

    # 5. Titulo
    html = re.sub(
        r'<title>.*?</title>',
        '<title>Portafolio de Proyectos \u00b7 PMO Hub</title>',
        html, count=1
    )

    # 6. Escribir salida
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"OK: {OUTPUT}  ({len(html):,} chars)")

if __name__ == "__main__":
    main()
