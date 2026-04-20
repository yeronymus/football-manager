import sys
import ast
from pathlib import Path

def check_project_health():
    print("🚀 Starting Football Manager Bot Health Check...")
    
    critical_files = [
        "app/bot/instance.py",
        "app/bot/main.py",
        "app/bot/listeners.py",
        "app/core/events.py",
        "app/core/domain/dto.py",
        "app/core/services/game_lifecycle.py",
        "app/api/routers/admin.py",
        "app/api/auth.py",
        "app/api/routers/users.py",
        "app/api/routers/games.py",
        "app/api/main.py",
        "app/config.py",
    ]
    
    all_ok = True
    base_path = Path(__file__).parent
    
    print("\n🔍 Checking for syntax errors...")
    for file_path in critical_files:
        full_path = base_path / file_path
        if not full_path.exists():
            print(f"❌ MISSING: {file_path}")
            all_ok = False
            continue
            
        try:
            with open(full_path) as f:
                ast.parse(f.read())
            print(f"✅ OK: {file_path}")
        except SyntaxError as e:
            print(f"❌ SYNTAX ERROR in {file_path}: line {e.lineno}: {e.msg}")
            all_ok = False

    print("\n📦 Checking layer boundaries...")
    
    # core/ must NOT import from api/
    for py_file in (base_path / "app/core").rglob("*.py"):
        with open(py_file) as f:
            content = f.read()
        if "from app.api" in content or "import app.api" in content:
            rel = py_file.relative_to(base_path)
            print(f"❌ LAYER VIOLATION: {rel} imports from app.api!")
            all_ok = False

    # api/ must NOT have top-level bot imports (except main.py bootstrap)
    for py_file in (base_path / "app/api").rglob("*.py"):
        rel = py_file.relative_to(base_path)
        if "main.py" in str(rel):
            continue  # bootstrap is allowed
        with open(py_file) as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError:
                continue
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module and "app.bot" in node.module:
                    print(f"⚠️  TOP-LEVEL bot import in {rel}: line {node.lineno}")
                    # Not a hard fail, just a warning

    # instance.py must not import from bot.main
    try:
        with open(base_path / "app/bot/instance.py") as f:
            content = f.read()
        if "app.bot.main" in content:
            print("❌ CIRCULAR HAZARD: instance.py imports from app.bot.main!")
            all_ok = False
        else:
            print("✅ instance.py is clean.")
    except Exception as e:
        print(f"⚠️ Could not check instance.py: {e}")

    if all_ok:
        print("\n✨ ALL SYSTEMS GO! Your bot is stable. ✨")
        sys.exit(0)
    else:
        print("\n⚠️ Health check detected issues. Please review. ⚠️")
        sys.exit(1)

if __name__ == "__main__":
    check_project_health()
