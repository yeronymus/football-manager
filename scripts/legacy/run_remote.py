
import pty
import os
import sys
import time
import select

LOG_FILE = "run_remote_log.txt"
with open(LOG_FILE, "w") as f: f.write("Starting remote run...\n")

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
        f.flush()
    print(msg)

PASSWORD = "Omnibus1"
FILES = [
    "list_users_v2.py"
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
                    if b"password:" in chunk.lower():
                        os.write(fd, PASSWORD.encode() + b"\n")
            except OSError: break
            if os.waitpid(pid, os.WNOHANG) != (0, 0): break
        output_str = out.decode(errors='ignore')
        log(f"CMD Output: {output_str}")
        return output_str

# 1. Deploy Files
for f in FILES:
    log(f"Deploying {f}...")
    run_cmd(["scp", "-o", "StrictHostKeyChecking=no", f, f"ubuntu@yernur-vm1.sin.cvut.cz:/tmp/{os.path.basename(f)}"])
    run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", f"docker cp /tmp/{os.path.basename(f)} football-prod_app_1:/app/{f}"])

# 2. Run User List
log("Running list_users_v2.py...")
run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", "docker exec -t football-prod_app_1 python3 list_users_v2.py"])

log("Done.")
