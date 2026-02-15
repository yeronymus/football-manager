import requests
import os
import sys

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("ERROR: BOT_TOKEN env var is missing!")
        return

    print(f"Testing Token: {token[:5]}...{token[-5:]}")
    url = f"https://api.telegram.org/bot{token}/getMe"
    
    try:
        print(f"Requesting: {url.replace(token, 'HIDDEN')}")
        resp = requests.get(url, timeout=10)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    main()
