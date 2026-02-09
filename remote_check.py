import pty
import os
import sys
import time
import select

SERVER_USER = "ubuntu"
SERVER_HOST = "yernur-vm1.sin.cvut.cz"
PASSWORD = "Omnibus1"

def run_remote_command(command):
    cmd_list = ["ssh", "-o", "StrictHostKeyChecking=no", f"{SERVER_USER}@{SERVER_HOST}", command]
    print(f"[INFO] Connecting to {SERVER_HOST}...")
    
    pid, fd = pty.fork()
    if pid == 0:
        os.execlp(cmd_list[0], *cmd_list)
    else:
        full_out = b""
        while True:
            # simple read loop
            try:
                r, _, _ = select.select([fd], [], [], 1)
                if fd in r:
                    output = os.read(fd, 1024)
                    if not output:
                        break
                    
                    full_out += output
                    lower_out = full_out.lower()

                    if b"password:" in lower_out and b"omnibus1" not in lower_out:
                        os.write(fd, PASSWORD.encode() + b"\n")
                        # Clear buffer to avoid re-sending
                        full_out = b""
                    
            except OSError:
                break
            
            # Check if process exited
            if os.waitpid(pid, os.WNOHANG) != (0, 0):
                # Read remaining
                try:
                    output = os.read(fd, 4096)
                    if output:
                        full_out += output
                except:
                    pass
                break
        
        print(full_out.decode('utf-8', errors='ignore'))

if __name__ == "__main__":
    cmds = [
        "cat ~/football-prod/production.env",
        "docker logs --tail 100 football-prod_app_1",
        "docker exec football-prod_db_1 psql -U postgres -c '\\l'",
        "docker exec football-prod_db_1 psql -U postgres -d football -c 'SELECT count(*) FROM games;' || true"
    ]
    for cmd in cmds:
        print(f"\n--- EXEC: {cmd} ---")
        run_remote_command(cmd)
