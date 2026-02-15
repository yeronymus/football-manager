import os

ENDPOINTS_FILE = "app/api/endpoints.py"

ALIAS_CODE = """

# --- Legacy Alias for WebApp Caching ---
@router.get("/admin/find_users")
async def admin_find_users_alias(q: str, initData: str, session: AsyncSession = Depends(get_session)):
    # Redirect legacy 'q' param to new 'query' param
    return await search_users(query=q, initData=initData, session=session)
"""

def main():
    if not os.path.exists(ENDPOINTS_FILE):
        print(f"Error: {ENDPOINTS_FILE} not found!")
        return

    with open(ENDPOINTS_FILE, "r") as f:
        content = f.read()

    if "/admin/find_users" in content:
        print("Alias already exists. Skipping.")
    else:
        print("Appending alias...")
        with open(ENDPOINTS_FILE, "a") as f:
            f.write(ALIAS_CODE)
        print("Alias appended successfully.")

if __name__ == "__main__":
    main()
