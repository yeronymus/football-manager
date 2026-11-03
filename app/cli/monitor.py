import os
import shlex
import subprocess
import sys


def monitor_remote_logs() -> None:
    """ Tail remote container logs via standard SSH configured strictly from environment variables."""
    host = os.environ.get("SSH_MONITOR_HOST", "").strip()
    user = os.environ.get("SSH_MONITOR_USER", "deploy").strip()
    port = os.environ.get("SSH_MONITOR_PORT", "22").strip()
    project_dir = os.environ.get("SSH_MONITOR_DIR", "~/sports-platform").strip()

    if not host:
        print(
            "ERROR: SSH_MONITOR_HOST is not set. "
            "Configure SSH_MONITOR_HOST (and optional SSH_MONITOR_USER / SSH_MONITOR_PORT / SSH_MONITOR_DIR) in your local .env.",
            file=sys.stderr,
        )
        sys.exit(1)

    remote_cmd = f"cd {shlex.quote(project_dir)} && docker compose logs --tail=100 app"
    ssh_cmd = ["ssh", "-p", port, f"{user}@{host}", remote_cmd]
    print(f"[INFO] Connecting to {user}@{host}:{port}...")
    subprocess.run(ssh_cmd, check=False)
