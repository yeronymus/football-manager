import hashlib
import hmac
import time
import json
import urllib.parse
import urllib.request
import os

# CONFIG
BOT_TOKEN = "8067557564:AAGpWa9lF3jdPS4umdi-peX2H3cOXfwUW4E" # From production.env
ADMIN_ID = 502389915
BASE_URL = "https://yernur-vm1.sin.cvut.cz"

def generate_init_data():
    user_data = json.dumps({"id": ADMIN_ID, "first_name": "Admin", "username": "admin"})
    auth_date = str(int(time.time()))
    
    data_dict = {
        "query_id": "AAGHsQAJAQAAAIexAAAB",
        "user": user_data,
        "auth_date": auth_date
    }
    
    # Sort keys
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))
    
    # Sign
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    # Encode for URL
    data_dict["hash"] = hash_value
    encoded = []
    for k, v in data_dict.items():
        encoded.append(f"{k}={urllib.parse.quote(v)}")
    
    # Manual join to ensure correct format if strict
    # init_data = "&".join(encoded)
    # Actually checking validate_init_data: it uses parse_qsl. urlencode is fine.
    init_data = urllib.parse.urlencode(data_dict)
    return init_data

def check_game_status(game_id):
    print(f"Checking status for Game {game_id}...")
    init_data = generate_init_data()
    url = f"{BASE_URL}/game/{game_id}?initData={urllib.parse.quote(init_data)}"
    
    try:
        req = urllib.request.Request(url)
        print(f"Requesting {url}...")
        with urllib.request.urlopen(req, timeout=5) as response:
            print(f"Response Code: {response.status}")
            if response.status == 200:
                data = json.load(response)
                print(f"Game #{game_id} Status: {data.get('status')}")
                return data
            else:
                print(f"HTTP Error: {response.status}")
    except Exception as e:
        print(f"Error checking status: {e}")
        return None

def publish_teams(game_id):
    init_data = generate_init_data()
    url = f"{BASE_URL}/publish_teams"
    
    payload = {
        "game_id": game_id,
        "initData": init_data
    }
    data = json.dumps(payload).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print("Publish Success (Status might have changed to ACTIVE).")
                return True
            else:
                print(f"HTTP Error: {response.status}")
    except Exception as e:
        print(f"Error publishing: {e}")
        return False

if __name__ == "__main__":
    game_data = check_game_status(47)
    if game_data and game_data.get("status") == "cancelled":
        print("Game is CANCELLED. Attempting to reopen via publish_teams...")
        publish_teams(47)
        check_game_status(47)
    elif game_data and game_data.get("status") == "finished":
         print("Game is FINISHED. Cannot reopen via API methods found so far.")
    elif game_data:
         print(f"Game status is {game_data.get('status')}. No action taken.")
