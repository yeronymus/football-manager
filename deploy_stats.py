
import os
import subprocess
import time

# Configuration
SERVER_USER = "ubuntu"
SERVER_HOST = "yernur-vm1.sin.cvut.cz"
CONTAINER_NAME = "football-prod_app_1"
REMOTE_PATH = "/home/ubuntu/football-prod"
SSH_KEY_OPTS = ["-o", "StrictHostKeyChecking=no"]

# Files to deploy
FILES_TO_DEPLOY = [
    ("app/bot/stats_handlers.py", "app/bot/stats_handlers.py"),
    ("app/bot/main.py", "app/bot/main.py")
]

def run_cmd(cmd, check=True):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result

def deploy():
    print("Starting deployment of statistics feature...")
    
    # 1. SCP files to remote host
    for local_path, remote_rel_path in FILES_TO_DEPLOY:
        if not os.path.exists(local_path):
            print(f"Local file not found: {local_path}")
            continue
            
        remote_dest = f"{REMOTE_PATH}/{os.path.basename(local_path)}" # Flatten for simplicity or keep structure?
        # Actually our previous logic was flat copy to ~/football-prod then docker cp
        # But we need to keep structure inside container.
        
        print(f"Uploading {local_path}...")
        scp_cmd = ["scp"] + SSH_KEY_OPTS + [local_path, f"{SERVER_USER}@{SERVER_HOST}:{REMOTE_PATH}/{os.path.basename(local_path)}"]
        run_cmd(scp_cmd)
        
        # 2. Docker CP from host to container
        # We need to target specific paths inside container.
        # FILES_TO_DEPLOY has (local, container_rel_path)
        # We copied to ~/football-prod/basename
        
        container_dest = f"/app/{remote_rel_path}"
        remote_src = f"{REMOTE_PATH}/{os.path.basename(local_path)}"
        
        print(f"Copying to container: {container_dest}...")
        docker_cp_cmd = ["ssh"] + SSH_KEY_OPTS + [f"{SERVER_USER}@{SERVER_HOST}", f"docker cp {remote_src} {CONTAINER_NAME}:{container_dest}"]
        run_cmd(docker_cp_cmd)

    # 3. Restart Container
    print("Restarting container...")
    restart_cmd = ["ssh"] + SSH_KEY_OPTS + [f"{SERVER_USER}@{SERVER_HOST}", f"docker restart {CONTAINER_NAME}"]
    run_cmd(restart_cmd)
    
    # 4. Check Status
    time.sleep(5)
    status_cmd = ["ssh"] + SSH_KEY_OPTS + [f"{SERVER_USER}@{SERVER_HOST}", f"docker ps | grep {CONTAINER_NAME}"]
    res = run_cmd(status_cmd)
    print(f"Status: {res.stdout.strip()}")

if __name__ == "__main__":
    deploy()
