"""Sunucuyu başlatır ve hazır olduğunda tarayıcıyı açar.

Kullanım: python -m mizan.serve [--port 8000] [--no-browser]
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _open_when_ready(url: str, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.4)
    print(f"Sunucu {timeout:.0f} sn içinde yanıt vermedi; yukarıdaki hata mesajına bakın.")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="mizan-serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args(argv)

    url = f"http://{args.host}:{args.port}"
    if _port_in_use(args.host, args.port):
        print(f"{args.port} portu başka bir program tarafından kullanılıyor.")
        print(f"Başka bir port deneyin:  python -m mizan.serve --port {args.port + 1}")
        return 1

    import uvicorn

    env_file = Path(".env")
    print(f"\n  Mizan başlatılıyor: {url}\n  Durdurmak için: Ctrl+C\n")
    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run(
        "mizan.api:app",
        host=args.host,
        port=args.port,
        env_file=str(env_file) if env_file.exists() else None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
