import urllib.request, urllib.parse, base64, subprocess, os
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("10.50.109.14", username="yernur", password="Omnibus1")

sftp = ssh.open_sftp()
sftp.put("/home/yeronym/Documents/fmBot/football-manager/fix_goals.py", "/home/yernur/football-manager/fix_goals.py")
sftp.close()

stdin, stdout, stderr = ssh.exec_command("echo 'Omnibus1' | sudo -S docker cp ~/football-manager/fix_goals.py football-manager-app-1:/app/fix_goals.py && echo 'Omnibus1' | sudo -S docker exec football-manager-app-1 python3 /app/fix_goals.py")
print("STDOUT:", stdout.read().decode())
print("STDERR:", stderr.read().decode())
ssh.close()
