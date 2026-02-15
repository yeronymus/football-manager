import sys
import os

# Add project root to path
sys.path.append("/app")

try:
    from app.api.endpoints import router
    print("Successfully imported router from app.api.endpoints")
except ImportError as e:
    print(f"Could not import router: {e}")
    sys.exit(1)

print("\n--- Router Routes ---")
for route in router.routes:
    methods = ", ".join(route.methods) if hasattr(route, "methods") else "None"
    print(f"{methods} {route.path}")
print("---------------------")
