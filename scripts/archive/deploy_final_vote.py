import os
import subprocess
import time
import sys

HOSTR = "root@195.179.229.119"
REMOTE_BASE = "~/football-prod"

def run_with_retry(formatted_cmd, max_retries=5):
    """Run a command with retries."""
    for i in range(max_retries):
        try:
            print(f"[Attempt {i+1}/{max_retries}] {formatted_cmd}...")
            subprocess.check_call(formatted_cmd, shell=True)
            print("Success!")
            return True
        except subprocess.CalledProcessError:
            print("Failed. Retrying in 2s...")
            time.sleep(2)
    print("Fatal: Command failed after retries.")
    return False

def main():
    # 1. Upload vote_handlers.py (Critical for logic)
    # We need to ensure local file is correct first? I replaced it in previous steps.
    # Remote location: ~/football-prod/app/bot/vote_handlers.py
    
    cmd_upload_handler = f"scp app/bot/vote_handlers.py {HOSTR}:{REMOTE_BASE}/app/bot/vote_handlers.py"
    if not run_with_retry(cmd_upload_handler): return

    # 2. Upload force_simple_vote.py (Critical for UI)
    cmd_upload_script = f"scp force_simple_vote.py {HOSTR}:{REMOTE_BASE}/force_simple_vote.py"
    if not run_with_retry(cmd_upload_script): return

    # 3. Copy to Container & Restart
    # We Update the container's version just in case
    # Assuming volume mount works, but let's be safe and copy.
    cmd_update_container = f"ssh {HOSTR} 'docker cp {REMOTE_BASE}/app/bot/vote_handlers.py football-prod_app_1:/app/app/bot/vote_handlers.py && docker cp {REMOTE_BASE}/force_simple_vote.py football-prod_app_1:/app/force_simple_vote.py'"
    if not run_with_retry(cmd_update_container): return
    
    # 4. Restart Bot
    cmd_restart = f"ssh {HOSTR} 'docker restart football-prod_app_1'"
    if not run_with_retry(cmd_restart): return
    
    print("Bot restarting... Waiting 10s...")
    time.sleep(10)
    
    # 5. Run Voting Script
    cmd_run = f"ssh {HOSTR} 'docker exec -i football-prod_app_1 python3 /app/force_simple_vote.py'"
    if not run_with_retry(cmd_run): return

if __name__ == "__main__":
    main()
