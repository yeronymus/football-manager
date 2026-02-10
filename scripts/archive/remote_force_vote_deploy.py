import os
import subprocess
import time

def run_command(command):
    try:
        if "docker exec" in command:
             # Docker Exec
             print(f"Remote EXEC: {command}")
             subprocess.check_call(command, shell=True)
        elif "scp" in command:
             # SCP
             print(f"Uploading {command.split()[1]} -> {command.split()[2]}")
             subprocess.check_call(command, shell=True)
        else:
             # SSH or Local
             print(f"Local EXEC: {command}")
             subprocess.check_call(command, shell=True)
             
    except subprocess.CalledProcessError as e:
        print(f"Error executing {command}: {e}")
        exit(1)

def main():
    HOST = "root@195.179.229.119"
    REMOTE_DIR = "~/football-prod"
    
    # Upload Script
    run_command(f"scp force_voting_msg.py {HOST}:{REMOTE_DIR}/force_voting_msg.py")
    
    # Run in Container
    run_command(f"ssh {HOST} 'cd {REMOTE_DIR} && docker cp force_voting_msg.py football-prod_app_1:/app/force_voting_msg.py'")
    run_command(f"ssh {HOST} 'docker exec -i football-prod_app_1 python3 /app/force_voting_msg.py'")

if __name__ == "__main__":
    main()
