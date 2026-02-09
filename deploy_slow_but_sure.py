import os
import subprocess
import time
import base64
import gzip

HOST = "root@195.179.229.119"
REMOTE_BASE = "~/football-prod"

def run_command(command, ignore_errors=False):
    try:
        subprocess.check_call(command, shell=True)
        return True
    except subprocess.CalledProcessError as e:
        if not ignore_errors:
            print(f"Error: {e}")
        return False

def run_ssh(cmd, retries=3):
    """Run a single SSH command with retries."""
    full_cmd = f"ssh {HOST} \"{cmd}\""
    for i in range(retries):
        if run_command(full_cmd, ignore_errors=True):
            return True
        print(f"  Retry {i+1}/{retries}...")
        time.sleep(1)
    return False

def upload_chunked(local_path, remote_path):
    print(f"Uploading {local_path} -> {remote_path} (Chunked)...")
    
    # 1. Read and Compress
    with open(local_path, "rb") as f:
        data = f.read()
    
    compressed = gzip.compress(data)
    b64_data = base64.b64encode(compressed).decode('utf-8')
    
    # 2. Clear remote temp
    tmp_path = remote_path + ".b64"
    run_ssh(f"rm -f {tmp_path}")
    
    # 3. Send Chunks
    CHUNK_SIZE = 500
    total_chunks = (len(b64_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    for i in range(total_chunks):
        chunk = b64_data[i*CHUNK_SIZE : (i+1)*CHUNK_SIZE]
        # Append chunk
        # echo -n to avoid newlines
        if not run_ssh(f"echo -n '{chunk}' >> {tmp_path}"):
            print(f"Failed to upload chunk {i}")
            return False
        # Small delay to be nice to the network
        time.sleep(0.1)
        if i % 5 == 0:
             print(f"  Sent chunk {i+1}/{total_chunks}")
             
    # 4. Decode and Decompress on Remote
    print("  Decoding...")
    decode_cmd = f"cat {tmp_path} | base64 -d | gzip -d > {remote_path} && rm {tmp_path}"
    if not run_ssh(decode_cmd):
        print("Failed to decode remote file.")
        return False
        
    print(f"Success: {local_path}")
    return True

def main():
    # 1. Upload Files
    if not upload_chunked("app/bot/vote_handlers.py", f"{REMOTE_BASE}/vote_handlers.py"): return
    if not upload_chunked("force_simple_vote.py", f"{REMOTE_BASE}/force_simple_vote.py"): return
    
    # 2. Update Container
    print("Updating Container...")
    # vote_handlers.py -> /app/app/bot/vote_handlers.py
    run_ssh(f"docker cp {REMOTE_BASE}/vote_handlers.py football-prod_app_1:/app/app/bot/vote_handlers.py")
    # force_simple_vote.py -> /app/force_simple_vote.py
    run_ssh(f"docker cp {REMOTE_BASE}/force_simple_vote.py football-prod_app_1:/app/force_simple_vote.py")
    
    # 3. Restart Bot
    print("Restarting Bot...")
    run_ssh("docker restart football-prod_app_1")
    
    print("Waiting 10s for boot...")
    time.sleep(10)
    
    # 4. Execute Script
    print("Triggering Voting Script...")
    run_ssh("docker exec -i football-prod_app_1 python3 /app/force_simple_vote.py")
    
    # Cleanup
    run_ssh(f"rm {REMOTE_BASE}/vote_handlers.py {REMOTE_BASE}/force_simple_vote.py")

if __name__ == "__main__":
    main()
