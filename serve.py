#!/usr/bin/env python3
"""Servidor local del PMO Hub — CEN Systems
Uso: python serve.py [puerto]
"""
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

BASE = Path(__file__).parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8090


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE), **kwargs)

    def log_message(self, fmt, *args):
        pass  # silencia el log HTTP


def main():
    print("=" * 50)
    print("  Censys PMO Hub — Servidor local")
    print(f"  Abre: http://localhost:{PORT}")
    print("  Ctrl+C para detener.")
    print("=" * 50)
    url = f"http://localhost:{PORT}"
    webbrowser.open(url)
    server = HTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")


if __name__ == "__main__":
    main()
