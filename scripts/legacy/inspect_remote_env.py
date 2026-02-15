import pty
import os
import sys
import time
import select

LOG_FILE = "inspect_env_log.txt"
with open(LOG_FILE, "w") as f: f.write("Inspecting env...\n")

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
        f.flush()
    print(msg)

PASSWORD = "Omnibus1"

def run_cmd(cmd_list):
    log(f"Running: {' '.join(cmd_list)}")
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
        log(f"CMS Output: {output_str}")
        return output_str

# Run docker inspect
run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", "docker inspect football-prod_app_1"])

log("Done.")
