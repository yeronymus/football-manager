
import pty
import os
import sys
import select
import base64

SERVER_USER = "ubuntu"
SERVER_HOST = "yernur-vm1.sin.cvut.cz"
PASSWORD = "Omnibus1"

FILES_TO_DEPLOY = [
    ("app/bot/utils.py", "/app/app/bot/utils.py"),
    ("app/bot/admin_handlers.py", "/app/app/bot/admin_handlers.py"),
    ("app/services/game_service.py", "/app/app/services/game_service.py"),
    ("app/scheduler/tasks.py", "/app/app/scheduler/tasks.py"),
    ("app/web/index.html", "/app/app/web/index.html")
]

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
                    if b"password:" in full_out.lower() and b"omnibus" not in full_out.lower():
                        os.write(fd, PASSWORD.encode() + b"\n")
                        full_out = b""
                    
            except OSError:
                break
            
            if os.waitpid(pid, os.WNOHANG) != (0, 0):
                break

def deploy_via_base64():
    for local_path, container_path in FILES_TO_DEPLOY:
        print(f"Deploying {local_path} -> {container_path}")
        content = open(local_path, "rb").read()
        b64_content = base64.b64encode(content).decode()
        
        tmp_remote = f"/tmp/{os.path.basename(local_path)}.b64"
        
        # 1. Upload b64
        cmd = f"cat > {tmp_remote} <<EOF\n{b64_content}\nEOF"
        run_remote_command(cmd)
        
        # 2. Decode and copy to container
        cmd = f"base64 -d {tmp_remote} > {tmp_remote}.file && docker cp {tmp_remote}.file football-prod_app_1:{container_path}"
        run_remote_command(cmd)

    # 3. Restart container
    run_remote_command("docker restart -t 1 football-prod_app_1")

if __name__ == "__main__":
    deploy_via_base64()
