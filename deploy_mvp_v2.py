import pty
import os
import sys
import time

SERVER_USER = "ubuntu"
SERVER_HOST = "yernur-vm1.sin.cvut.cz"
PASSWORD = "Omnibus1"

def run_interactive(cmd_list):
    print(f"[INFO] Running: {' '.join(cmd_list)}")
    pid, fd = pty.fork()
    if pid == 0:
        os.execlp(cmd_list[0], *cmd_list)
    else:
        full_out = b""
        with open("deploy_mvp_v2_log.txt", "ab") as log_file:
            while True:
                try:
                    output = os.read(fd, 1024)
                except OSError:
                    break
                if not output:
                    break
                
                sys.stdout.buffer.write(output)
                sys.stdout.flush()
                log_file.write(output)
                log_file.flush()
                
                full_out += output
                lower_out = full_out.lower()
                
                if b"are you sure you want to continue connecting" in lower_out:
                    os.write(fd, b"yes\n")
                    full_out = b"" 
                elif b"password:" in lower_out:
                    os.write(fd, PASSWORD.encode() + b"\n")
                    full_out = b""

                time.sleep(0.01)
        
        os.waitpid(pid, 0)

def main():
    FILES = [
        ("app/api/endpoints.py", "~/football-prod/app/api/endpoints.py"),
        ("app/scheduler/tasks.py", "~/football-prod/app/scheduler/tasks.py"),
        ("force_voting_msg.py", "~/football-prod/force_voting_msg.py"),
    ]
    
    print("\n=== 1. UPLOADING FILES ===")
    for local, remote in FILES:
        run_interactive(["scp", "-o", "StrictHostKeyChecking=no", local, f"{SERVER_USER}@{SERVER_HOST}:{remote}"])
    
    print("\n=== 2. RESTARTING APP ===")
    remote_cmd = "cd ~/football-prod && docker-compose restart app"
    run_interactive(["ssh", "-o", "StrictHostKeyChecking=no", f"{SERVER_USER}@{SERVER_HOST}", remote_cmd])
    
    print("\n=== 3. FORCE SENDING VOTING MESSAGE ===")
    # Run script inside container
    force_cmd = "cd ~/football-prod && docker-compose run --rm app python force_voting_msg.py"
    run_interactive(["ssh", "-o", "StrictHostKeyChecking=no", f"{SERVER_USER}@{SERVER_HOST}", force_cmd])

if __name__ == "__main__":
    main()
