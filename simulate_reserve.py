def simulate_release(max_players, active_count, reserves_count):
    slots_available = max_players - active_count
    print(f"Max: {max_players}, Active: {active_count}, Slots: {slots_available}")
    
    promoted = 0
    if slots_available > 0:
        to_promote = min(slots_available, reserves_count)
        print(f"Promoting {to_promote} players from reserve.")
        promoted = to_promote
    else:
        print("No slots available. No promotion.")
        
    final_active = active_count + promoted
    final_reserves = reserves_count - promoted
    print(f"Final State -> Active: {final_active}, Reserve: {final_reserves}")

simulate_release(max_players=18, active_count=17, reserves_count=5)
