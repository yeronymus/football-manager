
import pty
import os
import sys
import select

SERVER_USER = "ubuntu"
SERVER_HOST = "yernur-vm1.sin.cvut.cz"
PASSWORD = "Omnibus1"

def run_remote_command(command):
    print(f"Remote EXEC: {command}")
    cmd_list = ["ssh", "-o", "StrictHostKeyChecking=no", f"{SERVER_USER}@{SERVER_HOST}", command]
    
    pid, fd = pty.fork()
    if pid == 0:
        os.execlp(cmd_list[0], *cmd_list)
    else:
        full_out = b""
        while True:
            try:
                r, _, _ = select.select([fd], [], [], 1)
                if fd in r:
                    output = os.read(fd, 1024)
                    if not output:
                        break
                    
                    full_out += output
                    lower_out = full_out.lower()

                    if b"password:" in lower_out:
                         # Check if we already sent the password to avoid loop
                         if b"omnibus" not in lower_out:
                             os.write(fd, PASSWORD.encode() + b"\n")
                    
            except OSError:
                break
            
            if os.waitpid(pid, os.WNOHANG) != (0, 0):
                # Small delay to capture final output
                try:
                    output = os.read(fd, 4096)
                    if output:
                        full_out += output
                except:
                    pass
                break
        
        print(full_out.decode('utf-8', errors='ignore'))

if __name__ == "__main__":
    run_remote_command("docker ps -a")
    run_remote_command("docker logs --tail 50 football-prod_app_1")
