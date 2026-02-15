import os

FILES = [
    ("app/bot/common_handlers.py", "app/bot/common_handlers.py"),
    ("app/bot/handlers/common.py", "app/bot/handlers/common.py"),
    ("app/web/draft.html", "app/web/draft.html"),
    ("app/bot/balancer.py", "app/bot/balancer.py"),
    ("app/api/endpoints.py", "app/api/endpoints.py")
]

SERVER = "ubuntu@yernur-vm1.sin.cvut.cz"

for local, remote in FILES:
    os.system(f"scp -o StrictHostKeyChecking=no {local} {SERVER}:~/football-prod/{remote}")

os.system(f"ssh -o StrictHostKeyChecking=no {SERVER} 'cd ~/football-prod && docker-compose restart app'")
