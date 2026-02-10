
import pty
import os
import sys
import time
import select

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

def scp_file(local_path, remote_path):
    print(f"SCP: {local_path} -> {remote_path}")
    cmd_list = ["scp", "-o", "StrictHostKeyChecking=no", local_path, f"{SERVER_USER}@{SERVER_HOST}:{remote_path}"]
    
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
                    if not output: break
                    full_out += output
                    if b"password:" in full_out.lower():
                        os.write(fd, PASSWORD.encode() + b"\n")
                        full_out = b""
            except OSError: break
            if os.waitpid(pid, os.WNOHANG) != (0, 0): break

if __name__ == "__main__":
    # 1. Deploy keyboard fix
    scp_file("app/bot/keyboards.py", "/home/ubuntu/football-prod/keyboards.py")
    print(run_remote_command("docker cp /home/ubuntu/football-prod/keyboards.py football-prod_app_1:/app/app/bot/keyboards.py"))
    
    # 2. Restart (optional but recommended for code changes)
    print("Restarting container...")
    print(run_remote_command("docker restart football-prod_app_1"))
    time.sleep(5)
    
    # 3. Force Publish Game 47
    print("Forcing publication...")
    publish_cmd = "docker exec football-prod_app_1 python3 -c 'import asyncio; from app.scheduler.tasks import publish_game_task; asyncio.run(publish_game_task(47))'"
    print(run_remote_command(publish_cmd))
    
    print("DONE")
