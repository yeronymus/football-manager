import pty
import os
import sys
import time

SERVER_USER = "root"
SERVER_HOST = "147.32.107.65"
SERVER_PORT = "2222"
PASSWORD = "" # Should be provided via env or prompt

def run_interactive(cmd_list):
    print(f"[INFO] Running: {' '.join(cmd_list)}")
    pid, fd = pty.fork()
    if pid == 0:
        os.execlp(cmd_list[0], *cmd_list)
    else:
        full_out = b""
        with open("server_log.txt", "ab") as log_file:
            while True:
                try:
                    output = os.read(fd, 1024)
                except OSError:
                    break
                if not output:
                    break
                
                # Print to stdout
                sys.stdout.buffer.write(output)
                sys.stdout.flush()
                # Log to file
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

def monitor_remote_logs():
    # Check status and last 100 logs of app
    print("\n=== CHECKING LOGS ===\n")
    remote_cmd = "cd ~/football-bot && docker compose logs --tail=100 app"
    run_interactive(["ssh", "-p", SERVER_PORT, "-o", "StrictHostKeyChecking=no", f"{SERVER_USER}@{SERVER_HOST}", remote_cmd])
