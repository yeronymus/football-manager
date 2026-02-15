import subprocess
import sys

def run_ssh_command(cmd):
    ssh_cmd = f"ssh -o StrictHostKeyChecking=no ubuntu@yernur-vm1.sin.cvut.cz {cmd}"
    print(f"Executing: {ssh_cmd}")
    try:
        result = subprocess.run(
            ssh_cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        if result.returncode != 0:
            print(f"Exit Code: {result.returncode}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    # Test simple command first
    run_ssh_command("echo hello_world")
    
    # Fetch Docker logs
    run_ssh_command("docker logs --tail 100 football-prod_app_1 2>&1")
