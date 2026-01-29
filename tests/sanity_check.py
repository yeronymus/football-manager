import sys
import os
import pkgutil
import importlib
import logging

# Add project root to path
sys.path.append(os.getcwd())

# Dummy environment variables to prevent Config crash
os.environ.setdefault("BOT_TOKEN", "123:test")
os.environ.setdefault("POSTGRES_USER", "user")
os.environ.setdefault("POSTGRES_PASSWORD", "pass")
os.environ.setdefault("POSTGRES_DB", "db")
os.environ.setdefault("POSTGRES_HOST", "localhost")

def check_imports():
    """
    Walks through the application packages and attempts to import them.
    This catches SyntaxErrors, IndentationErrors, and top-level NameErrors.
    """
    pkgs = ["app"]
    error_count = 0
    
    print("🔍 Starting Codebase Sanity Check...")
    
    for pkg_name in pkgs:
        package = importlib.import_module(pkg_name)
        for _, name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            try:
                print(f"Checking {name}...", end="")
                importlib.import_module(name)
                print(" OK")
            except Exception as e:
                print(f" FAIL\n❌ Error importing {name}: {e}")
                error_count += 1
                
    if error_count == 0:
        print("\n✅ Sanity Check Passed: All modules imported successfully.")
        sys.exit(0)
    else:
        print(f"\n🚫 Sanity Check Failed: {error_count} errors found.")
        sys.exit(1)

if __name__ == "__main__":
    check_imports()
