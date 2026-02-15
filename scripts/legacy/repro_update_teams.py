from pydantic import BaseModel
from typing import Optional, Dict
import asyncio

class UpdateTeamsRequest(BaseModel):
    game_id: int
    team_a: list[int]
    team_b: list[int]
    team_c: Optional[list[int]] = None
    positions: Optional[dict[int, str]] = None
    initData: str

async def test():
    # Simulate frontend payload
    json_data = {
        "game_id": 10,
        "team_a": [-1739437158123456], # Guest ID
        "team_b": [123],
        "team_c": [],
        "positions": {"-1739437158123456": "CM"},
        "initData": "dummy"
    }
    
    try:
        req = UpdateTeamsRequest(**json_data)
        print("Pydantic: OK")
        print(f"Positions keys types: {[type(k) for k in req.positions.keys()]}")
        print(f"Positions keys values: {list(req.positions.keys())}")
        
        # Simulate logic in RosterService
        positions = req.positions
        uid = -1739437158123456
        
        if str(uid) in positions:
            print("Found in positions via str(uid)")
        elif uid in positions:
            print("Found in positions via uid")
        else:
            print("Not found in positions")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
