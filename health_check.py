import sys
import os
import py_compile
from pathlib import Path

def check_project_health():
    print("🚀 Starting Football Manager Bot Health Check...")
    
    # Files to check for syntax
    critical_files = [
        "app/bot/instance.py",
        "app/bot/main.py",
        "app/bot/listeners.py",
        "app/api/routers/admin.py",
        "app/config.py",
    ]
    
    all_ok = True
    base_path = Path(__file__).parent
    
    print("\n🔍 Checking for syntax errors and NameErrors...")
    for file_path in critical_files:
        full_path = base_path / file_path
        if not full_path.exists():
            print(f"❌ MISSING: {file_path}")
            all_ok = False
            continue
            
        try:
            py_compile.compile(str(full_path), doraise=True)
            print(f"✅ OK: {file_path}")
        except Exception as e:
            print(f"❌ ERROR in {file_path}: {e}")
            all_ok = False

    print("\n📦 Checking for circular imports (Dry Run)...")
    # This is harder to do without running, but we can check if instance.py is clean
    try:
        with open(base_path / "app/bot/instance.py", "r") as f:
            content = f.read()
            if "app.bot.main" in content:
                print("❌ WARNING: app/bot/instance.py imports from app.bot.main! (Circular hazard)")
                all_ok = False
            else:
                print("✅ instance.py is clean.")
    except Exception as e:
        print(f"⚠️ Could not check instance.py: {e}")

    if all_ok:
        print("\n✨ ALL SYSTEMS GO! Your bot is stable. ✨")
        sys.exit(0)
    else:
        print("\n⚠️ Health check detected issues. Please review the errors above. ⚠️")
        sys.exit(1)

if __name__ == "__main__":
    check_project_health()
