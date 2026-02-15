import subprocess
import os
import sys

LOG_FILE = "fix_remote_log.txt"
with open(LOG_FILE, "w") as f: f.write("Starting remote fix...\n")

def log(msg):
    with open(LOG_FILE, "a") as f: # Append mode
        f.write(msg + "\n")
        f.flush()
    print(msg)

FILES = [
    "debug_router_only.py"
]

def run_cmd(cmd_list):
    log(f"Running: {' '.join(cmd_list)}")
    try:
        # Added timeout to avoid hanging
        result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=20)
        output_str = result.stdout + result.stderr
        log(f"CMS Output: {output_str}")
        return output_str
    except Exception as e:
        log(f"Error: {e}")
        return str(e)

# 1. Deploy New Architecture
log("Uploading app package...")
run_cmd(["scp", "-o", "StrictHostKeyChecking=no", "app_deploy.tar.gz", "ubuntu@yernur-vm1.sin.cvut.cz:~/football-prod/app_deploy.tar.gz"])

log("Updating remote code...")
# Create backup, extract, restart
cmds = [
    "cd ~/football-prod",
    "cp -r app app_backup_$(date +%s) || true",
    "tar -xzf app_deploy.tar.gz", # overwrites app folder
    "docker-compose restart app"
]
remote_cmd = " && ".join(cmds)
run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", remote_cmd])

log("\nDeploying verification script...")
run_cmd(["scp", "-o", "StrictHostKeyChecking=no", "verify_game_6.py", "ubuntu@yernur-vm1.sin.cvut.cz:/tmp/verify_game_6.py"])
run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", "docker cp /tmp/verify_game_6.py football-prod_app_1:/app/verify_game_6.py"])

log("\nRunning verification inside container...")
# Need to wait a bit for restart? 'restart' command blocks until done usually.
# Uvicorn might take a second to start.
import time
time.sleep(5) 

# Debug: Check uow.py content
log("Checking remote uow.py...")
run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", "docker exec football-prod_app_1 cat /app/app/core/uow.py"])

# Cleanup pycache
log("Cleaning pycache...")
run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", "docker exec football-prod_app_1 find /app -name '*.pyc' -delete"])
run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", "cd ~/football-prod && docker-compose restart app"])
time.sleep(5)

run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", "docker exec football-prod_app_1 python3 verify_game_6.py"])

log("Done.")

# 1. Check Docker Logs
log("Reading container logs...")
run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", "docker logs --tail 200 football-prod_app_1"])

# 1. Deploy & Run Router Debug
for f in FILES:
    log(f"Deploying {f}...")
    run_cmd(["scp", "-o", "StrictHostKeyChecking=no", f, f"ubuntu@yernur-vm1.sin.cvut.cz:/tmp/{os.path.basename(f)}"])
    run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", f"docker cp /tmp/{os.path.basename(f)} football-prod_app_1:/app/{f}"])

log("Running debug_router_only.py...")
run_cmd(["ssh", "-o", "StrictHostKeyChecking=no", "ubuntu@yernur-vm1.sin.cvut.cz", "docker exec football-prod_app_1 python3 debug_router_only.py"])

log("Done.")
