import os

ENDPOINTS_FILE = "app/api/endpoints.py"

ADD_PLAYER_CODE = """
from app.api.schemas import AddPlayerRequest

@router.post("/admin/add_player")
async def admin_add_player(data: AddPlayerRequest, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
        
    user_id = get_user_from_init_data(data.initData)
    
    # Check Admin Rights on Game
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    # Check existence
    result = await session.execute(select(Signup).where(Signup.game_id == data.game_id, Signup.user_id == data.user_id))
    existing = result.scalar_one_or_none()
    
    if existing:
        if existing.status != SignupStatus.ACTIVE:
            existing.status = SignupStatus.ACTIVE
            await session.commit()
            return {"status": "updated", "message": "Player restored to Active"}
        else:
            return {"status": "ok", "message": "Already active"}
            
    # Create new
    signup = Signup(game_id=data.game_id, user_id=data.user_id, status=SignupStatus.ACTIVE)
    session.add(signup)
    await session.commit()
    
    return {"status": "added"}
"""

def main():
    if not os.path.exists(ENDPOINTS_FILE):
        print(f"Error: {ENDPOINTS_FILE} not found!")
        return

    with open(ENDPOINTS_FILE, "r") as f:
        content = f.read()

    # robust check
    if "def admin_add_player" in content:
        print("Function admin_add_player already exists. Doing nothing.")
    else:
        print("Function missing. Appending...")
        with open(ENDPOINTS_FILE, "a") as f:
            f.write(ADD_PLAYER_CODE)
        print("Function appended.")

if __name__ == "__main__":
    main()
