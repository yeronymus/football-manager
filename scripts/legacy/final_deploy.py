
import pty
import os
import sys
import select

LOG_FILE = "/home/yeronym/Documents/fmBot/football-manager/deploy_log.txt"
with open(LOG_FILE, "w") as f: f.write("Starting deploy...\n")

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
        f.flush()

PASSWORD = "Omnibus1"
FILES = [
    "app/bot/utils.py",
    "app/bot/admin_handlers.py",
    "app/services/game_service.py",
    "app/scheduler/tasks.py",
    "app/web/index.html"
]

def run_cmd(cmd_list):
    pid, fd = pty.fork()
    if pid == 0:
        os.execlp(cmd_list[0], *cmd_list)
    else:
        out = b""
        while True:
            try:
                r, _, _ = select.select([fd], [], [], 0.5)
                if fd in r:
                    chunk = os.read(fd, 1024)
                    if not chunk: break
                    out += chunk
                    log(chunk.decode(errors='ignore'))
                    if b"password:" in chunk.lower():
                        os.write(fd, PASSWORD.encode() + b"\n")
            except OSError: break
            if os.waitpid(pid, os.WNOHANG) != (0, 0): break
        return out.decode(errors='ignore')

for f in FILES:
    log(f"Deploying {f}...")
    # 1. SCP to /tmp
    run_cmd(["scp", "-o", "StrictHostKeyChecking=no", f, f"ubuntu@yernur-vm1.sin.cvut.cz:/tmp/{os.path.basename(f)}"])
    # 2. Docker CP
    run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", f"docker cp /tmp/{os.path.basename(f)} football-prod_app_1:/app/{f}"])

# 3. Restart
log("Restarting...")
run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", "docker restart -t 1 football-prod_app_1"])
log("Done.")
