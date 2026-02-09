import pty
import os
import sys
import time
import select
import subprocess

SERVER_USER = "ubuntu"
SERVER_HOST = "yernur-vm1.sin.cvut.cz"
PASSWORD = "Omnibus1"

def run_remote_command(command):
    print(f"Remote EXEC: {command}")
    cmd_list = ["ssh", "-o", "StrictHostKeyChecking=no", f"{SERVER_USER}@{SERVER_HOST}", command]
    
    pid, fd = pty.fork()
    if pid == 0:
        os.execlp(cmd_list[0], *cmd_list)
    else:
        full_out = b""
        while True:
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
                        full_out = b""
                    
            except OSError:
                break
            
            if os.waitpid(pid, os.WNOHANG) != (0, 0):
                try:
                    output = os.read(fd, 4096)
                    if output:
                        full_out += output
                except:
                    pass
                break
        
        return full_out.decode('utf-8', errors='ignore')

if __name__ == "__main__":
    # Get last 200 lines of logs
    logs = run_remote_command("docker logs --tail 200 football-prod_app_1")
    print(logs)
    
    # Check if there are any errors in the log
    if "error" in logs.lower() or "exception" in logs.lower():
        print("!!! Potential errors found in logs !!!")
