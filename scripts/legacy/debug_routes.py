import sys
import os
import asyncio

# Add project root to path
sys.path.append("/app")

try:
    from app.api.main import app
    print("Successfully imported app from app.api.main")
except ImportError:
    try:
        from app.main import app
        print("Successfully imported app from app.main")
    except ImportError:
        print("Could not import app")
        sys.exit(1)

print("\n--- Registered Routes ---")
for route in app.routes:
    methods = ", ".join(route.methods) if hasattr(route, "methods") else "None"
    print(f"{methods} {route.path}")
print("-------------------------")
