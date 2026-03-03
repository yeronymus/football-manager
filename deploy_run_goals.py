import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("10.50.109.14", username="yernur", password="Omnibus1", timeout=10)

commands = [
    "echo 'Omnibus1' | sudo -S docker cp ~/football-manager/FM_Player_Stats.csv football-manager-app-1:/app/FM_Player_Stats.csv",
    "echo 'Omnibus1' | sudo -S docker cp ~/football-manager/fix_goals.py football-manager-app-1:/app/fix_goals.py",
    "echo 'Omnibus1' | sudo -S docker exec football-manager-app-1 python3 /app/fix_goals.py"
]

for cmd in commands:
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print("STDOUT:", stdout.read().decode())
    print("STDERR:", stderr.read().decode())

ssh.close()
