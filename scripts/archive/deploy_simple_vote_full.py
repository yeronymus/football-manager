import os
import subprocess
import time

def run_command(command):
    try:
        print(f"EXEC: {command}")
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing {command}: {e}")
        exit(1)

def main():
    HOST = "root@195.179.229.119"
    REMOTE_DIR = "~/football-prod"
    
    # 1. Tar the APP and the SCRIPT
    print("Packaging app and script...")
    run_command("tar -czf full_vote_deploy.tar.gz app force_simple_vote.py")
    
    # 2. Upload
    print("Uploading...")
    run_command(f"scp full_vote_deploy.tar.gz {HOST}:{REMOTE_DIR}/full_vote_deploy.tar.gz")
    
    # 3. Extract on Remote
    print("Extracting remote...")
    run_command(f"ssh {HOST} 'cd {REMOTE_DIR} && tar -xzf full_vote_deploy.tar.gz'")
    
    # 4. Copy to Container
    # We need to copy 'app' folder content to /app/app inside container
    # But usually we copy the whole app folder.
    # The container mounts /app? No, usually it's copied.
    # Let's check docker cp syntax.
    print("Updating container code...")
    run_command(f"ssh {HOST} 'docker cp {REMOTE_DIR}/app football-prod_app_1:/app/'")
    run_command(f"ssh {HOST} 'docker cp {REMOTE_DIR}/force_simple_vote.py football-prod_app_1:/app/force_simple_vote.py'")
    
    # 5. Restart Bot to pick up vote_handlers.py changes
    print("Restarting bot...")
    run_command(f"ssh {HOST} 'docker restart football-prod_app_1'")
    
    print("Waiting for boot (10s)...")
    time.sleep(10)
    
    # 6. Run the Script
    print("Running Voting Script...")
    run_command(f"ssh {HOST} 'docker exec -i football-prod_app_1 python3 /app/force_simple_vote.py'")
    
    # Cleanup
    run_command("rm full_vote_deploy.tar.gz")
    run_command(f"ssh {HOST} 'rm {REMOTE_DIR}/full_vote_deploy.tar.gz'")

if __name__ == "__main__":
    main()
