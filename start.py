#!/usr/bin/env python3
"""
Interactive startup: scans for nearby GSM cells, then launches
grgsm_livemon_headless + the web UI together.
"""

import os
import shutil
import signal
import socket
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEBUI = os.path.join(SCRIPT_DIR, "webui.py")
BANDS = ["GSM900", "DCS1800", "GSM850", "PCS1900"]


# ── helpers ──────────────────────────────────────────────────────────────────

def _hr():
    print("  " + "─" * 46)


def _ask(prompt, default):
    try:
        val = input(f"  {prompt} [{default}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return val or str(default)


def _pick(prompt, count, default=1):
    """Ask for a number 1–count; return it."""
    while True:
        raw = _ask(prompt, default)
        try:
            n = int(raw)
            if 1 <= n <= count:
                return n
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {count}.")


def _port_free(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


def _kill(procs):
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    for p in procs:
        try:
            p.wait(timeout=4)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


# ── steps ────────────────────────────────────────────────────────────────────

def banner():
    print()
    print("  IMSI Catcher — Startup")
    _hr()
    print()


def check_tools():
    missing = [t for t in ("grgsm_livemon_headless", "grgsm_scanner")
               if not shutil.which(t)]
    if missing:
        print(f"  Missing tools: {', '.join(missing)}")
        print("  Install gr-gsm first (apt install gr-gsm).")
        sys.exit(1)


def ask_webui_port():
    print("[1/3]  Web UI port\n")
    while True:
        raw = _ask("HTTP port", 8080)
        try:
            port = int(raw)
            if not (1024 <= port <= 65535):
                raise ValueError
        except ValueError:
            print("  Enter a number between 1024 and 65535.")
            continue
        if not _port_free(port):
            print(f"  Port {port} is already in use — try another.")
            continue
        return port


def _parse_cell_line(line):
    # grgsm_scanner output: "ARFCN:  975, Freq:  924.0M, CID: 12345, LAC:   412, MCC: 208, MNC:  20, Pwr: -60"
    if "ARFCN:" not in line or "Freq:" not in line:
        return None
    try:
        parts = {}
        for chunk in line.split(","):
            if ":" in chunk:
                k, _, v = chunk.partition(":")
                parts[k.strip()] = v.strip()
        freq_str = parts.get("Freq", "0")
        if freq_str.endswith("M"):
            freq_hz = float(freq_str[:-1]) * 1e6
        elif freq_str.endswith("G"):
            freq_hz = float(freq_str[:-1]) * 1e9
        elif freq_str.endswith("k"):
            freq_hz = float(freq_str[:-1]) * 1e3
        else:
            freq_hz = float(freq_str)
        return {
            "arfcn": int(parts.get("ARFCN", 0)),
            "freq":  freq_hz,
            "freq_str": freq_str,
            "cid":   int(parts.get("CID", 0)),
            "lac":   int(parts.get("LAC", 0)),
            "mcc":   parts.get("MCC", "?").strip(),
            "mnc":   parts.get("MNC", "?").strip(),
            "power": float(parts.get("Pwr", "-999")),
        }
    except Exception:
        return None


def _run_scan(band):
    print(f"\n  Scanning {band} — this takes 30 – 120 seconds...")
    try:
        result = subprocess.run(
            ["grgsm_scanner", "-b", band],
            capture_output=True, text=True, timeout=180,
        )
        cells = [c for c in (_parse_cell_line(l) for l in (result.stdout + result.stderr).splitlines()) if c]
        return sorted(cells, key=lambda c: -c["power"])
    except subprocess.TimeoutExpired:
        print("  Scan timed out.")
        return []
    except KeyboardInterrupt:
        print("  Scan cancelled.")
        return []
    except Exception as exc:
        print(f"  Scan failed: {exc}")
        return []


def _show_cells(cells):
    header = f"  {'#':>3}  {'ARFCN':>5}  {'MHz':>9}  {'MCC/MNC':<8}  {'LAC':>5}  {'CID':>6}  {'dBm':>5}"
    print(f"\n  Found {len(cells)} cell(s):\n")
    print(header)
    print("  " + "─" * (len(header) - 2))
    for i, c in enumerate(cells, 1):
        mhz = c["freq"] / 1e6
        print(f"  {i:>3}  {c['arfcn']:>5}  {mhz:>9.3f}  "
              f"{c['mcc']}/{c['mnc']:<5}  {c['lac']:>5}  {c['cid']:>6}  {c['power']:>4.0f}")
    print()


def _ask_manual_freq():
    raw = _ask("Frequency (MHz)", "924.0")
    try:
        return float(raw) * 1e6
    except ValueError:
        print("  Invalid — using 924.0 MHz.")
        return 924.0e6


def ask_frequency():
    print("\n[2/3]  GSM frequency\n")
    print("    1)  Auto-scan for nearby cells (30 – 120 s)")
    print("    2)  Enter frequency manually (MHz)")
    print()
    mode = _pick("Mode", 2)

    if mode == 2:
        return _ask_manual_freq()

    # auto-scan: pick a band first
    print()
    for i, b in enumerate(BANDS, 1):
        print(f"    {i})  {b}")
    print()
    band = BANDS[_pick("Band", len(BANDS)) - 1]

    cells = _run_scan(band)

    if not cells:
        print("  No cells found. Enter frequency manually.")
        return _ask_manual_freq()

    _show_cells(cells)
    idx = _pick("Select cell (Enter for strongest)", len(cells)) - 1
    chosen = cells[idx]
    print(f"\n  → {chosen['freq'] / 1e6:.3f} MHz  (ARFCN {chosen['arfcn']},"
          f" MCC {chosen['mcc']} / MNC {chosen['mnc']})")
    return chosen["freq"]


def launch(freq_hz, http_port):
    print(f"\n[3/3]  Launching\n")

    # grgsm produces noisy radio diagnostics — suppress them
    print(f"  grgsm_livemon_headless  {freq_hz / 1e6:.3f} MHz → UDP 4729")
    grgsm = subprocess.Popen(
        ["grgsm_livemon_headless", "-f", str(freq_hz)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)

    # webui: inherit stderr so startup errors are visible
    print(f"  Web UI  →  http://127.0.0.1:{http_port}")
    webui = subprocess.Popen(
        [sys.executable, WEBUI, "--http-port", str(http_port)],
        stdout=subprocess.DEVNULL,
    )
    time.sleep(0.8)

    # webui failing is fatal
    if webui.poll() is not None:
        print(f"\n  webui.py exited immediately (code {webui.returncode}).")
        grgsm.terminate()
        sys.exit(1)

    # grgsm may have exited (no SDR plugged in yet) — warn but keep the UI up
    if grgsm.poll() is not None:
        print(f"\n  Warning: grgsm_livemon_headless exited (code {grgsm.returncode}).")
        print(f"  The web UI is still running — plug in the SDR and")
        print(f"  restart, or use 'Load Capture' to replay a saved file.")

    return grgsm, webui


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    banner()
    check_tools()

    http_port = ask_webui_port()
    freq_hz = ask_frequency()
    grgsm, webui = launch(freq_hz, http_port)

    print()
    _hr()
    print(f"  Open   http://127.0.0.1:{http_port}")
    print( "  Then click  'Start Capture'  in the browser.")
    print( "  Ctrl+C to stop everything.")
    _hr()
    print()

    def _shutdown(sig, _frame):
        print("\n  Stopping...")
        _kill([grgsm, webui])
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # webui dying is fatal; grgsm dying just means no live RF — warn once
    grgsm_warned = grgsm.poll() is not None  # may have already warned in launch()
    while True:
        if webui.poll() is not None:
            print(f"\n  webui.py exited (code {webui.returncode}).")
            _shutdown(None, None)
        if not grgsm_warned and grgsm.poll() is not None:
            grgsm_warned = True
            print(f"\n  grgsm_livemon_headless stopped.")
            print(f"  Web UI is still up at http://127.0.0.1:{http_port}")
        time.sleep(2)


if __name__ == "__main__":
    main()
