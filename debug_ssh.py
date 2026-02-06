
import pty
import os
import sys
import time

def main():
    pid, fd = pty.fork()
    if pid == 0:
        # Child
        # Try to execute SSH
        # SERVER_USER="ubuntu"
        # SERVER_HOST="yernur-vm1.sin.cvut.cz"
        sys.stdout.flush()
        os.execlp("ssh", "ssh", "-o", "ConnectTimeout=5", "ubuntu@yernur-vm1.sin.cvut.cz", "echo success")
    else:
        # Parent
        try:
            full_out = b""
            while True:
                try:
                    output = os.read(fd, 1024)
                except OSError:
                    break
                if not output:
                    break
                
                full_out += output
                sys.stdout.buffer.write(output)
                sys.stdout.flush()
                
                lower_out = full_out.lower()
                
                if b"are you sure you want to continue connecting" in lower_out:
                    print("\n[DEBUG] Sending 'yes'...")
                    os.write(fd, b"yes\n")
                    full_out = b"" # Reset buffer to avoid repeat matching if stream is slow
                
                elif b"password" in lower_out:
                    print("\n[DEBUG] Sending Password...")
                    os.write(fd, b"Omnibus1\n")
                    # We exit after sending? No, wait for result.
                    full_out = b""

                time.sleep(0.1)
                
        except Exception as e:
            print(f"Parent Error: {e}")
        finally:
            os.close(fd)
            os.waitpid(pid, 0)

if __name__ == "__main__":
    main()
