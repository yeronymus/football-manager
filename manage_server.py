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

def main():
    # Check status and last 100 logs of app
    print("\n=== CHECKING LOGS ===_")
    remote_cmd = "cd ~/football-prod && docker-compose logs --tail=100 app"
    run_interactive(["ssh", "-o", "StrictHostKeyChecking=no", f"{SERVER_USER}@{SERVER_HOST}", remote_cmd])

if __name__ == "__main__":
    main()
