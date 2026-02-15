
import pty
import os
import sys
import time
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

                    if b"password:" in lower_out and b"omnibus1" not in lower_out:
                        os.write(fd, PASSWORD.encode() + b"\n")
                        full_out = b""
                    
            except OSError:
                break
            
            if os.waitpid(pid, os.WNOHANG) != (0, 0):
                try:
                    output = os.read(fd, 4096)
                    if output:
                        full_out += output
                except:
                    pass
                break
        
        return full_out.decode('utf-8', errors='ignore')

if __name__ == "__main__":
    print("--- SYSTEM TIME ---")
    print(run_remote_command("date"))
    print("--- CONTAINER TIME ---")
    print(run_remote_command("docker exec football-prod_app_1 date"))
    
    print("--- PUBLISHING GAME 47 ---")
    publish_cmd = "docker exec football-prod_app_1 python3 -c 'import asyncio; from app.scheduler.tasks import publish_game_task; asyncio.run(publish_game_task(47))'"
    print(run_remote_command(publish_cmd))
    
    print("--- CHECKING DB STATE ---")
    db_cmd = "docker exec football-prod_app_1 python3 -c 'import asyncio; from app.db.database import async_session_maker; from app.db.models import Game; from sqlalchemy import select; async def check(): async with async_session_maker() as s: g = await s.get(Game, 47); print(f\"Game 47 Status: {g.status}, MsgID: {g.message_id}, ChanMsgID: {g.channel_message_id}\" if g else \"Not found\"); asyncio.run(check())'"
    print(run_remote_command(db_cmd))
