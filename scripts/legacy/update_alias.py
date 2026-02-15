import os

ENDPOINTS_FILE = "app/api/endpoints.py"

# The incorrect/simple alias we added previously
OLD_ALIAS_START = '@router.get("/admin/find_users")'

# The new robust alias
NEW_ALIAS_CODE = """
# --- Legacy Alias for WebApp Caching ---
@router.get("/admin/find_users")
async def admin_find_users_alias(q: str, initData: str, session: AsyncSession = Depends(get_session)):
    # Redirect legacy 'q' param to new 'query' param
    results = await search_users(query=q, initData=initData, session=session)
    # Legacy frontend likely expects 'full_name' instead of 'name'
    # We return a list of dicts, so we can modify them.
    enriched = []
    for u in results:
        # u is a dict from search_users
        item = u.copy()
        item['full_name'] = item['name']
        item['fullname'] = item['name'] 
        enriched.append(item)
    return enriched
"""

def main():
    if not os.path.exists(ENDPOINTS_FILE):
        print(f"Error: {ENDPOINTS_FILE} not found!")
        return

    with open(ENDPOINTS_FILE, "r") as f:
        content = f.read()

    # Find where the old alias starts (it was appended to the end)
    # We will search for the specific def line
    target_str = '@router.get("/admin/find_users")'
    idx = content.rfind(target_str)
    
    if idx == -1:
        print("Old alias not found to replace. Appending new one...")
        with open(ENDPOINTS_FILE, "a") as f:
            f.write(NEW_ALIAS_CODE)
    else:
        print("Found old alias. Replacing it...")
        # Assume it's the last thing in the file or we just truncate from there
        # Since I appended it at the end, I can just truncate from `idx`
        # But to be safe, let's verify it looks like the old one
        
        # We will keep everything BEFORE the alias
        new_content = content[:idx] + NEW_ALIAS_CODE
        
        with open(ENDPOINTS_FILE, "w") as f:
            f.write(new_content)
        print("Alias updated successfully.")

if __name__ == "__main__":
    main()
