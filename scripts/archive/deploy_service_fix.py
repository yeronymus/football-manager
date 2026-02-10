
import pty
import os
import sys
import time
import select

SERVER_USER = "ubuntu"
SERVER_HOST = "yernur-vm1.sin.cvut.cz"
PASSWORD = "Omnibus1"
LOCAL_FILE = "app/services/game_service.py"
REMOTE_DEST = "~/football-prod/game_service.py"
CONTAINER_DEST = "/app/app/services/game_service.py"

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
    upload_file(LOCAL_FILE, REMOTE_DEST)
    run_remote_command(f"docker cp {REMOTE_DEST} football-prod_app_1:{CONTAINER_DEST}")
    run_remote_command("docker restart -t 1 football-prod_app_1")
