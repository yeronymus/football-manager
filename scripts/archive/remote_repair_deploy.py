import pty
import os
import sys
import time
import select
import subprocess

SERVER_USER = "ubuntu"
SERVER_HOST = "yernur-vm1.sin.cvut.cz"
PASSWORD = "Omnibus1"
LOCAL_APP_PATH = "app"
REMOTE_PATH = "~/football-prod"

def run_local_command(command):
    print(f"Local EXEC: {command}")
    subprocess.run(command, shell=True, check=True)

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
        
        print(full_out.decode('utf-8', errors='ignore'))

def upload_file(local_file, remote_dest):
    print(f"Uploading {local_file} -> {remote_dest}")
    cmd_list = ["scp", "-o", "StrictHostKeyChecking=no", local_file, f"{SERVER_USER}@{SERVER_HOST}:{remote_dest}"]
    
    pid, fd = pty.fork()
    if pid == 0:
        os.execlp(cmd_list[0], *cmd_list)
    else:
        while True:
            try:
                r, _, _ = select.select([fd], [], [], 1)
                if fd in r:
                    output = os.read(fd, 1024)
                    if not output:
                        break
                    if b"password:" in output.lower():
                        os.write(fd, PASSWORD.encode() + b"\n")
            except OSError:
                break
            if os.waitpid(pid, os.WNOHANG) != (0, 0):
                break

if __name__ == "__main__":
    # 1. Compress local app
    run_local_command("tar -czf app_repair.tar.gz app")
    
    # 2. Upload
    upload_file("app_repair.tar.gz", REMOTE_PATH + "/app_repair.tar.gz")
    
    # 3. Remote unpack and restart
    cmds = [
        f"cd {REMOTE_PATH} && tar -xzf app_repair.tar.gz",
        f"cd {REMOTE_PATH} && rm app_repair.tar.gz",
        "docker restart football-prod_app_1",
        "sleep 5",
        "docker logs --tail 20 football-prod_app_1"
    ]
    for cmd in cmds:
        run_remote_command(cmd)
    
    # 4. Cleanup local
    run_local_command("rm app_repair.tar.gz")
