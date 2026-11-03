"""
Runtime Container Liveness & Readiness Probe.
Replaces static AST parsing in Docker HEALTHCHECK with real HTTP & worker heartbeat checks.
"""
import os
import pathlib
import sys
import time
import urllib.request


def main() -> int:
    mode = os.getenv("PROBE_MODE", "api").lower()
    if mode == "worker":
        hb_file = pathlib.Path("/tmp/worker_heartbeat")
        if not hb_file.exists():
            print("Worker heartbeat file missing", file=sys.stderr)
            return 1
        try:
            last_beat = float(hb_file.read_text(encoding="utf-8").strip())
        except ValueError:
            print("Invalid worker heartbeat timestamp", file=sys.stderr)
            return 1
        if time.time() - last_beat > 60:
            print("Worker heartbeat stale (>60s)", file=sys.stderr)
            return 1
        return 0

    port = os.getenv("PORT", "8000")
    url = f"http://127.0.0.1:{port}/health/ready"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return 0 if resp.status == 200 else 1
    except Exception as exc:
        print(f"API readiness probe failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
