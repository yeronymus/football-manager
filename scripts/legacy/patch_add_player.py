import os

ENDPOINTS_FILE = "app/api/endpoints.py"

def main():
    if not os.path.exists(ENDPOINTS_FILE):
        print(f"Error: {ENDPOINTS_FILE} not found!")
        return

    with open(ENDPOINTS_FILE, "r") as f:
        lines = f.readlines()

    found = False
    new_lines = []
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        if '@router.post("/admin/add_player")' in line:
            # Check next line for def
            if i + 1 < len(lines) and "def admin_add_player" in lines[i+1]:
                found = True
                print("Found endpoint definition.")
        
        if found and "def admin_add_player" in line:
            # We just appended the def line.
            # Now append the debug raise
            # Typically 4 spaces indentation
            indent = "    "
            # Adjust indent if needed by looking at next line? 
            # But usually 4 spaces.
            debug_code = f'{indent}raise HTTPException(status_code=400, detail=f"DEBUG HIT: game={{data.game_id}} user={{data.user_id}}")\n'
            new_lines.append(debug_code)
            found = False # Stop inserting

    if not found and '@router.post("/admin/add_player")' not in "".join(lines):
         print("Endpoint not found to patch.")
         return

    with open(ENDPOINTS_FILE, "w") as f:
        f.writelines(new_lines)
    
    print("Patched admin_add_player with debug raise.")

if __name__ == "__main__":
    main()
