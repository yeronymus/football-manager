import subprocess
import time

def main():
    HOST = "root@195.179.229.119"
    cmd = f"ssh {HOST} 'docker logs --tail 100 football-prod_app_1'"
    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
