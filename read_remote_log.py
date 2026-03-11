import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("10.50.109.14", username="yernur", password="Omnibus1", timeout=15)

try:
    sftp = ssh.open_sftp()
    remote_file = sftp.file("/home/yernur/cloudflared.log", "r")
    log_content = remote_file.read().decode()
    remote_file.close()
    
    print("LOG CONTENT:")
    print(log_content)
            
except Exception as e:
    print(f"SFTP failed: {e}")

ssh.close()
