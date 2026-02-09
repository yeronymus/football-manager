import os
import subprocess
import time
import base64

def run_command(command):
    try:
        # print(f"EXEC: {command}") # Too verbose with base64
        print(f"Executing remote command...")
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        exit(1)

def upload_file(local_path, remote_path):
    HOST = "root@195.179.229.119"
    print(f"Uploading {local_path} -> {remote_path}...")
    with open(local_path, "rb") as f:
        content_bytes = f.read()
    b64 = base64.b64encode(content_bytes).decode('utf-8')
    
    # Chunk the base64 if needed? SSH command limit? 
    # Let's hope it fits in one command (usually ~128KB is fine for args, files are small).
    # vote_handlers.py is 2KB. force_simple_vote.py is 3KB. Should be fine.
    
    cmd = f"ssh {HOST} \"echo '{b64}' | base64 -d > {remote_path}\""
    run_command(cmd)

def main():
    HOST = "root@195.179.229.119"
    REMOTE_DIR = "~/football-prod"
    
    # 1. Upload vote_handlers.py
    upload_file("app/bot/vote_handlers.py", f"{REMOTE_DIR}/vote_handlers.py")
    
    # 2. Upload force_simple_vote.py
    upload_file("force_simple_vote.py", f"{REMOTE_DIR}/force_simple_vote.py")
    
    # 3. Copy to Container
    print("Copying to container...")
    run_command(f"ssh {HOST} 'docker cp {REMOTE_DIR}/vote_handlers.py football-prod_app_1:/app/app/bot/vote_handlers.py'")
    run_command(f"ssh {HOST} 'docker cp {REMOTE_DIR}/force_simple_vote.py football-prod_app_1:/app/force_simple_vote.py'")
    
    # 4. Restart Bot
    print("Restarting bot...")
    run_command(f"ssh {HOST} 'docker restart football-prod_app_1'")
    
    print("Waiting for boot (10s)...")
    time.sleep(10)
    
    # 5. Run Script
    print("Running Voting Script...")
    run_command(f"ssh {HOST} 'docker exec -i football-prod_app_1 python3 /app/force_simple_vote.py'")
    
    # Cleanup remote temp files
    run_command(f"ssh {HOST} 'rm {REMOTE_DIR}/vote_handlers.py {REMOTE_DIR}/force_simple_vote.py'")

if __name__ == "__main__":
    main()
